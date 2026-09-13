# FirstIslamicCoin Wallet -- Privacy Policy (draft)

**Status: draft, not published anywhere. `TODO-HUMAN`: needs legal review
and a real publication URL (both Apple and Google require a live,
publicly reachable privacy-policy URL in store listings) before this app
can actually be submitted -- see `../../docs/CHANGELOG-FIC.md`'s
TODO-HUMAN table. Nothing below has been reviewed by a lawyer.**

## What this app stores on your device

- Your 12-word recovery phrase (BIP39 mnemonic), encrypted at rest via
  the operating system's own secure storage (iOS Keychain, device-only,
  never iCloud-synced; Android Keystore, hardware-backed where
  available). See `store-compliance.md` for the technical detail.
- Non-secret bookkeeping: which addresses you've generated, your local
  address book and watch list, your local record of transactions you've
  sent (used only to support "bump fee"), and your chosen theme/network.

None of this data leaves your device except as described below.

## What this app sends over the network, and to whom

- **Balance, transaction history, and broadcasting a signed transaction**:
  sent to the staking-service gateway (see `../docs/mobile-api.md`) --
  not built or deployed yet (Phase 6). Once it exists, this traffic goes
  to a server operated by this project, not a third party.
- **Push notifications** (optional, off by default): if you enable
  "notify me on incoming payment" or a price alert, your device's FCM
  token is registered with the same gateway, keyed to the address you
  asked to be notified about. Delivery itself goes through Google's
  Firebase Cloud Messaging (and, for iOS, Apple's APNs via FCM's
  bridging) -- both third-party infrastructure, receiving only a device
  token and an address, never your recovery phrase or private keys.
- **Staking sign-up** (optional): if you create a staking-pool account,
  the email/password/full name/date of birth/ID type/ID number you enter
  are sent to the same gateway. This is self-attested information, not
  identity-verified by this app -- see `../docs/mobile-api.md` and
  whatever the eventual Phase 6 service's own data-handling documentation
  says once it exists. The ID number is meant to be encrypted before
  storage server-side; this app cannot itself guarantee that, since it
  doesn't control the server.
- **Nothing else**. This app makes no analytics, crash-reporting, or
  advertising network calls, and embeds no third-party SDK beyond
  Firebase Cloud Messaging (used only for the push notifications above).

## What this app never does

- Never sends your recovery phrase, private keys, or unsigned transaction
  data anywhere, under any circumstance.
- Never mines or stakes on your device, and never runs any background or
  scheduled computation -- see `store-compliance.md`.
- Never shares data with advertisers or data brokers.

## Your controls

- Push notifications: off by default, and can be left off entirely --
  every core wallet feature (send, receive, view balance/history) works
  without ever enabling them.
- Staking-pool sign-up: entirely optional and separate from the wallet
  itself -- the on-chain wallet (create/restore/send/receive) needs no
  account of any kind.
- Wiping the wallet (Settings -> Wipe wallet) deletes the recovery phrase
  and all local bookkeeping from this device immediately and
  irreversibly, per `store-compliance.md`'s note on that being a
  deliberate, explicitly-confirmed action.

## Contact

`TODO-HUMAN`: this needs a real contact address/method once the project
has one to publish (see `../../docs/dns.md` for the domain's own
not-yet-live status).
