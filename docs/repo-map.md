# Repository map — CodexaCoin monorepo → FirstIslamicCoin layout

The FIC prompt's target layout assumes nine sibling repositories. CodexaCoin is a
**single monorepo**. Per the prompt's own instruction ("If CodexaCoin's
repositories are structured differently, mirror CAC's structure and record the
mapping here"), FIC mirrors the monorepo shape and this file is the mapping.

## Adopted structure

A single `firstislamiccoin/` monorepo, with directories named after the prompt's
target repositories so the phase instructions still read correctly:

```
First Islamic Coin/
├── codexacoin/                       # upstream reference clone, read-only, never edited
├── docs/                             # FIC-level docs (this file, cac-audit.md, CHANGELOG-FIC.md, …)
├── firstislamiccoin-brand/           # brand kit  ← done, Phase 0
├── firstislamiccoin-core/            # ← codexacoin/codexacoin-core
├── firstislamiccoin-electrumx/       # ← codexacoin/electrumx-cac
├── firstislamiccoin-mobile/          # ← codexacoin/cac_wallet
├── firstislamiccoin-web-wallet/      # ← codexacoin/web-wallet
├── firstislamiccoin-explorer/        # ← codexacoin/explorer
├── firstislamiccoin-staking-service/ # ← codexacoin/vps-gateway
├── firstislamiccoin-website/         # ← codexacoin/website
└── firstislamiccoin-infra/           # ← codexacoin/provisioning + docker
```

`codexacoin/` stays in place as an unmodified reference. Keeping it lets every
later phase diff FIC against upstream to prove a change was deliberate, and it is
where `PARAMETERS.md` (CAC's consensus source of truth) lives.

## Directory mapping

| FIC target | CAC source | Notes |
|---|---|---|
| `firstislamiccoin-core/` | `codexacoin-core/` | Autotools, not CMake. 2,650 files |
| `firstislamiccoin-electrumx/` | `electrumx-cac/` | Fork of `CoinBlack/electrumx-blk`. Indexing unverified upstream |
| `firstislamiccoin-mobile/` | `cac_wallet/` | Flutter, Android + iOS |
| `firstislamiccoin-web-wallet/` | `web-wallet/` | Static vanilla JS, **no build step** — not React/Vite |
| `firstislamiccoin-explorer/` | `explorer/` | Flask + static frontend, not `btc-rpc-explorer` |
| `firstislamiccoin-staking-service/` | `vps-gateway/` | Custodial pool only; see note below |
| `firstislamiccoin-website/` | `website/` | Static; not Astro/Next |
| `firstislamiccoin-infra/` | `provisioning/` + `docker/` | Merged: systemd/nginx/Docker deploy + regtest env |
| `firstislamiccoin-brand/` | *(none)* | New in FIC. Sourced from `FIC_Brand_Kit/fic-brand/` |

### Components with no FIC target

Dropped per the decision recorded in
[`CHANGELOG-FIC.md`](CHANGELOG-FIC.md#decision-3--drop-the-issuer-and-dex-components):

| CAC source | What it is |
|---|---|
| `base-issuer/` | Wrapped ERC-20 on Base, Uniswap listing (live for CAC) |
| `bnb-issuer/` | Wrapped BEP-20 on BNB Chain, PancakeSwap listing (live for CAC) |
| `stellar-issuer/` | Stellar asset issuer |
| `checkout-widget/` | Merchant payment widget |

### Components with no prompt equivalent, carried anyway

| CAC source | FIC destination | Why |
|---|---|---|
| `faucet/` | `firstislamiccoin-infra/faucet/` | Needed for testnet work in Phase 2 |
| `docs/mobile-api.md` | `firstislamiccoin-staking-service/docs/` | REST contract the mobile + web wallets both speak |
| `docs/store-compliance.md` | `firstislamiccoin-mobile/store/` | App Store / Play policy notes; feeds Phase 5.7 |

## Where the prompt's phases land

| Phase | Directory | Upstream state |
|---|---|---|
| 1 — core rebrand, chain params, fixed reward | `firstislamiccoin-core/` | Builds on Linux; mainnet live |
| 2 — testnet validation | `firstislamiccoin-infra/` | `docker/` regtest env works |
| 3 — desktop CI + release | `firstislamiccoin-core/.github/` | `release.yml` written, **never run end-to-end** |
| 4 — ElectrumX | `firstislamiccoin-electrumx/` | **Indexing unverified** |
| 5 — mobile | `firstislamiccoin-mobile/` | Builds; store metadata written |
| 6 — staking service | `firstislamiccoin-staking-service/` | Custodial only — **no P2CS exists** |
| 7 — web wallet | `firstislamiccoin-web-wallet/` | Deployed |
| 8 — explorer | `firstislamiccoin-explorer/` | Deployed |
| 9 — website | `firstislamiccoin-website/` | Deployed |
| 10 — launch | `docs/` | — |

## Two mapping caveats

**Phase 6 is not a rebrand.** The prompt's Phase 6.2 describes non-custodial P2CS
cold staking as the primary mode, with the custodial pool as an opt-in secondary.
CAC has this backwards relative to the prompt: the custodial pool
(`vps-gateway/staking.py`) is built and deployed, and P2CS **does not exist in any
form** — `PARAMETERS.md` §14 is a design document for an unbuilt feature. See
[`cac-audit.md` §7](cac-audit.md). So `firstislamiccoin-staking-service/` is a
rebrand for the custodial half and greenfield consensus work for the other.

**Phase 3.4 and Phases 5.3 / 7.2 / 8.2 inherit that gap**, since each assumes a
P2CS delegation UI "reused from CAC". There is nothing to reuse.
