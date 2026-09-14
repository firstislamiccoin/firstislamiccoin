# FirstIslamicCoin Electrum server provisioning (firstislamiccoin-electrumx)

Adapts [CoinBlack/electrumx-blk](https://github.com/CoinBlack/electrumx-blk)
(Blackcoin's own ElectrumX fork), by way of CAC's own `electrumx-cac`, to
FIC — see `../../../firstislamiccoin-electrumx/` at the repo root for the
actual source. This directory is deployment tooling only.

## Why ElectrumX, not Fulcrum

Same reasoning CAC's own `electrumx-cac/README.md` gives: Fulcrum has no
generic altcoin support, while `electrumx-blk` already ships a
Blackcoin-specific transaction deserializer (`DeserializerBlackcoinSegWit`)
that correctly parses the PoS coinstake `nTime` field FIC inherits
unchanged from Blackcoin/CAC. Adapting it was chain-identity configuration
(genesis hash, RPC port, address prefixes) — see the
`FirstIslamicCoin`/`FirstIslamicCoinTestnet`/`FirstIslamicCoinRegtest`
classes in `firstislamiccoin-electrumx/src/electrumx/lib/coins.py`.

## What was actually verified this phase

Unlike CAC's own Phase 4 (see their `electrumx-cac/provisioning/electrumx/
README.md`) — which macOS packaging issues blocked from ever running real
indexing, only a daemon-connection check — this was verified end-to-end
against a live regtest `firstislamiccoind`:

1. Built the `Dockerfile` in this directory (Debian bookworm-slim +
   `libleveldb-dev`) as image `fic-electrumx`. It built and ran cleanly —
   the macOS/`plyvel` packaging problem CAC hit does not apply on Linux.
2. Ran it against `fic-regtest3` (a local regtest node with 50+ blocks,
   including a real send: `9278a0c0a6f10467589796490f9deb3fa8c15cf030c5a
   d12b015998b25bce31f`, 777.5 FIC to `mz5jgSPSRht9swKqAHi2GPQpbV9SEKKwhx`).
   It fully synced to the daemon's height and started serving.
3. Queried the running server directly over its TCP RPC port
   (`blockchain.scripthash.get_balance` / `get_history`) for that address
   and got back exactly `{"confirmed": 77750000000, "unconfirmed": 0}` and
   a history containing that same txid at height 3 — matching the node's
   own `gettxout`/`getrawtransaction` output (777.50000000 FIC) exactly.

This surfaced and fixed two real, FIC-specific bugs in
`firstislamiccoin-electrumx/src/electrumx/lib/coins.py` that CAC's own
verification depth was never able to catch (see `docs/CHANGELOG-FIC.md`'s
Phase 4 section for the full writeup):

- The base `Coin.genesis_block()` truncates the genesis block to an
  unspendable, zero-transaction coinbase, matching Bitcoin/CAC. FIC's
  genesis intentionally has 1000 spendable premine outputs (see
  `docs/genesis.md`), so that truncation silently dropped the premine
  transaction from the index — the very first spend of a premine output
  crashed the indexer with `ChainError: UTXO ... not found in "h" table`.
  Fixed by overriding `genesis_block()` on the `FirstIslamicCoin` base
  class to keep the real transactions, only verifying the header hash.
- `FirstIslamicCoinRegtest.TX_COUNT_HEIGHT` was `0` (a "fresh chain, no
  history yet" placeholder), which divides by zero in
  `block_processor.estimate_txs_remaining()` the moment sync first catches
  up to the daemon. Fixed by setting it to `1`.

## Usage

### Docker (recommended)

```bash
cd firstislamiccoin-electrumx
docker build -f ../firstislamiccoin-infra/provisioning/electrumx/Dockerfile -t firstislamiccoin-electrumx .
docker run -d --name firstislamiccoin-electrumx \
  -e DAEMON_URL="http://rpcuser:rpcpassword@<node-host>:19771/" \
  -e COIN=FirstIslamicCoin -e NET=mainnet \
  -p 50001:50001 -p 50002:50002 \
  -v firstislamiccoin-electrumx-db:/home/electrumx/db \
  firstislamiccoin-electrumx
```

### Bare VPS (systemd)

On a fresh Ubuntu 22.04/24.04 or Debian 12 VPS, with a fully-synced,
`-txindex`-enabled `firstislamiccoind` already reachable:

```bash
REPO_URL=https://github.com/firstislamiccoin/firstislamiccoin-electrumx.git \
REPO_REF=main \
PUBLIC_HOSTNAME=electrum1.firstislamiccoin.com \
NETWORK=testnet \
DAEMON_URL="http://rpcuser:rpcpassword@127.0.0.1:29771/" \
sudo -E ./provision.sh
```

This installs `libleveldb-dev` + build tools, clones and `pip install -e`s
`firstislamiccoin-electrumx` into a venv, obtains a Let's Encrypt cert via
`certbot` (standalone mode — needs DNS for `PUBLIC_HOSTNAME` already
pointed at this host, or it warns and continues without TLS so you can
rerun later), writes `/etc/firstislamiccoin-electrumx.conf`, and
installs+starts the `firstislamiccoin-electrumx.service` systemd unit.
electrumx has native TLS support (`SSL_CERTFILE`/`SSL_KEYFILE`) — no
nginx/stunnel reverse-proxy needed.

Re-running `provision.sh` is safe (idempotent).

## For the second server

Repeat with a different `PUBLIC_HOSTNAME` — `docs/dns.md` already reserves
`electrum1`/`electrum2` (mainnet) and `testnet-electrum1`/
`testnet-electrum2` (testnet) subdomains, matching the `PEERS` entries in
`coins.py`. They don't need to talk to each other — each independently
indexes from its own (or a shared) `firstislamiccoind`'s RPC.

## Verifying

```bash
journalctl -u firstislamiccoin-electrumx -f   # watch initial sync

# from any machine, once a cert is live:
echo '{"id": 1, "method": "blockchain.headers.subscribe", "params": []}' | \
  openssl s_client -quiet -connect electrum1.firstislamiccoin.com:50002
```

## Ports

| Network | TCP | SSL |
|---|---|---|
| mainnet | 50001 | 50002 |
| testnet | 51001 | 51002 |
| regtest | 52001 | 52002 |

(Deliberately different from Bitcoin's own 50001/50002 mainnet convention
being reused for FIC testnet/regtest, to avoid confusing a wallet pointed
at the wrong network with a plausible-looking but wrong port.)
