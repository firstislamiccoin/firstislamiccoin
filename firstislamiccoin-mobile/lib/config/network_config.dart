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

  /// BIP44 coin type for HD derivation (m/44'/coinType'/...). FIC uses
  /// 9770 on every network, mainnet included -- unlike most coins, which
  /// follow SLIP-44 convention and use testnet index 1, FIC's own testnet
  /// chainparams.cpp derivation comments use 9770 uniformly (see
  /// docs/CHANGELOG-FIC.md). Unregistered with SLIP-44 pre-launch, same
  /// status CAC's 3377 had -- see docs/cac-audit.md section 5 and
  /// docs/CHANGELOG-FIC.md's TODO-HUMAN table.
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
    bip44CoinType: 9770,
    gatewayBaseUrl: 'https://staking-api.testnet.firstislamiccoin.com/v1',
  );

  static NetworkConfig forNetwork(FicNetwork n) =>
      n == FicNetwork.mainnet ? mainnet : testnet;
}
