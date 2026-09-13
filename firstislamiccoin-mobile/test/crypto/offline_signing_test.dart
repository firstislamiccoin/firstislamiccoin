import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';

import 'package:fic_wallet/config/network_config.dart';
import 'package:fic_wallet/crypto/address.dart';
import 'package:fic_wallet/crypto/keys.dart';
import 'package:fic_wallet/crypto/offline_signing.dart';
import 'package:fic_wallet/crypto/transaction.dart' as tx;

// A fixed, well-formed 12-word test mnemonic -- never used for a real
// wallet, only here to derive deterministic keys for these tests.
const _testMnemonic =
    'abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about';

String _bytesToHex(List<int> b) => b.map((x) => x.toRadixString(16).padLeft(2, '0')).join();

void main() {
  const network = NetworkConfig.mainnet;

  group('OfflineSignRequest JSON round-trip', () {
    test('preserves every field through toJson/fromJson', () {
      final request = OfflineSignRequest(
        locktime: 0,
        inputs: [
          OfflineSignInput(
            txidHex: 'ab' * 32,
            vout: 1,
            valueSatoshis: 5000000,
            derivationIndex: 3,
            pubkeyHashHex: 'cd' * 20,
          ),
        ],
        outputs: [
          OfflineSignOutput(scriptPubKeyHex: '76a914${'ef' * 20}88ac', valueSatoshis: 4900000),
        ],
      );
      final roundTripped = OfflineSignRequest.fromJson(request.toJson());
      expect(roundTripped.locktime, 0);
      expect(roundTripped.inputs.single.txidHex, 'ab' * 32);
      expect(roundTripped.inputs.single.derivationIndex, 3);
      expect(roundTripped.outputs.single.valueSatoshis, 4900000);
    });

    test('rejects JSON that is not a FIC offline-signing request', () {
      expect(() => OfflineSignRequest.fromJson({'type': 'something_else'}), throwsFormatException);
    });
  });

  group('signOfflineTransaction', () {
    test('produces byte-identical output to signing directly with the key', () {
      const index = 2;
      final key = deriveKey(mnemonic: _testMnemonic, network: network, index: index);
      final pubkeyHash = hash160(key.publicKey);

      final txid = 'ab' * 32;
      const valueIn = 10000000;
      final destScript = tx.p2pkhScriptPubKey(hash160(key.publicKey)); // send-to-self, doesn't matter for this test
      const change = 9900000;

      // 1. Sign directly, the normal (hot-wallet) way.
      final directRawTx = tx.buildAndSignTransaction(
        inputs: [
          tx.Utxo(
            txid: Uint8List.fromList(_hexToBytesReversedForTest(txid)),
            vout: 0,
            valueSatoshis: valueIn,
            pubkeyHash: pubkeyHash,
            privateKey: key.privateKey,
            publicKeyCompressed: key.publicKey,
          ),
        ],
        outputs: [tx.TxOutputSpec(destScript, change)],
      );

      // 2. Sign the equivalent request via the offline-signing path.
      final request = OfflineSignRequest(
        locktime: 0,
        inputs: [
          OfflineSignInput(
            txidHex: txid,
            vout: 0,
            valueSatoshis: valueIn,
            derivationIndex: index,
            pubkeyHashHex: _bytesToHex(pubkeyHash),
          ),
        ],
        outputs: [OfflineSignOutput(scriptPubKeyHex: _bytesToHex(destScript), valueSatoshis: change)],
      );
      final offlineRawTx = signOfflineTransaction(request: request, mnemonic: _testMnemonic, network: network);

      // Signing is deterministic (RFC6979) -- these must match exactly.
      expect(_bytesToHex(offlineRawTx), _bytesToHex(directRawTx));
    });

    test('signs multiple inputs at different derivation indices', () {
      final key0 = deriveKey(mnemonic: _testMnemonic, network: network, index: 0);
      final key1 = deriveKey(mnemonic: _testMnemonic, network: network, index: 1);
      final destScript = tx.p2pkhScriptPubKey(hash160(key0.publicKey));

      final request = OfflineSignRequest(
        locktime: 0,
        inputs: [
          OfflineSignInput(
            txidHex: 'aa' * 32,
            vout: 0,
            valueSatoshis: 1000000,
            derivationIndex: 0,
            pubkeyHashHex: _bytesToHex(hash160(key0.publicKey)),
          ),
          OfflineSignInput(
            txidHex: 'bb' * 32,
            vout: 1,
            valueSatoshis: 2000000,
            derivationIndex: 1,
            pubkeyHashHex: _bytesToHex(hash160(key1.publicKey)),
          ),
        ],
        outputs: [OfflineSignOutput(scriptPubKeyHex: _bytesToHex(destScript), valueSatoshis: 2900000)],
      );

      final rawTx = signOfflineTransaction(request: request, mnemonic: _testMnemonic, network: network);
      expect(rawTx, isNotEmpty);
    });

    test('refuses to sign an input whose claimed pubkey hash is wrong', () {
      final key = deriveKey(mnemonic: _testMnemonic, network: network, index: 0);
      final wrongHash = List<int>.filled(20, 0xff);

      final request = OfflineSignRequest(
        locktime: 0,
        inputs: [
          OfflineSignInput(
            txidHex: 'ab' * 32,
            vout: 0,
            valueSatoshis: 1000000,
            derivationIndex: 0,
            pubkeyHashHex: _bytesToHex(wrongHash),
          ),
        ],
        outputs: [OfflineSignOutput(scriptPubKeyHex: _bytesToHex(tx.p2pkhScriptPubKey(hash160(key.publicKey))), valueSatoshis: 900000)],
      );

      expect(
        () => signOfflineTransaction(request: request, mnemonic: _testMnemonic, network: network),
        throwsA(isA<StateError>()),
      );
    });

    test('rejects a request with no inputs', () {
      const request = OfflineSignRequest(locktime: 0, inputs: [], outputs: []);
      expect(
        () => signOfflineTransaction(request: request, mnemonic: _testMnemonic, network: network),
        throwsA(isA<ArgumentError>()),
      );
    });
  });
}

List<int> _hexToBytesForTest(String hex) {
  final out = List<int>.filled(hex.length ~/ 2, 0);
  for (var i = 0; i < out.length; i++) {
    out[i] = int.parse(hex.substring(i * 2, i * 2 + 2), radix: 16);
  }
  return out;
}

List<int> _hexToBytesReversedForTest(String hex) => _hexToBytesForTest(hex).reversed.toList();
