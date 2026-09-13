// message.dart hand-rolls ECDSA public-key recovery (pointycastle has no
// built-in support for it, unlike the web side's @noble/secp256k1) --
// this is the highest-risk new code in this batch, so these tests check
// actual sign->verify round trips against real derived keys, not just
// that the functions don't throw.
import 'package:fic_wallet/config/network_config.dart';
import 'package:fic_wallet/crypto/address.dart';
import 'package:fic_wallet/crypto/keys.dart';
import 'package:fic_wallet/crypto/message.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  const testMnemonic =
      'abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about';

  test('sign then verify round-trips true for the signing address', () {
    for (var index = 0; index < 5; index++) {
      final key = deriveKey(mnemonic: testMnemonic, network: NetworkConfig.mainnet, index: index);
      final address = p2pkhAddress(hash160(key.publicKey), NetworkConfig.mainnet);
      final sig = signMessage(key.privateKey, key.publicKey, 'hello FirstIslamicCoin #$index');
      expect(verifyMessage(address, sig, 'hello FirstIslamicCoin #$index', NetworkConfig.mainnet), isTrue);
    }
  });

  test('verify fails for a different message', () {
    final key = deriveKey(mnemonic: testMnemonic, network: NetworkConfig.mainnet, index: 0);
    final address = p2pkhAddress(hash160(key.publicKey), NetworkConfig.mainnet);
    final sig = signMessage(key.privateKey, key.publicKey, 'original message');
    expect(verifyMessage(address, sig, 'tampered message', NetworkConfig.mainnet), isFalse);
  });

  test('verify fails for a different address', () {
    final key0 = deriveKey(mnemonic: testMnemonic, network: NetworkConfig.mainnet, index: 0);
    final key1 = deriveKey(mnemonic: testMnemonic, network: NetworkConfig.mainnet, index: 1);
    final address1 = p2pkhAddress(hash160(key1.publicKey), NetworkConfig.mainnet);
    final sig = signMessage(key0.privateKey, key0.publicKey, 'hello');
    expect(verifyMessage(address1, sig, 'hello', NetworkConfig.mainnet), isFalse);
  });

  test('verify throws on a malformed (non-base64) signature', () {
    final key = deriveKey(mnemonic: testMnemonic, network: NetworkConfig.mainnet, index: 0);
    final address = p2pkhAddress(hash160(key.publicKey), NetworkConfig.mainnet);
    expect(
      () => verifyMessage(address, 'not-base64!!', 'hello', NetworkConfig.mainnet),
      throwsFormatException,
    );
  });

  test('verify throws for a non-P2PKH (P2SH) address', () {
    final key = deriveKey(mnemonic: testMnemonic, network: NetworkConfig.mainnet, index: 0);
    // Any well-formed P2SH address is enough -- verification should reject
    // it before ever looking at the signature.
    final p2shAddr = p2shAddress(hash160(key.publicKey), NetworkConfig.mainnet);
    final sig = signMessage(key.privateKey, key.publicKey, 'hello');
    expect(
      () => verifyMessage(p2shAddr, sig, 'hello', NetworkConfig.mainnet),
      throwsFormatException,
    );
  });

  test('signature is a 65-byte compact signature, base64-encoded', () {
    final key = deriveKey(mnemonic: testMnemonic, network: NetworkConfig.mainnet, index: 0);
    final sig = signMessage(key.privateKey, key.publicKey, 'hello');
    final decoded = Uri.parse('data:;base64,$sig').data!.contentAsBytes();
    expect(decoded.length, 65);
    expect(decoded[0], inInclusiveRange(31, 34)); // 27 + recid(0-3) + 4 (compressed)
  });

  // CAC had a golden vector here captured live from web-wallet/message.js,
  // cross-checking this hand-rolled recovery (pointycastle has no
  // built-in support, unlike @noble/secp256k1 on the web side) against an
  // independent implementation. FIC has no web-wallet yet (Phase 7 --
  // see docs/repo-map.md) to capture an equivalent vector from, and the
  // message magic changed ("FirstIslamicCoin Signed Message:\n", see
  // message.dart), so CAC's own vector can't be reused either. Until a
  // second FIC implementation exists to cross-check against, the
  // round-trip tests above are this file's only coverage -- add a real
  // cross-platform vector here once web-wallet/message.js exists for FIC.
}
