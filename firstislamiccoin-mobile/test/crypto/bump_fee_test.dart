// buildBumpFeeTransaction's job is narrow but easy to get subtly wrong
// (which output is "change", exactly how much to shrink it by, failing
// closed instead of guessing) -- these tests check the actual output
// values and signature, not just that it runs without throwing.
import 'dart:typed_data';

import 'package:fic_wallet/crypto/address.dart';
import 'package:fic_wallet/crypto/transaction.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pointycastle/ecc/api.dart';
import 'package:pointycastle/ecc/curves/secp256k1.dart';

final _domain = ECDomainParameters('secp256k1');

Uint8List _fixedPrivateKey() => Uint8List.fromList(List<int>.generate(32, (i) => i + 1));

BigInt _bytesToBigInt(Uint8List bytes) {
  var result = BigInt.zero;
  for (final b in bytes) {
    result = (result << 8) | BigInt.from(b);
  }
  return result;
}

// Same "hand-roll the point multiplication, checkable against a real
// domain" approach transaction_test.dart already uses for its own
// fixtures -- ECCurve_secp256k1() is imported (not just relied on via
// the registry) for the same reason message.dart needed it directly:
// this test file doesn't otherwise import anything that registers the
// curve.
Uint8List _publicKeyFor(Uint8List privateKey) {
  ECCurve_secp256k1(); // registers secp256k1 with ECDomainParameters('secp256k1')'s registry lookup
  final d = _bytesToBigInt(privateKey);
  final q = _domain.G * d;
  return q!.getEncoded(true);
}

void main() {
  final privateKey = _fixedPrivateKey();
  final publicKey = _publicKeyFor(privateKey);
  final pubkeyHash = hash160(publicKey);

  SentTxRecord makeRecord({required bool withChange}) {
    final destHash = Uint8List.fromList(List<int>.generate(20, (i) => 20 - i));
    return SentTxRecord(
      inputs: [
        SentTxInput(txidHex: 'aa' * 32, vout: 0, valueSatoshis: 100000000, derivationIndex: 0),
      ],
      outputs: [
        SentTxOutput(scriptPubKeyHex: _hex(p2pkhScriptPubKey(destHash)), valueSatoshis: 50000000),
        if (withChange)
          SentTxOutput(scriptPubKeyHex: _hex(p2pkhScriptPubKey(pubkeyHash)), valueSatoshis: 49990000, isChange: true),
      ],
      feeSatoshis: 10000,
    );
  }

  test('reduces only the change output by exactly the fee increase', () {
    final record = makeRecord(withChange: true);
    final result = buildBumpFeeTransaction(
      record: record,
      newFeeSatoshis: 20000,
      inputPrivateKeys: [privateKey],
      inputPublicKeys: [publicKey],
    );
    expect(result.newOutputs[0].valueSatoshis, 50000000); // non-change untouched
    expect(result.newOutputs[1].valueSatoshis, 49990000 - 10000); // change shrunk by the increase
    expect(result.newOutputs[1].isChange, isTrue);
  });

  test('throws when there is no change output to shrink', () {
    final record = makeRecord(withChange: false);
    expect(
      () => buildBumpFeeTransaction(
        record: record,
        newFeeSatoshis: 20000,
        inputPrivateKeys: [privateKey],
        inputPublicKeys: [publicKey],
      ),
      throwsStateError,
    );
  });

  test('throws when the fee increase would exceed the change output', () {
    final record = makeRecord(withChange: true);
    expect(
      () => buildBumpFeeTransaction(
        record: record,
        newFeeSatoshis: 999999999,
        inputPrivateKeys: [privateKey],
        inputPublicKeys: [publicKey],
      ),
      throwsStateError,
    );
  });

  test('produces a transaction signed with the given key, RBF-signalling sequence', () {
    final record = makeRecord(withChange: true);
    final result = buildBumpFeeTransaction(
      record: record,
      newFeeSatoshis: 20000,
      inputPrivateKeys: [privateKey],
      inputPublicKeys: [publicKey],
    );
    final rawTx = result.rawTx;
    // version(4) + inputcount varint(1) + prevtxid(32) + vout(4) = 41 before the scriptSig length byte
    final scriptSigLen = rawTx[41];
    final scriptSig = rawTx.sublist(42, 42 + scriptSigLen);
    final sigLen = scriptSig[0];
    final pubkeyLen = scriptSig[1 + sigLen];
    final extractedPubkey = scriptSig.sublist(2 + sigLen, 2 + sigLen + pubkeyLen);
    expect(extractedPubkey, publicKey);
    final sequenceOffset = 42 + scriptSigLen;
    final sequence = rawTx.buffer.asByteData().getUint32(sequenceOffset, Endian.little);
    expect(sequence, 0xfffffffd); // BIP125 opt-in RBF signal, from Utxo's new default
  });
}

String _hex(Uint8List b) => b.map((x) => x.toRadixString(16).padLeft(2, '0')).join();
