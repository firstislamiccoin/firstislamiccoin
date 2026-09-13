/// Legacy (non-segwit, non-coinstake) FirstIslamicCoin transaction construction
/// and signing.
///
/// Scope note: this wallet only ever builds and signs *ordinary* P2PKH
/// spends -- never a coinstake (no on-device staking, by design; see
/// docs/store-compliance.md). Ordinary FIC transactions use nVersion=2,
/// which is wire-compatible with standard Bitcoin legacy transaction
/// serialization (no nTime field -- that only applies to nVersion<2,
/// which this wallet never produces). That equivalence is why this can
/// be hand-implemented against the standard format directly rather than
/// needing any FIC-specific transaction-format handling here.
///
/// Only legacy P2PKH signing (SIGHASH_ALL) is implemented. This wallet
/// defaults new receive addresses to P2PKH (see wallet_service.dart) so
/// it only ever needs to sign inputs of that one type; it can still
/// *send to* any address type (P2PKH/P2SH/P2WPKH) by constructing the
/// matching output script, which needs no signing-side support.
library;

import 'dart:typed_data';

import 'package:pointycastle/api.dart';
import 'package:pointycastle/digests/sha256.dart';
import 'package:pointycastle/ecc/api.dart';
import 'package:pointycastle/ecc/curves/secp256k1.dart';
import 'package:pointycastle/macs/hmac.dart';
import 'package:pointycastle/random/fortuna_random.dart';
import 'package:pointycastle/signers/ecdsa_signer.dart';

import '../config/network_config.dart';
import 'address.dart' show hash160, p2shAddress;

const int sighashAll = 0x01;

class Utxo {
  final Uint8List txid; // internal byte order (as stored/hashed, NOT display/reversed)
  final int vout;
  final int valueSatoshis;
  final Uint8List pubkeyHash; // the 20-byte hash160 this UTXO pays to (must be P2PKH)
  // Per-input signing key override -- needed once a wallet can spend UTXOs
  // sitting at more than one derived address in the same transaction (the
  // global privateKey/publicKeyCompressed args to buildAndSignTransaction
  // only support one key for every input). Null falls back to those
  // global args, so existing single-key callers are unaffected.
  final Uint8List? privateKey;
  final Uint8List? publicKeyCompressed;
  // BIP125 opt-in replace-by-fee signal (any value below 0xfffffffe).
  // Defaulting every new send to this (rather than the plain
  // 0xffffffff every send used before this field existed) is what makes
  // "bump fee" possible later -- the node's inherited Bitcoin Core
  // mempool policy only allows a conflicting replacement transaction
  // when the original signalled replaceability this way. A transaction
  // built before this default existed did not signal it and can't be
  // bumped through standard replacement -- see wallet_service.dart's
  // bumpFee().
  final int sequence;
  const Utxo({
    required this.txid,
    required this.vout,
    required this.valueSatoshis,
    required this.pubkeyHash,
    this.privateKey,
    this.publicKeyCompressed,
    this.sequence = 0xfffffffd,
  });
}

class TxOutputSpec {
  final Uint8List scriptPubKey;
  final int valueSatoshis;
  const TxOutputSpec(this.scriptPubKey, this.valueSatoshis);
}

/// scriptPubKey for a standard P2PKH output: OP_DUP OP_HASH160 <20 bytes>
/// OP_EQUALVERIFY OP_CHECKSIG
Uint8List p2pkhScriptPubKey(Uint8List pubkeyHash20) {
  return Uint8List.fromList([
    0x76, 0xa9, 0x14, ...pubkeyHash20, 0x88, 0xac,
  ]);
}

/// scriptPubKey for a standard P2SH output: OP_HASH160 <20 bytes> OP_EQUAL
Uint8List p2shScriptPubKey(Uint8List scriptHash20) {
  return Uint8List.fromList([0xa9, 0x14, ...scriptHash20, 0x87]);
}

/// scriptPubKey for a P2WPKH output: OP_0 <20 bytes>
Uint8List p2wpkhScriptPubKey(Uint8List pubkeyHash20) {
  return Uint8List.fromList([0x00, 0x14, ...pubkeyHash20]);
}

Uint8List _varInt(int n) {
  if (n < 0xfd) return Uint8List.fromList([n]);
  if (n <= 0xffff) {
    final b = Uint8List(3)..[0] = 0xfd;
    b.buffer.asByteData().setUint16(1, n, Endian.little);
    return b;
  }
  if (n <= 0xffffffff) {
    final b = Uint8List(5)..[0] = 0xfe;
    b.buffer.asByteData().setUint32(1, n, Endian.little);
    return b;
  }
  final b = Uint8List(9)..[0] = 0xff;
  b.buffer.asByteData().setUint64(1, n, Endian.little);
  return b;
}

Uint8List _uint32le(int n) {
  final b = Uint8List(4);
  b.buffer.asByteData().setUint32(0, n, Endian.little);
  return b;
}

Uint8List _uint64le(int n) {
  final b = Uint8List(8);
  b.buffer.asByteData().setUint64(0, n, Endian.little);
  return b;
}

Uint8List _doubleSha256(Uint8List data) {
  final once = SHA256Digest().process(data);
  return SHA256Digest().process(once);
}

class _TxInput {
  final Uint8List prevTxid;
  final int prevVout;
  Uint8List scriptSig;
  final int sequence;
  _TxInput(this.prevTxid, this.prevVout, this.scriptSig, {this.sequence = 0xffffffff});
}

/// Serializes a legacy transaction, given already-finalized scriptSigs
/// (or empty scriptSigs, for sighash preimage construction -- see below).
Uint8List _serialize(int version, List<_TxInput> inputs, List<TxOutputSpec> outputs, int locktime) {
  final buf = BytesBuilder();
  buf.add(_uint32le(version));
  buf.add(_varInt(inputs.length));
  for (final input in inputs) {
    buf.add(input.prevTxid);
    buf.add(_uint32le(input.prevVout));
    buf.add(_varInt(input.scriptSig.length));
    buf.add(input.scriptSig);
    buf.add(_uint32le(input.sequence));
  }
  buf.add(_varInt(outputs.length));
  for (final output in outputs) {
    buf.add(_uint64le(output.valueSatoshis));
    buf.add(_varInt(output.scriptPubKey.length));
    buf.add(output.scriptPubKey);
  }
  buf.add(_uint32le(locktime));
  return buf.toBytes();
}

/// Legacy SIGHASH_ALL preimage for signing [inputIndex], per the original
/// Bitcoin signing algorithm: every other input's scriptSig is emptied,
/// the input being signed gets the prevout's scriptPubKey substituted in
/// as its scriptSig, and the sighash type is appended as a 4-byte
/// little-endian trailer before double-SHA256.
Uint8List _legacySighash({
  required List<_TxInput> inputs,
  required List<TxOutputSpec> outputs,
  required int inputIndex,
  required Uint8List subscript, // the prevout's scriptPubKey being spent
  required int locktime,
}) {
  final blanked = <_TxInput>[
    for (var i = 0; i < inputs.length; i++)
      _TxInput(
        inputs[i].prevTxid,
        inputs[i].prevVout,
        i == inputIndex ? subscript : Uint8List(0),
        sequence: inputs[i].sequence,
      ),
  ];
  final preimage = _serialize(2, blanked, outputs, locktime);
  final withSighashType = Uint8List.fromList([...preimage, ...(_uint32le(sighashAll))]);
  return _doubleSha256(withSighashType);
}

/// DER-encode an ECDSA signature the way Bitcoin-family scriptSigs expect
/// (low-S already enforced by using pointycastle's deterministic signer
/// with the secp256k1 curve order check below).
Uint8List _derEncodeSignature(ECSignature sig) {
  final n = ECCurve_secp256k1().n;
  var s = sig.s;
  if (s > (n >> 1)) {
    s = n - s; // enforce low-S (BIP62/policy convention)
  }
  Uint8List encodeInt(BigInt v) {
    var bytes = _bigIntToBytes(v);
    if (bytes.isNotEmpty && bytes[0] & 0x80 != 0) {
      bytes = Uint8List.fromList([0, ...bytes]);
    }
    return Uint8List.fromList([0x02, bytes.length, ...bytes]);
  }

  final rEnc = encodeInt(sig.r);
  final sEnc = encodeInt(s);
  return Uint8List.fromList([0x30, rEnc.length + sEnc.length, ...rEnc, ...sEnc]);
}

Uint8List _bigIntToBytes(BigInt v) {
  if (v == BigInt.zero) return Uint8List.fromList([0]);
  var hex = v.toRadixString(16);
  if (hex.length % 2 != 0) hex = '0$hex';
  final bytes = Uint8List(hex.length ~/ 2);
  for (var i = 0; i < bytes.length; i++) {
    bytes[i] = int.parse(hex.substring(i * 2, i * 2 + 2), radix: 16);
  }
  return bytes;
}

/// Build and sign a legacy P2PKH-input transaction. Every input must be
/// signable with either its own [Utxo.privateKey]/[Utxo.publicKeyCompressed]
/// (needed once a send can span more than one derived address) or the
/// global [privateKey]/[publicKeyCompressed] args, used as the fallback
/// for any input that doesn't specify its own.
Uint8List buildAndSignTransaction({
  required List<Utxo> inputs,
  required List<TxOutputSpec> outputs,
  Uint8List? privateKey,
  Uint8List? publicKeyCompressed,
  int locktime = 0,
}) {
  if (inputs.isEmpty) {
    throw ArgumentError('No inputs provided');
  }
  final txInputs = [
    for (final u in inputs) _TxInput(u.txid, u.vout, Uint8List(0), sequence: u.sequence),
  ];

  final domain = ECDomainParameters('secp256k1');

  for (var i = 0; i < inputs.length; i++) {
    final inputPrivateKey = inputs[i].privateKey ?? privateKey;
    final inputPublicKey = inputs[i].publicKeyCompressed ?? publicKeyCompressed;
    if (inputPrivateKey == null || inputPublicKey == null) {
      throw ArgumentError('Input $i has no signing key (neither its own nor a global fallback)');
    }
    final signer = ECDSASigner(null, HMac(SHA256Digest(), 64));
    final priv = ECPrivateKey(_bytesToBigInt(inputPrivateKey), domain);
    signer.init(true, PrivateKeyParameter(priv));

    final subscript = p2pkhScriptPubKey(inputs[i].pubkeyHash);
    final sighash = _legacySighash(
      inputs: txInputs,
      outputs: outputs,
      inputIndex: i,
      subscript: subscript,
      locktime: locktime,
    );
    final sig = signer.generateSignature(sighash) as ECSignature;
    final derSig = _derEncodeSignature(sig);
    final sigWithType = Uint8List.fromList([...derSig, sighashAll]);
    // scriptSig: <sig+sighashtype> <pubkey>
    txInputs[i].scriptSig = Uint8List.fromList([
      sigWithType.length, ...sigWithType,
      inputPublicKey.length, ...inputPublicKey,
    ]);
  }

  return _serialize(2, txInputs, outputs, locktime);
}

/// A locally-recorded sent-tx entry, kept purely so "bump fee" can
/// rebuild the exact same transaction later with a higher fee -- see
/// wallet_service.dart's recordSentTx/bumpFee and web-wallet/
/// crypto.js's buildBumpFeeTransaction, which this mirrors exactly.
class SentTxInput {
  final String txidHex; // display order, as returned by the gateway
  final int vout;
  final int valueSatoshis;
  final int derivationIndex;
  const SentTxInput({
    required this.txidHex,
    required this.vout,
    required this.valueSatoshis,
    required this.derivationIndex,
  });
  Map<String, dynamic> toJson() =>
      {'txid': txidHex, 'vout': vout, 'valueSatoshis': valueSatoshis, 'derivationIndex': derivationIndex};
  factory SentTxInput.fromJson(Map<String, dynamic> j) => SentTxInput(
        txidHex: j['txid'] as String,
        vout: j['vout'] as int,
        valueSatoshis: j['valueSatoshis'] as int,
        derivationIndex: j['derivationIndex'] as int,
      );
}

class SentTxOutput {
  final String scriptPubKeyHex;
  final int valueSatoshis;
  final bool isChange;
  const SentTxOutput({required this.scriptPubKeyHex, required this.valueSatoshis, this.isChange = false});
  Map<String, dynamic> toJson() =>
      {'scriptPubKeyHex': scriptPubKeyHex, 'valueSatoshis': valueSatoshis, 'isChange': isChange};
  factory SentTxOutput.fromJson(Map<String, dynamic> j) => SentTxOutput(
        scriptPubKeyHex: j['scriptPubKeyHex'] as String,
        valueSatoshis: j['valueSatoshis'] as int,
        isChange: j['isChange'] as bool? ?? false,
      );
}

class SentTxRecord {
  final List<SentTxInput> inputs;
  final List<SentTxOutput> outputs;
  final int feeSatoshis;
  const SentTxRecord({required this.inputs, required this.outputs, required this.feeSatoshis});
  Map<String, dynamic> toJson() => {
        'inputs': [for (final i in inputs) i.toJson()],
        'outputs': [for (final o in outputs) o.toJson()],
        'feeSatoshis': feeSatoshis,
      };
  factory SentTxRecord.fromJson(Map<String, dynamic> j) => SentTxRecord(
        inputs: [
          for (final i in (j['inputs'] as List)) SentTxInput.fromJson((i as Map).cast<String, dynamic>()),
        ],
        outputs: [
          for (final o in (j['outputs'] as List)) SentTxOutput.fromJson((o as Map).cast<String, dynamic>()),
        ],
        feeSatoshis: j['feeSatoshis'] as int,
      );
}

class BumpFeeResult {
  final Uint8List rawTx;
  final List<SentTxOutput> newOutputs;
  const BumpFeeResult(this.rawTx, this.newOutputs);
}

/// Rebuilds and signs a replacement transaction spending the exact same
/// inputs as [record], paying every non-change output the same amount,
/// only shrinking the change output by the fee increase. Throws
/// [StateError] if there's no change output to shrink, or not enough
/// change to absorb the increase -- fails closed rather than guessing
/// at a fallback (e.g. pulling in an extra input) for either case.
/// [inputPrivateKeys]/[inputPublicKeys][i] must correspond to
/// [record]'s inputs[i].
BumpFeeResult buildBumpFeeTransaction({
  required SentTxRecord record,
  required int newFeeSatoshis,
  required List<Uint8List> inputPrivateKeys,
  required List<Uint8List> inputPublicKeys,
}) {
  final changeIndex = record.outputs.indexWhere((o) => o.isChange);
  if (changeIndex == -1) {
    throw StateError("This transaction has no change output to reduce -- can't bump its fee automatically here.");
  }
  final feeIncrease = newFeeSatoshis - record.feeSatoshis;
  final newChangeValue = record.outputs[changeIndex].valueSatoshis - feeIncrease;
  if (newChangeValue <= 0) {
    throw StateError('Not enough change left to cover a higher fee.');
  }
  final inputs = <Utxo>[
    for (var i = 0; i < record.inputs.length; i++)
      Utxo(
        txid: _hexToBytesReversedLocal(record.inputs[i].txidHex),
        vout: record.inputs[i].vout,
        valueSatoshis: record.inputs[i].valueSatoshis,
        pubkeyHash: hash160(inputPublicKeys[i]),
        privateKey: inputPrivateKeys[i],
        publicKeyCompressed: inputPublicKeys[i],
      ),
  ];
  final outputs = <TxOutputSpec>[
    for (var i = 0; i < record.outputs.length; i++)
      TxOutputSpec(
        _hexToBytesLocal(record.outputs[i].scriptPubKeyHex),
        i == changeIndex ? newChangeValue : record.outputs[i].valueSatoshis,
      ),
  ];
  final rawTx = buildAndSignTransaction(inputs: inputs, outputs: outputs);
  final newOutputs = <SentTxOutput>[
    for (var i = 0; i < record.outputs.length; i++)
      i == changeIndex
          ? SentTxOutput(scriptPubKeyHex: record.outputs[i].scriptPubKeyHex, valueSatoshis: newChangeValue, isChange: true)
          : record.outputs[i],
  ];
  return BumpFeeResult(rawTx, newOutputs);
}

Uint8List _hexToBytesReversedLocal(String hex) {
  final bytes = _hexToBytesLocal(hex);
  return Uint8List.fromList(bytes.reversed.toList());
}

BigInt _bytesToBigInt(Uint8List bytes) {
  var result = BigInt.zero;
  for (final b in bytes) {
    result = (result << 8) | BigInt.from(b);
  }
  return result;
}

/// Deterministically-seeded PRNG hookup point, kept separate so tests can
/// substitute a fixed seed for reproducible signature tests. Not used by
/// ECDSASigner directly (it uses RFC6979 deterministic nonces via the
/// HMac-DRBG passed to its constructor above, so signing is already
/// deterministic and reproducible without needing real randomness) --
/// kept here only in case a future revision needs a source of randomness
/// elsewhere (e.g. mnemonic generation already gets its own randomness
/// from bip39's own generator, not this).
FortunaRandom seededRandom(Uint8List seed) {
  final r = FortunaRandom();
  r.seed(KeyParameter(seed.length >= 32 ? seed.sublist(0, 32) : Uint8List(32)..setRange(0, seed.length, seed)));
  return r;
}

// -- N-of-M P2SH multisig --
//
// Mirrors web-wallet/crypto.js's multisig functions exactly (same
// script layout, same signing rules, same proposal/merge/finalize
// flow) -- see that file's comment block for the full design reasoning
// (standard Bitcoin-family bare multisig inside P2SH, no new consensus
// feature needed; a minimal from-scratch partial-signature-exchange
// format scoped to this wallet's needs, not a general PSBT
// implementation).

const int opCheckMultisig = 0xae;

int _opN(int n) {
  if (n < 1 || n > 16) throw ArgumentError('OP_N only supports 1..16');
  return 0x50 + n;
}

/// pubkeysCompressed: in the fixed order all cosigners must agree on
/// ahead of time (order determines both the resulting address AND the
/// required signature order when spending).
Uint8List createMultisigRedeemScript(int m, List<Uint8List> pubkeysCompressed) {
  if (m < 1 || m > pubkeysCompressed.length) {
    throw ArgumentError('m must be between 1 and the number of pubkeys');
  }
  if (pubkeysCompressed.length > 16) {
    throw ArgumentError('at most 16 pubkeys supported (OP_N range)');
  }
  final parts = BytesBuilder()..addByte(_opN(m));
  for (final pk in pubkeysCompressed) {
    if (pk.length != 33) {
      throw ArgumentError('Only compressed (33-byte) pubkeys are supported');
    }
    parts.addByte(pk.length);
    parts.add(pk);
  }
  parts.addByte(_opN(pubkeysCompressed.length));
  parts.addByte(opCheckMultisig);
  return parts.toBytes();
}

String multisigAddress(Uint8List redeemScript, NetworkConfig network) =>
    p2shAddress(hash160(redeemScript), network);

String _bytesToHexLocal(Uint8List b) => b.map((x) => x.toRadixString(16).padLeft(2, '0')).join();

Uint8List _hexToBytesLocal(String hex) {
  final out = Uint8List(hex.length ~/ 2);
  for (var i = 0; i < out.length; i++) {
    out[i] = int.parse(hex.substring(i * 2, i * 2 + 2), radix: 16);
  }
  return out;
}

/// A partially-signed multisig spend proposal, JSON-serializable (hex
/// strings throughout) so it can be handed off between cosigners however
/// they like -- see web-wallet/crypto.js's module comment for why this
/// exists instead of a general PSBT implementation.
class MultisigProposal {
  final int version;
  final int locktime;
  final List<Map<String, dynamic>> inputs; // {txid, vout, valueSatoshis, redeemScript} hex
  final List<Map<String, dynamic>> outputs; // {scriptPubKey, valueSatoshis} hex
  final List<Map<String, String>> signatures; // per-input: pubkeyHex -> derSigWithTypeHex

  MultisigProposal({
    required this.version,
    required this.locktime,
    required this.inputs,
    required this.outputs,
    required this.signatures,
  });

  Map<String, dynamic> toJson() => {
        'version': version,
        'locktime': locktime,
        'inputs': inputs,
        'outputs': outputs,
        'signatures': signatures,
      };

  factory MultisigProposal.fromJson(Map<String, dynamic> json) => MultisigProposal(
        version: json['version'] as int,
        locktime: json['locktime'] as int,
        inputs: (json['inputs'] as List).cast<Map<String, dynamic>>(),
        outputs: (json['outputs'] as List).cast<Map<String, dynamic>>(),
        signatures: (json['signatures'] as List)
            .map((s) => (s as Map).cast<String, String>())
            .toList(),
      );
}

MultisigProposal createMultisigProposal({
  required List<Utxo> inputs,
  required List<Uint8List> redeemScripts, // one per input
  required List<TxOutputSpec> outputs,
  int locktime = 0,
}) {
  return MultisigProposal(
    version: 2,
    locktime: locktime,
    inputs: [
      for (var i = 0; i < inputs.length; i++)
        {
          'txid': _bytesToHexLocal(inputs[i].txid),
          'vout': inputs[i].vout,
          'valueSatoshis': inputs[i].valueSatoshis,
          'redeemScript': _bytesToHexLocal(redeemScripts[i]),
        },
    ],
    outputs: [
      for (final o in outputs) {'scriptPubKey': _bytesToHexLocal(o.scriptPubKey), 'valueSatoshis': o.valueSatoshis},
    ],
    signatures: [for (var _ in inputs) <String, String>{}],
  );
}

List<_TxInput> _proposalTxInputs(MultisigProposal p) => [
      for (final inp in p.inputs)
        _TxInput(_hexToBytesLocal(inp['txid'] as String), inp['vout'] as int, Uint8List(0)),
    ];

List<TxOutputSpec> _proposalOutputs(MultisigProposal p) => [
      for (final out in p.outputs)
        TxOutputSpec(_hexToBytesLocal(out['scriptPubKey'] as String), out['valueSatoshis'] as int),
    ];

bool _scriptContainsPubkey(Uint8List redeemScript, Uint8List pubkeyCompressed) {
  final needle = _bytesToHexLocal(pubkeyCompressed);
  final hex = _bytesToHexLocal(redeemScript);
  return hex.contains(needle);
}

/// Mutates and returns [proposal] with this signer's signature added for
/// every input whose redeemScript this pubkey actually appears in.
MultisigProposal signMultisigProposal(
  MultisigProposal proposal,
  Uint8List privateKey,
  Uint8List publicKeyCompressed,
) {
  final txInputs = _proposalTxInputs(proposal);
  final outputs = _proposalOutputs(proposal);
  final pubkeyHex = _bytesToHexLocal(publicKeyCompressed);

  final signer = ECDSASigner(null, HMac(SHA256Digest(), 64));
  final domain = ECDomainParameters('secp256k1');
  final priv = ECPrivateKey(_bytesToBigInt(privateKey), domain);
  signer.init(true, PrivateKeyParameter(priv));

  for (var i = 0; i < proposal.inputs.length; i++) {
    final redeemScript = _hexToBytesLocal(proposal.inputs[i]['redeemScript'] as String);
    if (!_scriptContainsPubkey(redeemScript, publicKeyCompressed)) continue;
    // For OP_CHECKMULTISIG the subscript is the redeem script itself
    // (not a P2PKH scriptPubKey) -- the classic Bitcoin signing rule
    // for bare-multisig-in-P2SH.
    final sighash = _legacySighash(
      inputs: txInputs,
      outputs: outputs,
      inputIndex: i,
      subscript: redeemScript,
      locktime: proposal.locktime,
    );
    final sig = signer.generateSignature(sighash) as ECSignature;
    final derSig = _derEncodeSignature(sig);
    proposal.signatures[i][pubkeyHex] = _bytesToHexLocal(Uint8List.fromList([...derSig, sighashAll]));
  }
  return proposal;
}

/// Combines signatures collected across independently-signed copies of
/// the same proposal into one.
MultisigProposal mergeMultisigProposals(List<MultisigProposal> proposals) {
  final merged = MultisigProposal.fromJson(proposals.first.toJson());
  for (final p in proposals.skip(1)) {
    for (var i = 0; i < merged.signatures.length; i++) {
      merged.signatures[i].addAll(p.signatures[i]);
    }
  }
  return merged;
}

List<String> _parsePubkeysInOrder(Uint8List redeemScript) {
  // Walk the script's push opcodes to recover pubkeys in their original
  // script order -- required because OP_CHECKMULTISIG's signature
  // matching is order-sensitive.
  final pubkeys = <String>[];
  var i = 1; // skip leading OP_m
  while (i < redeemScript.length) {
    final opcode = redeemScript[i];
    if (opcode >= 1 && opcode <= 75) {
      pubkeys.add(_bytesToHexLocal(redeemScript.sublist(i + 1, i + 1 + opcode)));
      i += 1 + opcode;
    } else {
      break; // hit OP_n / OP_CHECKMULTISIG -- done
    }
  }
  return pubkeys;
}

/// Once enough signatures are collected (per input's redeemScript's own
/// m-of-n), assembles the final scriptSig for each input and returns the
/// serialized, broadcast-ready raw transaction. Throws if any input is
/// still short of its required signature count.
Uint8List finalizeMultisigTransaction(MultisigProposal proposal) {
  final txInputs = _proposalTxInputs(proposal);
  final outputs = _proposalOutputs(proposal);

  for (var i = 0; i < proposal.inputs.length; i++) {
    final redeemScript = _hexToBytesLocal(proposal.inputs[i]['redeemScript'] as String);
    final m = redeemScript[0] - 0x50;
    final pubkeysInOrder = _parsePubkeysInOrder(redeemScript);
    final collected = proposal.signatures[i];
    final orderedSigs = [
      for (final pk in pubkeysInOrder)
        if (collected.containsKey(pk)) collected[pk]!,
    ];
    if (orderedSigs.length < m) {
      throw StateError('Input $i has ${orderedSigs.length} signature(s), needs $m');
    }
    final sigsToUse = orderedSigs.take(m).map(_hexToBytesLocal).toList();
    // OP_0 dummy element (the historical OP_CHECKMULTISIG off-by-one
    // quirk, now a fixed, standard part of the script format) + each
    // signature push + the redeem script push.
    final parts = BytesBuilder()..addByte(0x00);
    for (final sig in sigsToUse) {
      parts.addByte(sig.length);
      parts.add(sig);
    }
    parts.add(_varInt(redeemScript.length));
    parts.add(redeemScript);
    txInputs[i].scriptSig = parts.toBytes();
  }
  return _serialize(proposal.version, txInputs, outputs, proposal.locktime);
}
