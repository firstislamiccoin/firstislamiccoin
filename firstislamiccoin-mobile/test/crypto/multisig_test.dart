// Mirrors web-wallet's browser-based multisig verification exactly: a
// real 2-of-3 create/sign/finalize cycle, then independent cryptographic
// verification of the resulting signatures (not just "it ran without
// throwing") -- recomputes the expected sighash from the known fixture
// values directly, not by re-deriving from the library's own internals,
// and confirms a signature does NOT verify against the wrong pubkey (so
// the check isn't trivially always-true).
import 'dart:typed_data';

import 'package:fic_wallet/config/network_config.dart';
import 'package:fic_wallet/crypto/transaction.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pointycastle/api.dart';
import 'package:pointycastle/digests/sha256.dart';
import 'package:pointycastle/ecc/api.dart';
import 'package:pointycastle/signers/ecdsa_signer.dart';

final _domain = ECDomainParameters('secp256k1');

BigInt _bytesToBigInt(Uint8List bytes) {
  var result = BigInt.zero;
  for (final b in bytes) {
    result = (result << 8) | BigInt.from(b);
  }
  return result;
}

Uint8List _scalar(int n) {
  final b = Uint8List(32);
  b[31] = n;
  return b;
}

Uint8List _compress(ECPublicKey pub) {
  final q = pub.Q!;
  final x = q.x!.toBigInteger()!;
  final y = q.y!.toBigInteger()!;
  final prefix = y.isEven ? 0x02 : 0x03;
  var hex = x.toRadixString(16);
  if (hex.length % 2 != 0) hex = '0$hex';
  final bytes = <int>[];
  for (var i = 0; i < hex.length; i += 2) {
    bytes.add(int.parse(hex.substring(i, i + 2), radix: 16));
  }
  final out = Uint8List(32);
  out.setRange(32 - bytes.length, 32, bytes);
  return Uint8List.fromList([prefix, ...out]);
}

Uint8List _pubFor(Uint8List priv) {
  final d = _bytesToBigInt(priv);
  final q = _domain.G * d;
  return _compress(ECPublicKey(q, _domain));
}

Uint8List _u32le(int n) {
  final b = Uint8List(4);
  b.buffer.asByteData().setUint32(0, n, Endian.little);
  return b;
}

Uint8List _u64le(int n) {
  final b = Uint8List(8);
  b.buffer.asByteData().setUint64(0, n, Endian.little);
  return b;
}

Uint8List _doubleSha256(Uint8List data) {
  final once = SHA256Digest().process(data);
  return SHA256Digest().process(once);
}

ECSignature _decodeDer(Uint8List der) {
  var offset = 2;
  offset += 1;
  final rLen = der[offset++];
  final r = _bytesToBigInt(der.sublist(offset, offset + rLen));
  offset += rLen;
  offset += 1;
  final sLen = der[offset++];
  final s = _bytesToBigInt(der.sublist(offset, offset + sLen));
  return ECSignature(r, s);
}

void main() {
  test('2-of-3 multisig: create, sign, finalize, and independently verify', () {
    final priv1 = _scalar(1);
    final priv2 = _scalar(2);
    final priv3 = _scalar(3);
    final pub1 = _pubFor(priv1);
    final pub2 = _pubFor(priv2);
    final pub3 = _pubFor(priv3);

    final redeemScript = createMultisigRedeemScript(2, [pub1, pub2, pub3]);
    final address = multisigAddress(redeemScript, NetworkConfig.mainnet);
    expect(address.startsWith('C'), isTrue); // mainnet P2SH prefix (version byte 28, docs/genesis.md)

    final fakeTxid = Uint8List(32)..fillRange(0, 32, 0xaa);
    final destHash = Uint8List(20)..fillRange(0, 20, 0x11);
    final utxo = Utxo(txid: fakeTxid, vout: 0, valueSatoshis: 100000000, pubkeyHash: Uint8List(20));
    final outputs = [TxOutputSpec(p2pkhScriptPubKey(destHash), 99990000)];

    final base = createMultisigProposal(
      inputs: [utxo],
      redeemScripts: [redeemScript],
      outputs: outputs,
    );

    // Signer 1 and signer 3 sign independently (skip signer 2 entirely -- only 2 of 3 needed)
    final p1 = MultisigProposal.fromJson(base.toJson());
    signMultisigProposal(p1, priv1, pub1);
    final p3 = MultisigProposal.fromJson(base.toJson());
    signMultisigProposal(p3, priv3, pub3);

    final merged = mergeMultisigProposals([p1, p3]);
    final rawTx = finalizeMultisigTransaction(merged);

    // Parse the scriptSig back out and verify independently.
    var off = 4 + 1 + 32 + 4;
    final scriptSigLen = rawTx[off];
    off += 1;
    final scriptSig = rawTx.sublist(off, off + scriptSigLen);
    expect(scriptSig[0], 0x00); // OP_0 dummy element

    var p = 1;
    final sig1Len = scriptSig[p];
    p += 1;
    final sig1WithType = scriptSig.sublist(p, p + sig1Len);
    p += sig1Len;
    final sig2Len = scriptSig[p];
    p += 1;
    final sig2WithType = scriptSig.sublist(p, p + sig2Len);
    p += sig2Len;

    final sig1Der = sig1WithType.sublist(0, sig1WithType.length - 1);
    final sig2Der = sig2WithType.sublist(0, sig2WithType.length - 1);

    // Independently reconstruct the expected sighash from the known
    // fixture values (not by calling back into the library's own
    // sighash helper).
    final preimage = BytesBuilder()
      ..add(_u32le(2))
      ..add([1])
      ..add(fakeTxid)
      ..add(_u32le(0))
      ..add([redeemScript.length])
      ..add(redeemScript)
      ..add(_u32le(0xffffffff))
      ..add([1])
      ..add(_u64le(99990000))
      ..add([outputs[0].scriptPubKey.length])
      ..add(outputs[0].scriptPubKey)
      ..add(_u32le(0))
      ..add(_u32le(1));
    final expectedSighash = _doubleSha256(preimage.toBytes());

    final verifier1 = ECDSASigner()..init(false, PublicKeyParameter(ECPublicKey(_domain.G * _bytesToBigInt(priv1), _domain)));
    final verifier2 = ECDSASigner()..init(false, PublicKeyParameter(ECPublicKey(_domain.G * _bytesToBigInt(priv2), _domain)));
    final verifier3 = ECDSASigner()..init(false, PublicKeyParameter(ECPublicKey(_domain.G * _bytesToBigInt(priv3), _domain)));

    final sig1 = _decodeDer(sig1Der);
    final sig2 = _decodeDer(sig2Der);

    expect(verifier1.verifySignature(expectedSighash, sig1), isTrue,
        reason: 'first signature must verify against signer 1\'s pubkey');
    expect(verifier3.verifySignature(expectedSighash, sig2), isTrue,
        reason: 'second signature must verify against signer 3\'s pubkey');
    // Cross-check: signature 1 must NOT verify against signer 2 -- makes
    // sure the check above isn't trivially always-true.
    expect(verifier2.verifySignature(expectedSighash, sig1), isFalse,
        reason: 'signature must not verify against the wrong pubkey');
  });

  test('finalizeMultisigTransaction throws when short of required signatures', () {
    final priv1 = _scalar(1);
    final pub1 = _pubFor(priv1);
    final pub2 = _pubFor(_scalar(2));
    final pub3 = _pubFor(_scalar(3));
    final redeemScript = createMultisigRedeemScript(2, [pub1, pub2, pub3]);

    final fakeTxid = Uint8List(32)..fillRange(0, 32, 0xaa);
    final utxo = Utxo(txid: fakeTxid, vout: 0, valueSatoshis: 100000000, pubkeyHash: Uint8List(20));
    final outputs = [TxOutputSpec(p2pkhScriptPubKey(Uint8List(20)), 99990000)];

    final proposal = createMultisigProposal(inputs: [utxo], redeemScripts: [redeemScript], outputs: outputs);
    signMultisigProposal(proposal, priv1, pub1); // only 1 of 2 required signatures

    expect(() => finalizeMultisigTransaction(proposal), throwsStateError);
  });
}
