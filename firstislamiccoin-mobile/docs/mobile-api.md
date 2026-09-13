# FirstIslamicCoin Mobile API Gateway Specification

This wallet's copy of CAC's `docs/mobile-api.md` -- the REST contract
`lib/services/gateway_api.dart` is built against. **The gateway itself
does not exist for FIC** -- Phase 6 (`firstislamiccoin-staking-service/`,
CAC's `vps-gateway/`) hasn't been built at all yet, see
`../../docs/repo-map.md`'s "Two mapping caveats". This document is carried
over from CAC almost unchanged (same endpoints, same shapes, same
rationale for a REST layer over raw Electrum) with one substantive
correction: §5's staking-status shape assumed CAC's coin-age reward
model, which FIC does not have (see the note in that section).

## Why a REST gateway in front of Electrum, not raw Electrum protocol

Real Electrum-based desktop wallets talk the Electrum JSON-RPC-over-TCP/SSL
protocol directly. Mobile apps *could* do the same, but:

1. The Electrum protocol is script-hash-indexed (SHA256 of the output
   script, reversed) -- every client needs correct script->scripthash
   derivation for every address type (P2PKH, P2SH, bech32) before it can
   ask "what's my balance". A REST layer that accepts addresses directly
   removes an entire class of mobile-client bugs.
2. Electrum protocol connections are long-lived, stateful (subscriptions,
   notifications) -- fine for a desktop app that stays running, awkward for
   a mobile app that gets backgrounded/killed by the OS constantly. A
   stateless REST API is a much better fit for mobile's actual lifecycle.
3. The staking-service endpoints (§5) have **no Electrum equivalent at
   all** -- they need a purpose-built backend regardless.

So: one gateway, REST/JSON, stateless, backed internally by one or more
`firstislamiccoin-electrumx` instances (wallet data: §2-4, Phase 4 --
also not built yet for FIC) plus the staking service once it exists (§5).
Mobile apps talk to the gateway; the gateway talks to Electrum servers and
the staking backend. Mobile apps never connect to Electrum servers
directly, and never see the staking backend's internals.

## Conventions

- Base URL: `https://staking-api.firstislamiccoin.com/v1` (placeholder --
  see `../lib/config/network_config.dart` and `../../docs/dns.md`; format
  `https://<gateway-host>/v1`).
- All amounts are strings in satoshis (8 decimals), never floats, to
  avoid client-side precision bugs. Format as FIC client-side by
  dividing by `100000000`.
- All requests/responses are JSON. `Content-Type: application/json`.
- Errors follow a consistent shape (see §6).
- No authentication for read endpoints (§2-4 are public blockchain data,
  same trust model as a public Electrum server). §5 (staking) requires
  auth -- see that section.
- Rate limiting: per-IP, details TBD when the gateway is actually built.

## 1. Health / network info

### `GET /v1/network/status`

```json
{
  "network": "mainnet",
  "chain_height": 812345,
  "best_block_hash": "000000...",
  "electrum_servers_healthy": 2,
  "electrum_servers_total": 2
}
```

Gateway-internal: queries `server.version` + `blockchain.headers.subscribe`
against each configured `firstislamiccoin-electrumx` backend, returns the
aggregate.

## 2. Balance

### `GET /v1/address/{address}/balance`

```json
{
  "address": "F...",
  "confirmed": "1400003034000000",
  "unconfirmed": "0"
}
```

Gateway-internal: derive scripthash from `address`, call
`blockchain.scripthash.get_balance`.

**Note on "stake" balance**: FIC's staking reward is a fixed 10 FIC plus
that block's fees, paid to whoever stakes the block -- it accrues directly
into the staker's own spendable balance the moment their coinstake
confirms, same "no separate staking balance bucket" story as CAC, just a
different reward formula underneath (see §5's note).

## 3. UTXOs

### `GET /v1/address/{address}/utxos`

```json
{
  "address": "F...",
  "utxos": [
    {
      "txid": "abcd...",
      "vout": 0,
      "value": "2800000000000000",
      "height": 501,
      "confirmations": 12
    }
  ]
}
```

Gateway-internal: `blockchain.scripthash.listunspent`, enriched with
`confirmations` (computed from `height` and current chain tip, since the
raw Electrum response only gives height).

## 4. Transaction history, details, broadcast, fee estimate

### `GET /v1/address/{address}/history?limit=50&before_height=<h>`

```json
{
  "address": "F...",
  "transactions": [
    {"txid": "abcd...", "height": 501, "fee": null}
  ],
  "has_more": false
}
```

Gateway-internal: `blockchain.scripthash.get_history` (+ pending mempool
entries via `blockchain.scripthash.get_mempool`), paginated
gateway-side since Electrum returns the full history in one call.

### `GET /v1/tx/{txid}`

Full transaction detail (decoded, not just raw hex) -- inputs, outputs,
addresses, value, confirmations, and (for coinstake transactions
specifically) the reward amount, computed gateway-side as: reward = (sum
of coinstake outputs) - (sum of coinstake inputs). For FIC that
difference should always equal the fixed 10 FIC block subsidy plus that
block's fees (see §5's note) -- unlike CAC's coin-age model, it does not
scale with how long or how much was staked.

```json
{
  "txid": "abcd...",
  "height": 501,
  "confirmations": 12,
  "is_coinstake": true,
  "reward_satoshis": "1000000000",
  "vin": [...],
  "vout": [...]
}
```

Gateway-internal: `blockchain.transaction.get` (verbose), plus the
reward-delta computation above for coinstake txs.

### `POST /v1/tx/broadcast`

Request:
```json
{"raw_tx_hex": "0200000001..."}
```

Response (success):
```json
{"txid": "abcd..."}
```

Response (rejected):
```json
{"error": {"code": "tx-rejected", "message": "bad-txns-inputs-missingorspent"}}
```

Gateway-internal: `blockchain.transaction.broadcast`. The gateway does
**not** sign anything -- signing happens entirely client-side on the
mobile device (see `../store/store-compliance.md`: keys never leave the
device). This endpoint only relays an already-signed transaction.

### `GET /v1/fee-estimate?target_blocks=6`

```json
{"target_blocks": 6, "fee_rate_sat_per_vbyte": "1000"}
```

Gateway-internal: `blockchain.estimatefee`. Like CAC's `electrumx-cac`,
`firstislamiccoin-electrumx`'s Blackcoin-derived coin definition returns a
**fixed** `ESTIMATE_FEE` rather than a real dynamic estimate, since this
Bitcoin-Core-derived codebase doesn't implement the `estimatesmartfee`-
style RPCs Blackcoin/CAC/FIC lack. Document this plainly in the mobile
app's fee UI rather than presenting it as a real-time estimate -- it's a
fixed default, not measured from the actual current mempool. (See
`send_screen.dart`'s own comment on this same point.)

## 5. Staking service (Phase 6 -- not implemented yet)

These endpoints don't exist behind any real backend today; specified now
so `lib/services/gateway_api.dart` and `lib/screens/staking_screen.dart`
have a stable contract to build against, and swap in the real thing once
Phase 6 ships. All require authentication -- a bearer token issued at
account creation (mechanism TBD in Phase 6).

**Reward-model correction from CAC.** CAC's version of this section
described `effective_monthly_rate_bp` echoing a consensus parameter
(`nStakeRewardAnnualBP`) that set a *rate* stakers earn proportional to
how much and how long they'd held -- CAC's coin-age design. FIC has no
coin-age mechanism: the reward is a fixed 10 FIC plus fees per block,
paid to whichever staker's kernel wins that block (see
`../../docs/CHANGELOG-FIC.md`'s Phase 1 section and `docs/genesis.md`).
There is no fixed annual/monthly *rate* a given staker is owed --
realized return depends on how much of the network's total staking weight
their coins represent and how often that wins a block, which is not a
single number the protocol defines. Whatever Phase 6 actually builds needs
to report real observed/estimated figures (e.g. this pool's own recent
average payout), not a consensus constant that doesn't exist for FIC.
`StakingStatus` in `lib/models/wallet_models.dart` keeps the
`effectiveMonthlyRateBp` field name for now (so this contract doesn't
change shape again once real numbers exist) but nothing computes a real
value for it yet.

### `GET /v1/staking/status` (auth required)

```json
{
  "mode": "custodial",
  "delegated_amount": "500000000000000",
  "accrued_rewards": "5700000000",
  "effective_monthly_rate_bp": 0,
  "pool_fee_bp": 500,
  "can_withdraw": true
}
```

`mode` is `"custodial"` (pooled staking through this gateway) or
`"delegated"` (on-chain P2CS cold-staking delegation) -- see the note
below on why `"delegated"` has no real meaning for FIC yet.

### `POST /v1/staking/deposit` (auth required)

Request: `{"amount": "500000000000000"}` -- returns a deposit address to
send funds to (custodial pool address). Mobile app builds and broadcasts
the funding transaction itself via §4's broadcast endpoint, same as any
other send.

### `POST /v1/staking/withdraw` (auth required)

Request: `{"amount": "500000000000000", "to_address": "F..."}` -- the
*user's own* address (withdrawals go back to an address the user's own
device controls the key for, never anywhere else).

### `POST /v1/staking/delegate` / `POST /v1/staking/revoke` -- not applicable to FIC

CAC's version of this document specified these for its Phase 6B
(non-custodial P2CS cold-staking delegation). **FIC has no P2CS in its
consensus layer at all** -- not paused, not planned for a later phase,
genuinely absent from `firstislamiccoin-core` (see
`../../docs/CHANGELOG-FIC.md`'s TODO-HUMAN table and
`../../docs/repo-map.md`'s "Two mapping caveats"). `GatewayApi` in this
wallet has no client methods for these endpoints, unlike CAC's, which
keeps them unused but present. Adding P2CS is real consensus-layer work,
not a mobile client change -- if it ever happens, this section gets
written for real at that point.

## 6. Error format

All non-2xx responses:

```json
{
  "error": {
    "code": "invalid-address",
    "message": "Human-readable description",
    "details": {}
  }
}
```

Standard `code` values: `invalid-address`, `not-found`, `tx-rejected`,
`electrum-backend-unavailable`, `rate-limited`, `unauthorized` (§5 only).

## 7. Push notifications, price alerts, referrals

`POST /v1/push/mobile/register`, the `/v1/price-alerts/mobile*` endpoints,
and `/v1/referral/*` all carry over from CAC unchanged in shape (see
`lib/services/gateway_api.dart`) -- none of them are staking- or
DEX-price-specific, so nothing about FIC's dropped coin-age/DEX features
required changing their contracts. `/v1/price`'s *meaning* is worth
flagging though: CAC's version sourced this from a real PancakeSwap/
Stellar DEX price (see CAC's `vps-gateway/price.py`), which existed only
because CAC has wrapped-token DEX listings this project deliberately
dropped (`../../docs/CHANGELOG-FIC.md`'s Decision 3). Whoever builds
Phase 6 for FIC needs a different, real source for this number -- there
is no DEX pool to read a price from. Until then this field has no honest
value to return, and `lib/widgets/fiat_placeholder.dart` reflects that on
the client side.

## 8. What this spec deliberately does not cover yet

- Exact auth mechanism for §5.
- Multi-backend failover/load-balancing behavior when the gateway has more
  than one `firstislamiccoin-electrumx` instance behind it (operational
  detail for whoever deploys the gateway, not a client-facing contract
  change).
- Where §7's `/v1/price` actually sources a number from, now that the DEX
  source CAC used doesn't apply -- see that section's note.
