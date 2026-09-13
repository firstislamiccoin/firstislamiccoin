// Structural tests for BIP39/BIP32 key derivation. Deliberately does not
// hardcode a specific mnemonic -> key golden vector (bip39/bip32 are
// well-tested upstream packages; what's worth testing here is that this
// wallet's own derivation path logic -- coin type selection, determinism,
// index/network separation -- behaves as PARAMETERS.md section 2 and
// crypto/keys.dart's derivation-path comment describe).
import 'package:fic_wallet/config/network_config.dart';
import 'package:fic_wallet/crypto/keys.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  const testMnemonic =
      'abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about';

  test('generateMnemonic produces a valid 12-word mnemonic', () {
    final mnemonic = generateMnemonic();
    expect(mnemonic.split(' ').length, 12);
    expect(isValidMnemonic(mnemonic), isTrue);
  });

  test('generateMnemonic is not deterministic across calls', () {
    expect(generateMnemonic(), isNot(equals(generateMnemonic())));
  });

  test('isValidMnemonic accepts a well-known valid test vector', () {
    expect(isValidMnemonic(testMnemonic), isTrue);
  });

  test('isValidMnemonic rejects a bad checksum', () {
    expect(isValidMnemonic('abandon abandon abandon abandon abandon abandon '
        'abandon abandon abandon abandon abandon abandon'), isFalse);
  });

  test('isValidMnemonic rejects nonsense input', () {
    expect(isValidMnemonic('not a mnemonic at all'), isFalse);
  });

  test('derivation is deterministic for the same mnemonic/network/index', () {
    final a = deriveKey(mnemonic: testMnemonic, network: NetworkConfig.mainnet, index: 0);
    final b = deriveKey(mnemonic: testMnemonic, network: NetworkConfig.mainnet, index: 0);
    expect(a.privateKey, b.privateKey);
    expect(a.publicKey, b.publicKey);
  });

  test('different indexes derive different keys', () {
    final a = deriveKey(mnemonic: testMnemonic, network: NetworkConfig.mainnet, index: 0);
    final b = deriveKey(mnemonic: testMnemonic, network: NetworkConfig.mainnet, index: 1);
    expect(a.privateKey, isNot(equals(b.privateKey)));
  });

  test('mainnet and testnet coin types derive different keys', () {
    final a = deriveKey(mnemonic: testMnemonic, network: NetworkConfig.mainnet, index: 0);
    final b = deriveKey(mnemonic: testMnemonic, network: NetworkConfig.testnet, index: 0);
    expect(a.privateKey, isNot(equals(b.privateKey)));
  });

  test('external and change chains derive different keys', () {
    final a = deriveKey(mnemonic: testMnemonic, network: NetworkConfig.mainnet, index: 0);
    final b = deriveKey(mnemonic: testMnemonic, network: NetworkConfig.mainnet, index: 0, change: true);
    expect(a.privateKey, isNot(equals(b.privateKey)));
  });

  test('private key is 32 bytes and public key is 33 bytes (compressed)', () {
    final key = deriveKey(mnemonic: testMnemonic, network: NetworkConfig.mainnet, index: 0);
    expect(key.privateKey.length, 32);
    expect(key.publicKey.length, 33);
    expect(key.publicKey[0] == 0x02 || key.publicKey[0] == 0x03, isTrue);
  });
}
