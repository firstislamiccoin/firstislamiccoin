/// Air-gapped transaction signing: splits building and signing an
/// ordinary P2PKH send across two devices/app instances, so the seed can
/// live on a device that never touches the network. Built as an
/// alternative to literal Ledger/Trezor hardware wallet support -- see
/// PARAMETERS.md section 32 for why (neither vendor's SDK will sign for
/// an unregistered coin like FIC, and Trezor isn't accepting new coins
/// at all right now).
///
/// Not a BIP-174 PSBT implementation: both ends of this exchange are
/// always this same wallet's own code, so there's no need for the wire
/// -format complexity a real cross-tool-interoperable PSBT would need --
/// and no third-party PSBT tool would recognize FIC's addresses anyway
/// (see xpub.dart's note on the same point). This is a minimal,
/// purpose-built request/result JSON format, in the same spirit as
/// transaction.dart's own MultisigProposal.
library;

import 'dart:typed_data';

import '../config/network_config.dart';
import 'address.dart' show hash160;
import 'keys.dart' show deriveKey;
import 'transaction.dart' as tx;

Uint8List _hexToBytes(String hex) {
  final out = Uint8List(hex.length ~/ 2);
  for (var i = 0; i < out.length; i++) {
    out[i] = int.parse(hex.substring(i * 2, i * 2 + 2), radix: 16);
  }
  return out;
}

Uint8List _hexToBytesReversed(String hex) => Uint8List.fromList(_hexToBytes(hex).reversed.toList());

bool _bytesEqual(Uint8List a, Uint8List b) {
  if (a.length != b.length) return false;
  for (var i = 0; i < a.length; i++) {
    if (a[i] != b[i]) return false;
  }
  return true;
}

/// One input the online (watch-only) device wants spent: its UTXO
/// identity, the derivation index whose key must sign it, and the
/// pubkey hash that key must actually hash to -- a safety cross-check,
/// not something the offline signer trusts blindly (see
/// [signOfflineTransaction]).
class OfflineSignInput {
  final String txidHex; // conventional display order, as the gateway returns it
  final int vout;
  final int valueSatoshis;
  final int derivationIndex;
  final String pubkeyHashHex;

  const OfflineSignInput({
    required this.txidHex,
    required this.vout,
    required this.valueSatoshis,
    required this.derivationIndex,
    required this.pubkeyHashHex,
  });

  Map<String, dynamic> toJson() => {
        'txid': txidHex,
        'vout': vout,
        'valueSatoshis': valueSatoshis,
        'derivationIndex': derivationIndex,
        'pubkeyHash': pubkeyHashHex,
      };

  factory OfflineSignInput.fromJson(Map<String, dynamic> j) => OfflineSignInput(
        txidHex: j['txid'] as String,
        vout: j['vout'] as int,
        valueSatoshis: j['valueSatoshis'] as int,
        derivationIndex: j['derivationIndex'] as int,
        pubkeyHashHex: j['pubkeyHash'] as String,
      );
}

class OfflineSignOutput {
  final String scriptPubKeyHex;
  final int valueSatoshis;

  const OfflineSignOutput({required this.scriptPubKeyHex, required this.valueSatoshis});

  Map<String, dynamic> toJson() => {'scriptPubKeyHex': scriptPubKeyHex, 'valueSatoshis': valueSatoshis};

  factory OfflineSignOutput.fromJson(Map<String, dynamic> j) => OfflineSignOutput(
        scriptPubKeyHex: j['scriptPubKeyHex'] as String,
        valueSatoshis: j['valueSatoshis'] as int,
      );
}

/// An unsigned-transaction handoff from an online, watch-only device to
/// an offline device holding the matching seed.
class OfflineSignRequest {
  final int locktime;
  final List<OfflineSignInput> inputs;
  final List<OfflineSignOutput> outputs;

  const OfflineSignRequest({required this.locktime, required this.inputs, required this.outputs});

  Map<String, dynamic> toJson() => {
        'type': 'fic_offline_sign_request',
        'v': 1,
        'locktime': locktime,
        'inputs': [for (final i in inputs) i.toJson()],
        'outputs': [for (final o in outputs) o.toJson()],
      };

  factory OfflineSignRequest.fromJson(Map<String, dynamic> j) {
    if (j['type'] != 'fic_offline_sign_request') {
      throw const FormatException('Not a FirstIslamicCoin offline-signing request.');
    }
    return OfflineSignRequest(
      locktime: j['locktime'] as int,
      inputs: [
        for (final i in (j['inputs'] as List)) OfflineSignInput.fromJson((i as Map).cast<String, dynamic>()),
      ],
      outputs: [
        for (final o in (j['outputs'] as List)) OfflineSignOutput.fromJson((o as Map).cast<String, dynamic>()),
      ],
    );
  }
}

/// Runs on the device that holds the seed (meant to be kept offline):
/// re-derives each input's private key from [mnemonic] at its claimed
/// derivation index and signs, after checking the derived key's pubkey
/// hash actually matches what [request] claims for that input. If it
/// doesn't, this seed doesn't own that UTXO -- wrong device, wrong
/// seed, or a tampered/mismatched request -- and this fails closed
/// rather than producing a signature for an input it can't verify
/// belongs to this wallet. Returns a fully signed, broadcast-ready raw
/// transaction. Does no I/O of its own (no scanning, no network) --
/// the caller handles getting [request] in and the result back out.
Uint8List signOfflineTransaction({
  required OfflineSignRequest request,
  required String mnemonic,
  required NetworkConfig network,
}) {
  if (request.inputs.isEmpty) {
    throw ArgumentError('This request has no inputs to sign.');
  }
  final utxos = <tx.Utxo>[];
  for (final inp in request.inputs) {
    final key = deriveKey(mnemonic: mnemonic, network: network, index: inp.derivationIndex);
    final actualHash = hash160(key.publicKey);
    final claimedHash = _hexToBytes(inp.pubkeyHashHex);
    if (!_bytesEqual(actualHash, claimedHash)) {
      throw StateError(
        "Input at derivation index ${inp.derivationIndex} doesn't belong to this "
        "seed. Wrong device, wrong seed, or this request wasn't built for this "
        "wallet -- refusing to sign it.",
      );
    }
    utxos.add(tx.Utxo(
      txid: _hexToBytesReversed(inp.txidHex),
      vout: inp.vout,
      valueSatoshis: inp.valueSatoshis,
      pubkeyHash: actualHash,
      privateKey: key.privateKey,
      publicKeyCompressed: key.publicKey,
    ));
  }
  final outputs = [
    for (final o in request.outputs) tx.TxOutputSpec(_hexToBytes(o.scriptPubKeyHex), o.valueSatoshis),
  ];
  return tx.buildAndSignTransaction(inputs: utxos, outputs: outputs, locktime: request.locktime);
}
