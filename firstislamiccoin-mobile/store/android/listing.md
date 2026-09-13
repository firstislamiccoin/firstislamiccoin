# Google Play Store listing (draft)

**Status: draft copy only. Not submitted to Google Play -- there is no
Google Play Console account, no signing keystore, and no privacy-policy
URL yet (see `../privacy-policy.md` and `../../docs/CHANGELOG-FIC.md`'s
TODO-HUMAN table). This file is what a human would paste into the Play
Console's listing form once those exist.**

## App name

FirstIslamicCoin Wallet

## Short description (max 80 characters)

```
Self-custody FIC wallet. Your keys, your coins. No mining, no staking here.
```
(76 characters)

## Full description (max 4000 characters)

```
FirstIslamicCoin Wallet is a self-custody light wallet for FIC. Your
recovery phrase and private keys are generated and stored only on your
device -- this app never holds your funds and never sends your keys
anywhere.

FEATURES
- Create a new wallet or restore from a 12-word recovery phrase
- Send and receive FIC, with QR codes for both
- Multiple addresses per wallet, plus a local address book
- Transaction history with CSV export
- N-of-M multisig: create shared addresses, propose spends, collect
  cosigner signatures, and broadcast
- Watch-only mode: monitor any address's balance, or an entire account
  via its extended public key (xpub), without ever holding its keys
- Air-gapped signing: build a send request on one device, sign it on a
  second device kept offline, then broadcast -- no seed phrase ever
  touches an internet-connected device
- Sign and verify messages to prove control of an address
- Biometric app lock (Face ID / fingerprint)
- Testnet support, clearly labeled, for trying the app before using real
  funds

WHAT THIS APP DOES NOT DO
- No mining, no on-device staking, no background processes of any kind.
  Staking happens through a separate service this app talks to over the
  network -- see the in-app Staking screen for details on what is and
  isn't available yet.
- No price feed and no exchange/swap integration. FIC does not trade on
  any exchange today; this app will never show a fabricated price.

This app is under active development. Some screens (staking, referrals,
price alerts) describe features whose backend service is not deployed
yet and will say so plainly rather than pretend to work.
```

## Category

Finance

## Content rating questionnaire notes

- Simulated gambling: no.
- Real-money gambling/staking: the in-app staking flow, once its backend
  exists, deposits/withdraws the user's own already-owned FIC to/from a
  pool the user opts into -- not gambling, and not a feature this app can
  actually exercise yet (see above). `TODO-HUMAN`: confirm Google's
  Financial Services declaration requirements once Phase 6 is live and
  this is a real, working feature, not a stub.

## Data safety section

Draw directly from `../privacy-policy.md` when filling in Play Console's
Data Safety form -- do not answer it from assumptions; every data type
declared there must match what the shipped build actually does.

## Screenshots / graphics

None captured yet -- needs a real device/emulator build.
`TODO-HUMAN`.
