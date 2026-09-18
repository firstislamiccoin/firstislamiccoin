/// FirstIslamicCoin network parameters. Values taken directly from
/// `firstislamiccoin-core/src/kernel/chainparams.cpp` -- do not hand-edit
/// these without updating that file too, it's the single source of truth.
/// See ../../../docs/genesis.md and ../../../docs/CHANGELOG-FIC.md for
/// where each value comes from.
library;

enum FicNetwork { mainnet, testnet }

class NetworkConfig {
  final FicNetwork network;
  final String name;

  /// Base58Check version byte for P2PKH addresses.
  final int p2pkhVersion;

  /// Base58Check version byte for P2SH addresses.
  final int p2shVersion;

  /// Base58Check version byte for WIF-encoded private keys.
  final int wifVersion;

  /// bech32 human-readable part for P2WPKH/P2WSH/P2TR addresses.
  final String bech32Hrp;

  /// BIP44 coin type for HD derivation (m/44'/coinType'/...).
  ///
  /// This does NOT match on mainnet vs. testnet, despite what an earlier
  /// version of this comment (and docs/CHANGELOG-FIC.md's Phase 5 section)
  /// claimed. The actual, single-source-of-truth behaviour is in
  /// firstislamiccoin-core/src/wallet/scriptpubkeyman.cpp:
  ///
  ///   // Mainnet derives at 0', testnet and regtest derive at 1'
  ///   if (Params().IsTestChain()) {
  ///       desc_prefix += "/1h";
  ///   } else {
  ///       // FirstIslamicCoin: BIP44 coin type 9770. Not yet registered...
  ///       desc_prefix += "/9770h";
  ///   }
  ///
  /// i.e. only mainnet uses the FIC-specific, unregistered 9770 value;
  /// testnet (and regtest) keep the standard, SLIP-44-shared testnet index
  /// `1` -- exactly the same mainnet-differs/testnet-and-regtest-share
  /// pattern as every other chain parameter in this file (P2PKH/P2SH/WIF
  /// version bytes, bech32 HRP). Using 9770 for testnet here as well (the
  /// bug this comment used to describe as intentional) made this wallet
  /// derive testnet keys/addresses that don't match what a real FIC
  /// testnet node wallet restoring the same mnemonic would derive --
  /// confirmed by test/crypto/keys_test.dart's "mainnet and testnet coin
  /// types derive different keys" failing an inequality assertion (they
  /// came out equal) until this was fixed. Mainnet's 9770 is unregistered
  /// with SLIP-44 pre-launch, same status CAC's 3377 had -- see
  /// docs/cac-audit.md section 5 and docs/CHANGELOG-FIC.md's TODO-HUMAN
  /// table.
  final int bip44CoinType;

  /// Staking-service gateway API base URL (Phase 6 -- not built for FIC
  /// yet, see docs/repo-map.md's "Two mapping caveats"). Both networks
  /// point at a hostname that resolves to nothing today; see
  /// ../../../docs/dns.md. Kept as a real (not `localhost`) URL so the
  /// app's error handling for "gateway unreachable" is exercised
  /// truthfully rather than masked by a loopback address that only works
  /// on a dev machine.
  final String gatewayBaseUrl;

  const NetworkConfig._({
    required this.network,
    required this.name,
    required this.p2pkhVersion,
    required this.p2shVersion,
    required this.wifVersion,
    required this.bech32Hrp,
    required this.bip44CoinType,
    required this.gatewayBaseUrl,
  });

  static const mainnet = NetworkConfig._(
    network: FicNetwork.mainnet,
    name: 'FirstIslamicCoin Mainnet',
    p2pkhVersion: 36, // 0x24 -> 'F...' addresses
    p2shVersion: 28, // 0x1c -> 'C...' addresses
    wifVersion: 164, // 0xa4
    bech32Hrp: 'fic',
    bip44CoinType: 9770,
    gatewayBaseUrl: 'https://staking-api.firstislamiccoin.com/v1',
  );

  static const testnet = NetworkConfig._(
    network: FicNetwork.testnet,
    name: 'FirstIslamicCoin Testnet',
    p2pkhVersion: 111, // 0x6f -- inherited Bitcoin-standard testnet value
    p2shVersion: 196, // 0xc4
    wifVersion: 239, // 0xef
    bech32Hrp: 'tfic',
    bip44CoinType: 1, // standard SLIP-44 shared testnet index, matching
    // scriptpubkeyman.cpp's IsTestChain() branch -- see the field doc above.
    gatewayBaseUrl: 'https://staking-api.testnet.firstislamiccoin.com/v1',
  );

  static NetworkConfig forNetwork(FicNetwork n) =>
      n == FicNetwork.mainnet ? mainnet : testnet;
}
