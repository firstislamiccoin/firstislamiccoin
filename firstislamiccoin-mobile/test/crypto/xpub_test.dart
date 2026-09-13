// xpub.dart's public (non-hardened) child derivation must produce the
// exact same addresses as the wallet's own private-key derivation path
// -- that's the entire point of watch-only-via-xpub, so these tests
// check real address equality, not just "it doesn't throw".
import 'package:fic_wallet/config/network_config.dart';
import 'package:fic_wallet/crypto/address.dart';
import 'package:fic_wallet/crypto/keys.dart';
import 'package:fic_wallet/crypto/xpub.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  const testMnemonic =
      'abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about';

  test('address derived via xpub matches the same index derived from the private key', () {
    final xpub = deriveAccountXpub(mnemonic: testMnemonic, network: NetworkConfig.mainnet);
    for (var index = 0; index < 3; index++) {
      final viaXpub = deriveXpubAddress(xpub: xpub, network: NetworkConfig.mainnet, index: index);
      final directKey = deriveKey(mnemonic: testMnemonic, network: NetworkConfig.mainnet, index: index);
      final directAddress = p2pkhAddress(hash160(directKey.publicKey), NetworkConfig.mainnet);
      expect(viaXpub, directAddress);
    }
  });

  test('importing a mainnet xpub while asking for testnet fails closed', () {
    final xpub = deriveAccountXpub(mnemonic: testMnemonic, network: NetworkConfig.mainnet);
    expect(
      () => deriveXpubAddress(xpub: xpub, network: NetworkConfig.testnet, index: 0),
      throwsArgumentError,
    );
  });

  // CAC had a golden vector here captured live from web-wallet/crypto.js,
  // cross-checking two independently hand-configured BIP32 version-byte
  // setups against each other. FIC has no web-wallet yet (Phase 7 --
  // see docs/repo-map.md) to capture an equivalent vector from, and its
  // own BIP44 coin type (9770 -- see network_config.dart) differs from
  // CAC's, so CAC's vector wouldn't match here even if it existed.
  // Until a second FIC implementation exists to cross-check against, the
  // two tests above are this file's coverage: internal xpub/private-key
  // consistency, and network-mismatch fail-closed behavior. Add a real
  // cross-platform vector here once web-wallet/crypto.js exists for FIC.
}
