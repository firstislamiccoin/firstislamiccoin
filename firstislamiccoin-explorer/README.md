# firstislamiccoin-explorer

Phase 8 deliverable. A public, read-only block explorer — a separate service
from any future staking-service backend, holding no wallet keys and able to
move no funds.

## Backend

Direct `firstislamiccoind` RPC. `txindex=1` is on by default on this fork
(staking depends on it — see `wallet/staking.cpp` in `firstislamiccoin-core`),
so arbitrary block/transaction lookup by hash/height/txid works natively, no
separate indexer needed for those. Address balance/UTXO lookups use
`scantxoutset`, a stateless full-UTXO-set scan, rather than importing
addresses into a wallet — appropriate here specifically because the explorer
has to accept *any* address a visitor types in without accumulating permanent
wallet state for each one.

**Known limitation**, stated in the API response itself, not just here:
`scantxoutset` only sees the *current* UTXO set. Address pages show accurate
current balance/UTXOs but not historical (already-spent) transactions — that
needs a real index (`firstislamiccoin-electrumx`, Phase 4, not built yet).
Block and transaction lookups by hash/height/txid are unaffected by this —
those work fully and precisely via `txindex`.

**Supply is exact, not estimated.** Unlike the project this was forked from
(which had a fixed-subsidy proof-of-work premine window followed by an
open-ended coin-age-proportional reward with no simple closed-form total),
FIC's supply at any height is `14,000,000,000 + 10 × height` FIC, always —
see `docs/tokenomics.md`. `/api/supply`, `/api/circulating` and
`/api/supply-series` compute this directly rather than scanning anything.

**`active_stake_weight` (staking statistics) is intentionally `null`.** It
would need a staking wallet's `getstakinginfo` RPC (`netstakeweight`), which
this backend deliberately doesn't hold — see the module docstring in
`app.py`. Shown as unavailable rather than approximated from an unverified
formula.

**Delegated (P2CS/cold) staking statistics don't exist**, because the feature
itself doesn't exist in `firstislamiccoin-core` yet (TODO-HUMAN 2 in
`docs/CHANGELOG-FIC.md`). `/api/staking-stats` reports this honestly rather
than fabricating numbers for an unbuilt feature.

## Frontend

Static, bundler-free (same approach as the planned `firstislamiccoin-web-wallet`
and `firstislamiccoin-website`), hash-routed:
`#/block/<height-or-hash>`, `#/tx/<txid>`, `#/address/<address>`,
`#/richlist`, `#/staking`.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/stats` | Height, best block, difficulty, premine, fixed reward, exact total supply |
| `GET /api/supply` | Plain total supply figure, for listing forms |
| `GET /api/circulating` | Circulating supply (equals total supply on this chain — see above) |
| `GET /api/blockreward` | The fixed reward and its rules, for listing forms |
| `GET /api/staking-stats` | Measured blocks/day, target blocks/day, current reward, annual emission |
| `GET /api/block/<height-or-hash>` | Block detail with its transactions |
| `GET /api/tx/<txid>` | Transaction detail; coinstake reward (and its fee portion) if applicable |
| `GET /api/address/<address>` | Current balance and UTXOs (see the historical-data limitation above) |
| `GET /api/search?q=` | Disambiguates a height, hash, txid, or address |
| `GET /api/richlist?limit=` | Top balances, windowed (see `EXPLORER_RICHLIST_MAX_BLOCKS`) |
| `GET /api/supply-series` | Exact supply at up to 50 sampled heights, for the home page chart |

## Running locally

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export FIC_RPC_COOKIEFILE=/path/to/.firstislamiccoin/testnet/.cookie
# or: export FIC_RPC_USER=... FIC_RPC_PASSWORD=...
python3 app.py              # backend, port 8081
python3 -m http.server 8091 # frontend, separately -- set localStorage
                             # "fic_explorer_api" if not http://127.0.0.1:8081
```

## Verification (Phase 8)

Run against the real, live testnet from `firstislamiccoin-infra/` (node2,
which already has `-coinstatsindex=1` and, like every node in that compose
file, `-txindex=1`), by installing this backend's dependencies into a
throwaway `tools`-profile container already wired to the testnet's network
and read-only cookie mount, then hitting it from the host:

```bash
cd firstislamiccoin-infra
docker compose -f docker-compose.testnet.yml run --rm -p 8081:8081 \
  --entrypoint sh -v "$(pwd)/../firstislamiccoin-explorer:/explorer:ro" tools -c \
  'apt-get update -qq && apt-get install -y -qq python3-pip >/dev/null && \
   pip3 install --quiet --break-system-packages -r /explorer/requirements.txt && \
   cd /explorer && FIC_RPC_HOST=node2 FIC_RPC_PORT=29771 \
   FIC_RPC_COOKIEFILE=/data/node2/testnet/.cookie python3 app.py'
```

At height 305 on the real testnet: `/api/stats` returned `best_block_hash`
identical to the node's own `getblockchaininfo`, and `total_supply_fils`
(`1,400,000,305,000,000,000` fils = 14,000,003,050 FIC) matched
`14,000,000,000 + 10 × 305` exactly. `/api/block/0` returned the known
testnet genesis hash and a premine total of exactly 14,000,000,000 FIC.
`/api/block/1` correctly flagged the block's second transaction as a
coinstake. `/api/tx/<that coinstake>` reported `reward_fils` of exactly
10 FIC with zero fees (the first staked block after genesis carried no other
transactions). `/api/address/<a real funded address>` returned a balance in
fils matching the node's own `getreceivedbyaddress` exactly. `/api/richlist`
returned real, plausible balances scanned from genesis. Every response was
checked against the node's own RPC output directly, not assumed correct.

## Deploying for real

Not deployed. See `docs/dns.md` (the `explorer.firstislamiccoin.com` DNS
record doesn't exist yet) and `firstislamiccoin-infra/provisioning/explorer/`
for an example nginx config that reverse-proxies the static frontend and
`/api/` to this backend under one origin — needs a real server and domain,
neither of which this environment has access to.
