# App Store Connect listing (draft)

**Status: draft copy only. Not submitted to App Store Connect -- there is
no Apple Developer Program account, no signing certificate/provisioning
profile, and no privacy-policy URL yet (see `../privacy-policy.md` and
`../../docs/CHANGELOG-FIC.md`'s TODO-HUMAN table). This file is what a
human would paste into App Store Connect's listing form once those
exist.**

## App name

FirstIslamicCoin Wallet

## Subtitle (max 30 characters)

```
Self-custody FIC wallet
```
(23 characters)

## Promotional text (max 170 characters)

```
Your keys, your FIC. Generated and stored only on your device. No
mining, no on-device staking, no background activity of any kind.
```

## Description

Same content as `../android/listing.md`'s full description -- App
Store's description field has no character limit worth truncating for,
so reuse it verbatim rather than maintaining two copies that could drift.

## Keywords (max 100 characters, comma-separated)

```
fic,firstislamiccoin,wallet,crypto,bitcoin,multisig,cold storage,self custody
```

## Category

Primary: Finance
Secondary: Utilities

## App Privacy (App Store Connect's privacy questionnaire)

Draw directly from `../privacy-policy.md` when filling in App Store
Connect's "App Privacy" section -- specifically: this app collects
Contact Info (email, name, DOB) and Financial Info (the wallet address
and, for staking sign-up, an ID number) only when the user opts into the
staking-pool account flow, and none of it is used for tracking or linked
to advertising. `TODO-HUMAN`: this questionnaire has legal weight
(Apple can reject or later flag the app for a mismatch) -- have someone
who has read the actual shipped code fill it in, not assumptions.

## Age rating

`TODO-HUMAN`: run Apple's actual age-rating questionnaire once ready to
submit; likely 17+ given the "Unrestricted Web Access" / financial-
services categories, but this is Apple's own determination to make via
their form, not something to pre-fill here.

## App Review notes

```
This is a self-custody cryptocurrency light wallet. It generates and
stores keys entirely on-device (see 3.1.5(b) compliance notes in
store-compliance.md, included in this repository) and never mines or
stakes on-device. The Staking, Referrals, and Price Alerts screens call
a backend service that is not deployed yet -- reviewers will see clear
in-app messaging on those screens rather than a broken/blank state.
A testnet mode is available in Settings for review without requiring
real funds.
```

## Screenshots

None captured yet -- needs a macOS/Xcode build, which this development
environment does not have. `TODO-HUMAN`.
