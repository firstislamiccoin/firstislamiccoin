// Tests transaction construction/signing against pointycastle's own
// ECDSA verifier -- i.e. "does the signature this wallet produces
// actually verify against the pubkey and sighash it claims to be for,"
// which is the property that actually matters for a signer (internal
// self-consistency of the hand-rolled serialization is necessary but not
// sufficient on its own).
//
// The expected sighash preimage is reconstructed directly from the known
// single-input/single-output test fixture (not by parsing bytes back out
// of the signer's own output), so this test doesn't just check the
// signer agrees with itself.
import 'dart:typed_data';

import 'package:fic_wallet/crypto/address.dart';
import 'package:fic_wallet/crypto/transaction.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pointycastle/api.dart';
import 'package:pointycastle/digests/sha256.dart';
import 'package:pointycastle/ecc/api.dart';
import 'package:pointycastle/signers/ecdsa_signer.dart';

final _domain = ECDomainParameters('secp256k1');

Uint8List _fixedPrivateKey() =>
    Uint8List.fromList(List<int>.generate(32, (i) => i + 1));

BigInt _bytesToBigInt(Uint8List bytes) {
  var result = BigInt.zero;
  for (final b in bytes) {
    result = (result << 8) | BigInt.from(b);
  }
  return result;
}

ECPublicKey _publicKeyFor(Uint8List privateKey) {
  final d = _bytesToBigInt(privateKey);
  final q = _domain.G * d;
  return ECPublicKey(q, _domain);
}

Uint8List _compress(ECPublicKey pub) {
  final q = pub.Q!;
  final x = q.x!.toBigInteger()!;
  final y = q.y!.toBigInteger()!;
  final prefix = y.isEven ? 0x02 : 0x03;
  return Uint8List.fromList([prefix, ..._bigIntTo32Bytes(x)]);
}

Uint8List _bigIntTo32Bytes(BigInt v) {
  var hex = v.toRadixString(16);
  if (hex.length % 2 != 0) hex = '0$hex';
  final bytes = <int>[];
  for (var i = 0; i < hex.length; i += 2) {
    bytes.add(int.parse(hex.substring(i, i + 2), radix: 16));
  }
  final out = Uint8List(32);
  out.setRange(32 - bytes.length, 32, bytes);
  return out;
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

/// Decodes a DER signature of the exact short-form shape
/// `_derEncodeSignature` in transaction.dart produces (single-byte
/// length fields throughout -- always true for secp256k1 r/s values).
ECSignature _decodeDer(Uint8List der) {
  var offset = 2; // 0x30 <total-len>
  offset += 1; // 0x02
  final rLen = der[offset++];
  final r = _bytesToBigInt(der.sublist(offset, offset + rLen));
  offset += rLen;
  offset += 1; // 0x02
  final sLen = der[offset++];
  final s = _bytesToBigInt(der.sublist(offset, offset + sLen));
  return ECSignature(r, s);
}

void main() {
  test('p2pkhScriptPubKey has the expected standard shape', () {
    final hash = Uint8List.fromList(List<int>.generate(20, (i) => i));
    final script = p2pkhScriptPubKey(hash);
    expect(script.length, 25);
    expect(script[0], 0x76); // OP_DUP
    expect(script[1], 0xa9); // OP_HASH160
    expect(script[2], 0x14); // push 20 bytes
    expect(script.sublist(3, 23), hash);
    expect(script[23], 0x88); // OP_EQUALVERIFY
    expect(script[24], 0xac); // OP_CHECKSIG
  });

  test('signing is deterministic (RFC6979) for identical inputs', () {
    final privateKey = _fixedPrivateKey();
    final publicKey = _compress(_publicKeyFor(privateKey));
    final utxo = Utxo(
      txid: Uint8List(32)..fillRange(0, 32, 0xaa),
      vout: 0,
      valueSatoshis: 100000000,
      pubkeyHash: hash160(publicKey),
    );
    final outputs = [TxOutputSpec(p2pkhScriptPubKey(Uint8List(20)), 99990000)];

    final a = buildAndSignTransaction(
        inputs: [utxo], outputs: outputs, privateKey: privateKey, publicKeyCompressed: publicKey);
    final b = buildAndSignTransaction(
        inputs: [utxo], outputs: outputs, privateKey: privateKey, publicKeyCompressed: publicKey);
    expect(a, b);
  });

  test('buildAndSignTransaction produces a signature verifiable against the '
      'independently-reconstructed sighash', () {
    final privateKey = _fixedPrivateKey();
    final publicKey = _compress(_publicKeyFor(privateKey));
    final pubkeyHash = hash160(publicKey);

    final prevTxid = Uint8List(32)..fillRange(0, 32, 0xaa);
    const prevVout = 0;
    const inputValue = 100000000;
    final destHash = Uint8List.fromList(List<int>.generate(20, (i) => 20 - i));
    const outputValue = 99990000;

    final utxo = Utxo(txid: prevTxid, vout: prevVout, valueSatoshis: inputValue, pubkeyHash: pubkeyHash);
    final outputScript = p2pkhScriptPubKey(destHash);
    final outputs = [TxOutputSpec(outputScript, outputValue)];

    final rawTx = buildAndSignTransaction(
      inputs: [utxo],
      outputs: outputs,
      privateKey: privateKey,
      publicKeyCompressed: publicKey,
    );

    // Independently reconstruct the legacy SIGHASH_ALL preimage for this
    // exact single-input/single-output fixture, per the classic Bitcoin
    // signing algorithm: version=2, one input with its scriptSig replaced
    // by the prevout's own scriptPubKey (the "subscript"), one output,
    // locktime=0, sighash type (1) appended, double-SHA256.
    final subscript = p2pkhScriptPubKey(pubkeyHash);
    final preimage = BytesBuilder()
      ..add(_u32le(2))
      ..add([1]) // varint: 1 input
      ..add(prevTxid)
      ..add(_u32le(prevVout))
      ..add([subscript.length])
      ..add(subscript)
      ..add(_u32le(0xfffffffd)) // sequence -- Utxo's default BIP125 opt-in-RBF signal
      ..add([1]) // varint: 1 output
      ..add(_u64le(outputValue))
      ..add([outputScript.length])
      ..add(outputScript)
      ..add(_u32le(0)) // locktime
      ..add(_u32le(1)); // sighash type
    final expectedSighash = _doubleSha256(preimage.toBytes());

    // Extract the DER signature from rawTx's scriptSig. Layout is fixed
    // given the fixture above: 4 (version) + 1 (input count) + 32 (prevtxid)
    // + 4 (vout) + 1 (scriptSig varint) = 42 before the scriptSig itself.
    final scriptSigLen = rawTx[41];
    final scriptSig = rawTx.sublist(42, 42 + scriptSigLen);
    final sigLen = scriptSig[0];
    final derWithSighashType = scriptSig.sublist(1, 1 + sigLen);
    final der = derWithSighashType.sublist(0, derWithSighashType.length - 1);
    final pubkeyLen = scriptSig[1 + sigLen];
    final extractedPubkey = scriptSig.sublist(2 + sigLen, 2 + sigLen + pubkeyLen);
    expect(extractedPubkey, publicKey);

    final signature = _decodeDer(der);
    final verifier = ECDSASigner()..init(false, PublicKeyParameter(_publicKeyFor(privateKey)));
    expect(verifier.verifySignature(expectedSighash, signature), isTrue);
  });

  test('buildAndSignTransaction signs each input with its own key when '
      'multiple different keys are used across inputs (multi-address send)', () {
    final privateKeyA = _fixedPrivateKey();
    final publicKeyA = _compress(_publicKeyFor(privateKeyA));
    final privateKeyB = Uint8List.fromList(List<int>.generate(32, (i) => 32 - i));
    final publicKeyB = _compress(_publicKeyFor(privateKeyB));
    expect(publicKeyA, isNot(equals(publicKeyB)));

    final utxoA = Utxo(
      txid: Uint8List(32)..fillRange(0, 32, 0xaa),
      vout: 0,
      valueSatoshis: 100000000,
      pubkeyHash: hash160(publicKeyA),
      privateKey: privateKeyA,
      publicKeyCompressed: publicKeyA,
    );
    final utxoB = Utxo(
      txid: Uint8List(32)..fillRange(0, 32, 0xbb),
      vout: 1,
      valueSatoshis: 50000000,
      pubkeyHash: hash160(publicKeyB),
      privateKey: privateKeyB,
      publicKeyCompressed: publicKeyB,
    );
    final outputs = [TxOutputSpec(p2pkhScriptPubKey(Uint8List(20)), 149990000)];

    final rawTx = buildAndSignTransaction(inputs: [utxoA, utxoB], outputs: outputs);

    // Walk the two scriptSigs out of the raw tx and confirm each pushes
    // its OWN input's public key -- not, say, both pushing key A because
    // a per-input override was silently ignored and a stale global key
    // (which doesn't even exist here -- privateKey/publicKeyCompressed
    // were deliberately omitted) leaked through instead.
    var offset = 4; // version
    offset += 1; // input count varint (2, single-byte)
    for (final expectedPubkey in [publicKeyA, publicKeyB]) {
      offset += 32 + 4; // prevTxid + vout
      final scriptSigLen = rawTx[offset];
      offset += 1;
      final scriptSig = rawTx.sublist(offset, offset + scriptSigLen);
      final sigLen = scriptSig[0];
      final pubkeyLen = scriptSig[1 + sigLen];
      final extractedPubkey = scriptSig.sublist(2 + sigLen, 2 + sigLen + pubkeyLen);
      expect(extractedPubkey, expectedPubkey);
      offset += scriptSigLen + 4; // scriptSig + sequence
    }
  });

  test('buildAndSignTransaction throws if an input has no key at all '
      '(neither its own nor a global fallback)', () {
    final utxo = Utxo(
      txid: Uint8List(32),
      vout: 0,
      valueSatoshis: 1,
      pubkeyHash: Uint8List(20),
    );
    expect(
      () => buildAndSignTransaction(
        inputs: [utxo],
        outputs: [TxOutputSpec(Uint8List(0), 1)],
      ),
      throwsArgumentError,
    );
  });

  test('throws on empty inputs', () {
    expect(
      () => buildAndSignTransaction(
        inputs: [],
        outputs: [TxOutputSpec(Uint8List(0), 1)],
        privateKey: _fixedPrivateKey(),
        publicKeyCompressed: Uint8List(33),
      ),
      throwsArgumentError,
    );
  });
}
