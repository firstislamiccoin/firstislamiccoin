# FirstIslamicCoin (FIC)

A proof-of-stake Layer-1 cryptocurrency: a fixed 10 FIC block reward
(independent of stake amount or age), no coin-age weighting, no developer
tax, and a design shaped throughout by Islamic-finance questions — see
[`docs/shariah-compliance.md`](docs/shariah-compliance.md) for exactly what
that does and doesn't mean; **no Shariah board or scholar has reviewed or
endorsed FIC**, and nothing in this repository should be read as claiming
otherwise.

FIC is a fork of [CodexaCoin (CAC)](https://github.com/fakharnaqvi5313/codexacoin)
— kept at `codexacoin/` in this checkout as an unmodified, read-only
reference — which is itself a fork of Blackcoin More. Every deviation from
CAC, deliberate or discovered, is recorded in
[`docs/CHANGELOG-FIC.md`](docs/CHANGELOG-FIC.md). Nothing here is
fabricated: certifications, endorsements, and Shariah rulings that don't
exist yet are marked `TODO-HUMAN`, not invented.

## Status

**Mainnet has not launched.** Its genesis block still pays a placeholder,
provably-unspendable key pending a real key ceremony — see
[`docs/genesis.md`](docs/genesis.md) and
[`docs/LAUNCH-RUNBOOK.md`](docs/LAUNCH-RUNBOOK.md). Testnet is live and has
been used to verify every component below against real transactions, not
just code review.

## Repositories

A single monorepo, not the nine separate repositories the original build
prompt assumed — see
[`docs/repo-map.md`](docs/repo-map.md#adopted-structure) for why and the full
CAC-to-FIC directory mapping.

| Directory | What it is | Status |
|---|---|---|
| [`firstislamiccoin-core/`](firstislamiccoin-core/) | The node (`firstislamiccoind`), wallet, and consensus rules. Builds on Linux; mainnet genesis is a placeholder | Rebranded, fixed reward + PoS consensus changes verified on testnet |
| [`firstislamiccoin-electrumx/`](firstislamiccoin-electrumx/) | Light-client backend (ElectrumX fork) | Real block indexing verified end-to-end against a live node — further than CAC's own equivalent ever got |
| [`firstislamiccoin-mobile/`](firstislamiccoin-mobile/) | Android + iOS wallet (Flutter) | Builds and analyzes clean; **two pre-existing crypto tests currently fail** — see `docs/security-review.md` §6 before shipping |
| [`firstislamiccoin-web-wallet/`](firstislamiccoin-web-wallet/) | Browser wallet, plain JS, no build step | Deployed to testnet; a real fee-calculation bug (found via live testing) was fixed here and in mobile |
| [`firstislamiccoin-explorer/`](firstislamiccoin-explorer/) | Block explorer (Flask + static frontend) | Deployed, verified against live testnet |
| [`firstislamiccoin-staking-service/`](firstislamiccoin-staking-service/) | Custodial staking pool REST API. Non-custodial P2CS cold staking does **not** exist — it was a CAC design document, never built | Deployed, verified end-to-end on regtest with exact reward/fee math |
| [`firstislamiccoin-website/`](firstislamiccoin-website/) | firstislamiccoin.com, static HTML | Deployed |
| [`firstislamiccoin-infra/`](firstislamiccoin-infra/) | Deployment tooling: systemd units, `provision.sh` scripts, Docker/testnet compose | Testnet environment live; mainnet provisioning scripts are written, unrun |
| [`firstislamiccoin-brand/`](firstislamiccoin-brand/) | Brand kit — colors, logo, identity constants | Done (new in FIC; no CAC equivalent) |
| `codexacoin/` | Upstream CAC reference clone. Read-only, never edited | Kept so any FIC change can be diffed against what it replaced |

## Documentation map

- [`docs/genesis.md`](docs/genesis.md) — every network's genesis block, and why the premine is
  1,000 outputs instead of one.
- [`docs/tokenomics.md`](docs/tokenomics.md) — every constant that affects how much FIC exists.
- [`docs/CHANGELOG-FIC.md`](docs/CHANGELOG-FIC.md) — the full, phase-by-phase record of every
  deviation from CAC, every bug found, and every open `TODO-HUMAN` item.
- [`docs/security-review.md`](docs/security-review.md) — what was actually run (lint, cppcheck,
  CI, `pip-audit`, `flutter analyze`/`test`) and what it found.
- [`docs/LAUNCH-RUNBOOK.md`](docs/LAUNCH-RUNBOOK.md) — the genesis key ceremony, seed node
  bring-up order, and launch sequence, for a human to follow.
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — backups, upgrades, incident response, and how the
  (currently disabled) reward-halving schedule would be turned on.
- [`docs/shariah-compliance.md`](docs/shariah-compliance.md) — what "Shariah-conscious" means in
  this project's design, and what it explicitly does not claim.
- [`docs/dns.md`](docs/dns.md) — every DNS record mainnet needs, and which phase depends on it.
- [`docs/repo-map.md`](docs/repo-map.md) — the CAC monorepo → FIC directory mapping in full.

## Phase status

Against the original 11-phase build prompt:

| Phase | What | Status |
|---|---|---|
| 0 | Discovery and brand kit | Done |
| 1 | Core rebrand, chain parameters, fixed reward | Done |
| 2 | Testnet validation | Done — live testnet, real transactions |
| 3 | Desktop CI + release | `release.yml` written; never run (no GitHub org yet) |
| 4 | ElectrumX | Done — real indexing verified, exceeding CAC's own verification |
| 5 | Mobile wallets | Builds; store metadata written; **2 known-failing crypto tests** |
| 6 | Staking service (custodial) | Done — verified end-to-end; P2CS non-custodial staking not built (never was, in CAC either) |
| 7 | Web wallet | Done — deployed, a real send-blocking bug found and fixed via live testing |
| 8 | Block explorer | Done — deployed |
| 9 | Website | Done — deployed |
| 10 | Mainnet launch checklist and handover | This document, `docs/security-review.md`, `docs/LAUNCH-RUNBOOK.md`, and `docs/OPERATIONS.md` — the ceremony and the launch itself are not done |

Full detail behind every one of these rows is in `docs/CHANGELOG-FIC.md`.
