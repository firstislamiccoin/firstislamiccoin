# App Store / Google Play compliance -- FirstIslamicCoin mobile wallet

Phase 5 deliverable, carried over from CAC's `docs/store-compliance.md`
almost unchanged -- the constraint driving this app's architecture is a
platform-policy fact about mining/staking apps, not anything specific to
either coin. Summarizes the specific policy constraints that shaped the
mobile app's architecture, and confirms the hard requirement the whole
design hinges on: **zero on-device mining, staking, or background
processing, on either platform.**

## The constraint that drives everything else

Apple App Store Review Guideline 3.1.5(b) ("Virtual Currencies") permits
apps to facilitate transmission of approved virtual currency in
compliant, lawful ways, but bars an app from mining cryptocurrency using
its own on-device mechanism -- mining is only allowed if it happens off
device (e.g. via cloud-based mining), quoting the guideline's own phrase
for that exception: *"performed off device"*.

Google Play's Financial Services / Cryptocurrency policy is less
prescriptive in exact wording but enforces the same practical constraint
via its Device and Network Abuse policy (prohibiting apps that run
persistent background compute, drain battery, or mine cryptocurrency on
the user's hardware without clear, foreground-only consent) and its
general stance that mining apps are restricted from Google Play outright.

**FirstIslamicCoin's design response, stated once here and enforced
everywhere else in this codebase**: the mobile apps are pure **light
wallets**. They generate/store keys, sign transactions, and display
balances/history. They never mine, never stake, and never run any
continuous or background-scheduled computation. All staking happens on
the staking-service gateway (Phase 6 -- not built yet, see
`../../docs/repo-map.md`). This is not a workaround to slip past review;
it's a straightforwardly compliant architecture, and it happens to also
be strictly better for users (no battery drain, no background
permissions, no continuous connectivity requirement, no missed rewards
from forgetting to keep the app open).

## What "zero on-device staking" actually means in the code

Concretely, and checkably:

- No `WorkManager` (Android) / `BGTaskScheduler` (iOS) registrations, no
  background isolates, no scheduled/periodic tasks of any kind in this
  Flutter project (`firstislamiccoin-mobile/`).
- No proof-of-work or proof-of-stake kernel-search logic exists anywhere
  in the Dart source. The staking screen (`lib/screens/staking_screen.dart`)
  is **read-only display + remote API calls** -- every action it exposes
  (view status, deposit, withdraw) is an HTTP call to the gateway service
  specified in `../docs/mobile-api.md`, never local computation. Search
  the codebase yourself:
  `grep -ri "mine\|kernel\|proof.of.work\|proof.of.stake" lib/`
  should turn up nothing except this compliance boundary being described
  in comments/docs.
- Signing (the one thing that *does* happen on-device, necessarily -- see
  below) is a single bounded cryptographic operation per user-initiated
  send, not a continuous process. It does not run when the app is
  backgrounded or closed.

## Key handling (Apple/Google security expectations, not just policy)

Both platforms increasingly expect -- and reviewers do check for --
proper use of platform key storage rather than app-managed files:

- **iOS**: keys stored via `flutter_secure_storage`, which uses the
  Keychain with `kSecAttrAccessibleWhenUnlockedThisDeviceOnly` (device-only,
  never iCloud Keychain synced -- a wallet seed must never leave the
  device via any sync mechanism). Where the device supports it, the
  Secure Enclave backs the Keychain item.
- **Android**: same package, backed by the Android Keystore system
  (hardware-backed on devices that support StrongBox).
- Signing happens **entirely on-device**, in the Flutter/Dart process.
  Only the final signed transaction hex is ever sent over the network
  (to the gateway's `/v1/tx/broadcast`, see `../docs/mobile-api.md`) --
  private keys and unsigned transaction data never leave the device.
- Biometric app-lock (`local_auth`) gates *app access*, not signing itself
  -- a deliberate simplification for this phase; a future hardening pass
  could additionally require biometric confirmation per-transaction, not
  just per-session.

## Offline-first behavior and its UI-copy implication

Keys, cached balances, cached history, and the receive-QR all work with
no network at all. Network access is needed only to *sync* balances/
rewards and to *broadcast* a transaction. This has a specific, deliberate
UI-copy consequence enforced in this app: staking reward copy says
**"rewards accrue automatically -- no need to keep the app open or
online"**, never "works without internet" -- the app genuinely needs a
network sync to *show* an updated balance or to *send* anything; what it
doesn't need is to be open or running for rewards to accrue server-side.

## Fiat value, BIP39, QR, testnet/mainnet switch

- Fiat value is an explicit, honest **placeholder** --
  `lib/widgets/fiat_placeholder.dart` never fetches or shows a number,
  because no exchange listing exists for FIC (see that file's own
  comment and `../../docs/CHANGELOG-FIC.md`'s Decision 3: unlike CAC,
  this project deliberately has no wrapped-token DEX listing to source a
  price from at all, not even a thin one).
- BIP39 mnemonic (12-word) seed creation/restore, standard derivation path
  (`m/44'/9770'/0'/0/n` -- see `lib/config/network_config.dart`, still
  pending SLIP-44 registration per `../../docs/CHANGELOG-FIC.md`'s
  TODO-HUMAN table).
- QR: generate for receive (`qr_flutter`), scan for send (`mobile_scanner`).
- Testnet/mainnet switch is a settings toggle that changes which chain
  parameters (address prefixes, gateway endpoint) the app uses -- see
  `lib/config/network_config.dart`. Switching networks does **not** reuse
  the same keys across networks silently without the user understanding
  that; the app clearly labels which network is active at all times.

## What was dropped from CAC, and why it doesn't affect this document

CAC's mobile wallet also shipped a PancakeSwap "buy/sell" external link
and a WalletConnect-based swap screen (`wallet_connect_swap_screen.dart`,
`services/pancake_swap.dart`), both connecting to BNB Chain DEX
infrastructure for its wrapped BEP-20 token. FirstIslamicCoin has no
wrapped-token/DEX component in its build (`../../docs/CHANGELOG-FIC.md`'s
Decision 3, `../../docs/repo-map.md`'s "Components with no FIC target"),
so both were removed rather than rebranded -- there is no FIC token on any
chain for either to point at. This has no compliance implication either
way (neither Apple's nor Google's cryptocurrency policy language turns on
whether a wallet also embeds a DEX swap flow); it's a product-scope
decision, noted here only because store metadata/screenshots must not
reference either removed feature.

## Deliverables checklist (this phase)

- [x] Flutter project (`firstislamiccoin-mobile/`) targeting both iOS and
      Android from one codebase.
- [x] BIP39 seed creation/restore, key derivation.
- [x] Send/receive with QR, transaction history (via the Phase 6 gateway
      API contract), fiat-value honest placeholder, biometric app lock,
      testnet/mainnet switch.
- [x] Staking screen: status, accrued rewards; deposit/withdraw actions
      call a gateway that doesn't exist yet (Phase 6) -- all via remote
      API calls only, nothing computed on-device.
- [~] Unit tests for key derivation/signing written (see `test/crypto/`), with real testnet-node-
      verified address vectors -- but not actually run against a Dart compiler this phase; see
      `../docs/CHANGELOG-FIC.md`'s Phase 5 "Verification" section for why.
- [ ] Integration test against a real testnet gateway + Electrum backend
      -- stubbed this phase (`test/integration/gateway_integration_test.dart`
      is `skip`ped without a real deployment; neither the gateway nor
      ElectrumX exists for FIC yet).
- [ ] Android APK/AAB actually built and installed on a device/emulator --
      see `../docs/CHANGELOG-FIC.md`'s Phase 5 section for exactly what
      was and wasn't verified locally this phase.
- [ ] iOS Xcode project actually built for the Simulator -- no macOS/Xcode
      toolchain in this development environment (Windows host); the iOS
      platform project is written but unbuilt, same category of gap as
      CAC's own iOS build status.
