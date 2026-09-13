# DNS records — firstislamiccoin.com

Every subdomain named in the brand constants table
([`firstislamiccoin-brand/docs/brand.md`](../firstislamiccoin-brand/docs/brand.md)), and what it's
for. **None of these records exist yet** — the domain itself is not confirmed registered by this
project, and no DNS provider or registrar access is available in this environment. This document
is the plan an operator with registrar/Cloudflare access should follow; nothing here should be
read as "already configured."

## Records to create

| Name | Type | Target / value | Purpose | Depends on |
|---|---|---|---|---|
| `firstislamiccoin.com` | CNAME (or `A`/`AAAA` per Cloudflare Pages' instructions) | Cloudflare Pages project | The website itself | `firstislamiccoin-website/` deployed (Phase 9) |
| `www.firstislamiccoin.com` | CNAME | `firstislamiccoin.com` | Redirect to the apex | Phase 9 |
| `explorer.firstislamiccoin.com` | CNAME | Explorer hosting target | Block explorer | Phase 8 |
| `wallet.firstislamiccoin.com` | CNAME | Web wallet hosting target | Browser wallet | Phase 7 |
| `staking-api.firstislamiccoin.com` | CNAME | Staking-service gateway hosting target | REST backend the mobile + web wallets both call for balance/history/broadcast/staking (see `firstislamiccoin-mobile/docs/mobile-api.md`) | Phase 6 |
| `staking-api.testnet.firstislamiccoin.com` | CNAME | Staking-service gateway hosting target (testnet) | Same, against testnet | Phase 6 |
| `electrum1.firstislamiccoin.com` | `A`/`AAAA` | ElectrumX server 1 IP | Light-client backend | Phase 4 |
| `electrum2.firstislamiccoin.com` | `A`/`AAAA` | ElectrumX server 2 IP | Light-client backend | Phase 4 |
| `seed1.firstislamiccoin.com` | `A`/`AAAA` (a real DNS seed also needs the domain's NS delegated for it, or a seeder like `dnsseed` returning peer IPs over DNS) | Seed node 1 IP | P2P bootstrap | Phase 6 infra / seed nodes |
| `seed2.firstislamiccoin.com` | `A`/`AAAA` | Seed node 2 IP | P2P bootstrap | Phase 6 infra / seed nodes |
| `seed3.firstislamiccoin.com` | `A`/`AAAA` | Seed node 3 IP | P2P bootstrap | Phase 6 infra / seed nodes |

`firstislamiccoin-core/src/kernel/chainparams.cpp` already has `seed{1,2,3}.firstislamiccoin.com`
as `vSeeds` on mainnet (not yet live — see `docs/CHANGELOG-FIC.md`); those hostnames need to
resolve before mainnet launch, not before testnet.

## What this project cannot do from here

- **Confirm domain ownership / registration.** No registrar credentials are available; this
  document assumes `firstislamiccoin.com` is or will be controlled by the project.
- **Create any DNS record.** Requires whoever holds the domain's DNS (Cloudflare, in the
  `firstislamiccoin-infra` deploy workflow's assumption) to add the records above by hand or via
  their own automation, using real server IPs / Cloudflare Pages project names once those exist.
- **Issue TLS certificates or configure Cloudflare Pages/Workers.** Downstream of DNS being live
  and an account existing; see `firstislamiccoin-website/.github/workflows/deploy.yml`, which
  needs `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` repository secrets that don't exist
  yet.

## `TODO-HUMAN`

All of the above — domain registration/ownership confirmation, a Cloudflare (or equivalent)
account, the actual DNS records, and the CI secrets — needs a human with registrar and hosting
access. Tracked in `docs/CHANGELOG-FIC.md`'s `TODO-HUMAN` table.
