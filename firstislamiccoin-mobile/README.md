# firstislamiccoin-mobile

FirstIslamicCoin (FIC) light wallet -- Android + iOS, one Flutter codebase.
Key generation/storage and transaction signing happen entirely on-device;
the app performs **no mining, staking, or background processing** (see
[`store/store-compliance.md`](store/store-compliance.md)). Forked from
CodexaCoin's `cac_wallet/` -- see [`docs/CHANGELOG-FIC.md`](../docs/CHANGELOG-FIC.md)
for every deviation from that source.

## Status

**`flutter analyze`/`flutter test` have not actually been run against
this code** -- see "Verification" below for exactly why (a real
environment constraint, not an oversight) and what stood in for them.
**Not published to either app store** -- no Play Console/App Store
Connect account, no signing keys, no privacy-policy URL. See
[`store/`](store/) for the draft listings and what's still `TODO-HUMAN`.

This wallet talks to a staking-service gateway
(`firstislamiccoin-staking-service/`, Phase 6) for balance/history/
broadcast/staking. **That service does not exist yet** -- see
[`docs/repo-map.md`](../docs/repo-map.md)'s "Two mapping caveats" and
[`docs/mobile-api.md`](docs/mobile-api.md) for the REST contract this
build is written against. Every screen that depends on it (send, receive
balance, history, staking, referrals, price alerts) will show real
network errors against `NetworkConfig`'s placeholder gateway hostnames
(see [`docs/dns.md`](../../docs/dns.md)) until that backend is deployed --
this is not a bug, it's the same "built ahead of its backend" situation
the explorer and website were in before Phases 8/9 deployed theirs.

## What's different from CodexaCoin's `cac_wallet/`

- **Chain parameters**: mainnet/testnet address version bytes, bech32 HRP
  (`fic`/`tfic`), and BIP44 coin type (9770, uniform across networks --
  see `lib/config/network_config.dart`) match `firstislamiccoin-core`'s
  actual chainparams, not CAC's.
- **No wrapped-token/DEX integration, anywhere.** CAC's wallet embedded a
  PancakeSwap external-link button and a WalletConnect-based swap screen
  for its BEP-20 token, and fetched a real (if thin) FIC/USD-equivalent
  price from that DEX pool plus a Stellar order book. FirstIslamicCoin
  has no wrapped token on any chain (`docs/CHANGELOG-FIC.md`'s
  Decision 3) -- both screens and the price-fetching service were removed
  rather than rebranded. `lib/widgets/fiat_placeholder.dart` shows an
  honest "unavailable" message instead of a fabricated number.
- **P2CS cold-staking**: does not exist in `firstislamiccoin-core`'s
  consensus layer at all (see `docs/mobile-api.md` §5's note). The
  staking screen only exposes the custodial pool flow CAC also has; the
  gateway client has no delegate/revoke methods.
- **Localization**: real `flutter gen-l10n` infrastructure plus English
  and Arabic strings for a representative sample of screens -- see
  [`docs/localization.md`](docs/localization.md) for exactly what's
  covered and what (Urdu, Bahasa, Malay, Turkish, and most screens'
  strings) is still open. CAC's wallet had no localization at all.
- **Package identity**: `com.firstislamiccoin.wallet` (was
  `com.codexacoin.cac_wallet`), Dart package `fic_wallet`.
- iOS `Info.plist` gained `NSCameraUsageDescription`/
  `NSFaceIDUsageDescription` -- missing from CAC's own `Info.plist`, and
  a real crash risk on first camera/biometric use without them, not a
  rebrand.

## Verification

No Flutter/Dart SDK exists on the Windows host this was built on, and
getting one running proved genuinely blocked: `docker pull` hangs
indefinitely for any image (Docker Hub/GHCR unreachable from this
sandbox), and a direct download of the official SDK tarball from
`storage.googleapis.com` (reachable, unlike Docker's registries) crawls
at ~150 KB/s against a 1.46 GB archive -- multiple hours, not run to
completion. See [`docs/CHANGELOG-FIC.md`](../docs/CHANGELOG-FIC.md)'s
Phase 5 section for the full account and what was done instead: a static
brace-balance/import-resolution check across every file, careful manual
re-reading of each edit, and live-testnet-verified (not invented) address
vectors in `test/crypto/address_test.dart`/`test/crypto/xpub_test.dart`.
`.github/workflows/ci.yml` runs the real `flutter analyze`/`flutter test`
on every push -- this gap is specific to the interactive environment this
phase was built in.

No Android SDK or Xcode toolchain exists in this development environment
either, so `flutter build apk`/`flutter build ios` were not run; see
`store/store-compliance.md`'s deliverables checklist for exactly what
that leaves unverified.

## Structure

```
lib/
  config/network_config.dart   -- chain parameters per network
  crypto/                      -- address encoding, BIP32/39 keys, tx
                                   building/signing, multisig, offline
                                   signing, message sign/verify
  models/wallet_models.dart    -- gateway response shapes
  services/                    -- gateway HTTP client, secure storage,
                                   BIP21, push notifications
  screens/                     -- one file per app screen
  l10n/                        -- ARB source strings + generated output
  widgets/fiat_placeholder.dart
  main.dart
test/
  crypto/                      -- unit tests, real testnet-verified
                                   vectors where a live node exists
  integration/                 -- gateway integration test, skipped
                                   without a real deployment
docs/
  mobile-api.md                -- the gateway REST contract this wallet
                                   is built against
  localization.md
store/
  store-compliance.md          -- App Store/Play policy notes
  privacy-policy.md            -- draft, not published
  android/, ios/               -- draft store listings
```

## Development

```bash
flutter pub get   # also runs the l10n codegen, via pubspec.yaml's generate: true
flutter analyze
flutter test
```
