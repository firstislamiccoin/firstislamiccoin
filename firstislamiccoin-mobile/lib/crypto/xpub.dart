/// Account-level extended public key ("xpub") export/import for
/// watch-only monitoring -- lets someone else (or this same wallet
/// restored on another device, without its private key) derive and
/// watch this wallet's addresses' balances. Mirrors web-wallet/
/// crypto.js's deriveAccountXpub/deriveXpubAddress exactly: same
/// account-level derivation path, same conventional BIP32 version
/// bytes used purely as a serialization container -- not a claim of
/// interop with generic Bitcoin tooling, since FIC's own address
/// version bytes (not Bitcoin's) are what actually get applied when
/// addresses are derived from one of these xpubs.
library;

import 'package:bip32/bip32.dart' as bip32;
import 'package:bip39/bip39.dart' as bip39;

import '../config/network_config.dart';
import 'address.dart' show hash160, p2pkhAddress;

final bip32.NetworkType _mainnetBip32 = bip32.NetworkType(
  wif: 0x80,
  bip32: bip32.Bip32Type(public: 0x0488b21e, private: 0x0488ade4),
);
final bip32.NetworkType _testnetBip32 = bip32.NetworkType(
  wif: 0xef,
  bip32: bip32.Bip32Type(public: 0x043587cf, private: 0x04358394),
);

bip32.NetworkType _bip32NetworkFor(NetworkConfig network) =>
    network.network == FicNetwork.testnet ? _testnetBip32 : _mainnetBip32;

/// Derives and serializes this wallet's account xpub, at
/// m/44'/coinType'/0' -- the standard BIP44 "account" depth, one level
/// above the external/change chains.
String deriveAccountXpub({
  required String mnemonic,
  required NetworkConfig network,
  String passphrase = '',
}) {
  final seed = bip39.mnemonicToSeed(mnemonic, passphrase: passphrase);
  final root = bip32.BIP32.fromSeed(seed, _bip32NetworkFor(network));
  final account = root.derivePath("m/44'/${network.bip44CoinType}'/0'");
  return account.neutered().toBase58();
}

/// Derives external-chain address #[index] from an imported account
/// xpub, via BIP32 public (non-hardened) child derivation -- no private
/// key involved anywhere in this call. Throws [ArgumentError] if [xpub]
/// doesn't decode for [network] (e.g. a testnet xpub imported while on
/// mainnet -- the version bytes won't match) or is otherwise malformed.
/// Like this wallet's existing multi-address support, this derives a
/// fixed, caller-chosen count of addresses rather than scanning for a
/// gap limit -- said explicitly in the UI.
String deriveXpubAddress({
  required String xpub,
  required NetworkConfig network,
  required int index,
}) {
  final node = bip32.BIP32.fromBase58(xpub, _bip32NetworkFor(network));
  final child = node.derivePath('0/$index');
  return p2pkhAddress(hash160(child.publicKey), network);
}
