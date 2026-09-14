# firstislamiccoin-staking-service

Phase 6 deliverable. Implements `../firstislamiccoin-mobile/docs/mobile-api.md`
for real -- the mobile app (`../firstislamiccoin-mobile/`) and the web wallet
(`../firstislamiccoin-web-wallet/`, not built yet -- see `../docs/repo-map.md`)
both talk to this. Also implements the 6A custodial staking pool
(mobile-api.md section 5's deposit/withdraw/status endpoints). Forked from
CodexaCoin's `vps-gateway/` -- see `../docs/CHANGELOG-FIC.md`'s Phase 6
section for every deviation from that source.

## Status

Not deployed anywhere -- no server, no DNS record (see `../docs/dns.md`,
which lists `staking-api.firstislamiccoin.com`/`staking-api.testnet.firstislamiccoin.com`
as planned but not live). Verified end-to-end against a real regtest
`firstislamiccoind` node in this development environment -- see
"Verification" below for exactly what that covered, including one real
finding worth a closer look (flagged, not fixed, in this phase).

## Backend choice: direct RPC, not firstislamiccoin-electrumx

`mobile-api.md` was written assuming this gateway sits in front of
`firstislamiccoin-electrumx` (Phase 4). This implementation instead talks
directly to `firstislamiccoind` via RPC, using a dedicated watch-only
wallet that imports any address it's asked about on first use. The REST
contract is identical either way -- mobile-api.md's own design treats the
backend as an internal detail. CAC's own `vps-gateway` made the exact same
substitution, for a related but distinct reason: CAC's `electrumx-cac`
existed but was blocked locally by a macOS packaging issue; FIC's
`firstislamiccoin-electrumx` (Phase 4) doesn't exist at all yet (see
`../docs/repo-map.md`'s "Two mapping caveats"). Either way, this is what
makes something actually runnable and verifiable end-to-end possible now
rather than waiting on Phase 4.

**Known limitation** (unchanged from CAC): unlike an indexed backend's
pre-built global index, this backend has to `importdescriptors` (with a
full rescan) the first time it sees a new address, which gets slower as
the chain grows. Fine for this project's current chain size; not a
drop-in replacement for a real Electrum backend at mainnet scale with
years of history.

## Staking pool design (6A)

Mechanically identical to CAC: each deposit gets its own dedicated
on-chain address/UTXO, funded once and never consolidated with other
users' deposits, so the chain's own PoS reward logic computes each
depositor's reward correctly and independently -- the pool never
reimplements that math, only detects when a deposit's UTXO gets staked
and credits the depositor's ledger with the reward minus the pool fee.

**Reward model differs from CAC, mechanics don't** -- see `staking.py`'s
module docstring for the full reasoning. CAC's coinstake reward is
coin-age-proportional, so the pool could quote a real annualized rate.
FIC's reward is a fixed 10 FIC plus that block's fees regardless of
deposit size (see `../docs/CHANGELOG-FIC.md`'s Phase 1 section) -- deposit
size affects only the *probability* of winning a block, not the *size* of
the reward. `status_for_user()`'s `effective_monthly_rate_bp` reports `0`
rather than a fabricated rate; see `../firstislamiccoin-mobile/docs/mobile-api.md`
section 5 for the client-facing side of this same note.

Known simplification (unchanged from CAC): `withdraw()` closes out all of
a user's active deposits at once rather than supporting partial
withdrawal from a specific deposit.

## What was dropped: price alerts have no price source

CAC's `price_alerts.py` sourced a real (if thin) price from a PancakeSwap
pool on BNB Chain and a Stellar DEX order book -- both only possible
because CodexaCoin issues wrapped tokens on those chains. FIC has neither
(`../docs/CHANGELOG-FIC.md`'s Decision 3) -- `fetch_fic_usd_price()` always
returns `None`, so `/v1/price` always answers `503 not-available` and the
price-alert watcher pass never fires. Both are honest, not bugs; see that
module's docstring.

## Configuration

Environment variables (see `../firstislamiccoin-infra/provisioning/staking-service/`
for how these get set in production):

| Variable | Default | Meaning |
|---|---|---|
| `FIC_RPC_HOST` / `FIC_RPC_PORT` | `127.0.0.1` / `29771` | firstislamiccoind RPC (29771 testnet, 19771 mainnet) |
| `FIC_RPC_COOKIEFILE` | — | preferred if set (matches how firstislamiccoin-infra's testnet nodes run -- no fixed RPC password) |
| `FIC_RPC_USER` / `FIC_RPC_PASSWORD` | — | used if no cookie file |
| `FIC_NETWORK` | `mainnet` | cosmetic only -- the RPC connection itself determines the real network |
| `GATEWAY_WATCH_WALLET` | `gateway` | watch-only wallet name for arbitrary-address queries |
| `GATEWAY_POOL_WALLET` | `stakingpool` | real (private-key-holding) wallet for the 6A pool |
| `GATEWAY_JWT_SECRET` | dev-only default | **generate a real one for production** (`openssl rand -hex 32`) |
| `GATEWAY_POOL_FEE_BP` | `500` (5%) | matches firstislamiccoin-mobile's `StakingStatus.notOptedIn` placeholder |
| _(none — `/v1/fee-estimate` is computed)_ | — | live `mempoolminfee` floor + a mempool-fullness heuristic; no config needed |
| `GATEWAY_CORS_ORIGINS` | `*` | tighten to the real web wallet's origin in production |
| `GATEWAY_DB_PATH` | `./gateway.db` | SQLite: users, deposits, reward ledger |
| `GATEWAY_KYC_ENCRYPTION_KEY` | — | Fernet key encrypting signup ID numbers at rest; signup returns 503 without it |
| `GATEWAY_ADMIN_WALLET` | `adminwallet` | funds referral payouts; must be funded manually, withdrawals fail cleanly if empty |
| `GATEWAY_REFERRAL_REWARD_BP` | `1000` (10%) | — |
| `GATEWAY_VAPID_PUBLIC_KEY` / `GATEWAY_VAPID_PRIVATE_KEY_PATH` / `GATEWAY_VAPID_SUBJECT` | — | Web Push, for the not-yet-built web wallet |
| `GATEWAY_FCM_SERVICE_ACCOUNT_PATH` | — | native mobile push via FCM |

## Running locally

```bash
python3 -m venv venv
source venv/bin/activate  # venv/Scripts/activate on Windows
pip install -r requirements.txt
export FIC_RPC_USER=... FIC_RPC_PASSWORD=... GATEWAY_JWT_SECRET=... GATEWAY_KYC_ENCRYPTION_KEY=...
python3 app.py            # dev server, port 8080
python3 watcher.py        # one watcher pass (run periodically -- see gateway-watcher.timer)
```

## Verification (Phase 6)

Full custodial-staking lifecycle verified end-to-end against a real
regtest `firstislamiccoind` node (regtest's 10-block maturity and ~1s
block spacing make a real coinstake reward observable within minutes,
unlike testnet/mainnet's real chain time) -- the same standard CAC's own
`vps-gateway` was held to, and the same "verify against something real"
standard this project's other phases (2, 8) used:

| Step | Result |
|---|---|
| Signup, login (JWT) | Worked; JWT round-trips correctly |
| Create deposit, fund externally from the regtest genesis premine | Gateway-issued P2PKH address funded via `sendtoaddress`; `/v1/staking/status` showed `0` delegated until... |
| Watcher detects funding | ...one `watcher.py` pass later, `delegated_amount` became `"500000000000"` (exactly the 5000 FIC sent) |
| Node stakes the deposit (regtest maturity + staking enabled on the pool wallet only, to give its small stake weight a realistic chance of winning a block) | Confirmed via `listtransactions`: `category: "generate"`, `amount: 10.0` -- **exactly** FIC's fixed block reward |
| Watcher detects the resulting coinstake, computes reward | `accrued_rewards` became `"950000000"` -- **exactly** `10 FIC gross − 5% pool fee = 9.5 FIC net`, matching the pool-fee math precisely |
| Withdraw | Hit a real, reproducible node/wallet-level issue -- see "One real finding" below. The gateway's own error handling was still verified: a clean `not-found`/"still maturing" JSON error, not a crash or a raw RPC exception leaking through |
| General wallet endpoints (`balance`, `utxos`, `history`, `tx-detail`, `fee-estimate`, `broadcast`) | Verified against a real ordinary (non-coinstake) send: `tx-detail` correctly showed `is_coinstake: false`; a separately-built-and-signed raw transaction was broadcast successfully through `/v1/tx/broadcast` itself, not just via the node directly |
| Referral | Bob signed up with Alice's real referral code and funded a 1000 FIC deposit; the watcher credited Alice exactly `100000000000 × 10% = 10000000000` satoshis (10 FIC) -- masked email (`b***@example.com`) confirmed in `/v1/referral/history` |
| Referral withdraw with an unfunded admin wallet | Clean `not-found` error, as designed, not a crash |
| `/v1/price` | `503 not-available`, as designed -- no source exists (see "What was dropped" above) |
| Mobile push registration + price alert creation | Both succeeded; `watcher.py`'s `mobile_notify` pass correctly detected the registered address's balance increase and attempted (then gracefully no-op'd, FCM unconfigured) a notification |
| Error paths: invalid address, missing auth | Clean `400`/`401` JSON errors |

### One real finding, flagged rather than fixed

After the deposit's coin staked (and, left running, kept re-staking every
time it matured -- an accepted/inherited limitation this phase didn't
need to solve, see `staking.py`'s docstring), its resulting UTXO showed
`"solvable": false` in the pool wallet -- a raw P2PK script, not the
P2PKH the original deposit address used -- and `sendtoaddress` failed
with `Insufficient funds` even though the wallet held the coin and its
private keys. This looks like a genuine, general issue in
`firstislamiccoin-core`'s coinstake-construction code (possibly reserving
a destination outside the descriptor wallet's normal bookkeeping), not
something specific to this gateway or to this test setup -- it could
affect any descriptor wallet that stakes, including the desktop wallet.
Flagged for a focused core-side investigation rather than guessed at
here; this touches consensus-adjacent wallet code well outside this
phase's scope.

### Not done in this pass

- **Not deployed anywhere.** No server, no DNS record -- see "Status"
  above. `../firstislamiccoin-infra/provisioning/staking-service/` (systemd
  units) is written and ready, adapted from CAC's own, but has no
  `provision.sh` (CAC's own `vps-gateway` didn't build one either; a
  human still needs to install Python, create the service user, and wire
  the systemd units by hand, same as CAC's own deployment story).
- **Web Push and FCM push were exercised structurally, not against a
  real subscriber/device** -- no VAPID keys or Firebase service account
  configured in this environment, so both paths took their documented
  "not configured, no-op" branch rather than actually delivering a
  notification.
- **The coinstake-output solvability finding above** -- flagged, not
  investigated further or fixed.

### `TODO-HUMAN`

Server, DNS, VAPID/FCM credentials, and the core-side coinstake-output
investigation -- tracked in `../docs/CHANGELOG-FIC.md`'s `TODO-HUMAN`
table.
