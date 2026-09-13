# Testnet validation network (Phase 2)

A four-node FirstIslamicCoin testnet in Docker, the scripts that bootstrap and
stress it, and the report generator behind [`docs/testnet-report.md`](../../docs/testnet-report.md).

## Topology

| Node | Networks | Extra configuration | Wallets |
|---|---|---|---|
| node0 | `fic-a` | `-txindex=1` | `genesis`, `staker1`, `stress0` |
| node1 | `fic-a` | `-maxmempool=5` during the spray step | `staker2`, `staker5`, `stress1` |
| node2 | `fic-a` + `fic-b` | `-coinstatsindex=1`; `-reindex` during the reindex step | `staker3` |
| node3 | `fic-b` | — | `staker4`, `stress3` |

node3 is on its own bridge network, so everything it receives has crossed node2.
Every node stakes (`-staking=1`) and keeps the transaction index, which FIC's
staker requires. No RPC port is published; the tools and monitor containers read
each node's cookie from its datadir volume, mounted read-only.

## Running it

From `firstislamiccoin-infra/`:

```bash
docker compose -f docker-compose.testnet.yml build
```
```bash
docker compose -f docker-compose.testnet.yml up -d
```
```bash
docker compose -f docker-compose.testnet.yml run -d --name fic-testnet-bootstrap tools testnet/bootstrap.py
```

The bootstrap needs `secrets/testnet-genesis-key.txt` (git-ignored; the `wif=`
line) and takes about three hours: the premine moves in tranches that each wait
out the 50-block maturity, because moving every genesis output at once would
leave nothing able to stake. Progress: `docker logs -f fic-testnet-bootstrap`,
live status: `testnet/out/monitor-status.json`.

Once it has finished:

```bash
testnet/run-stress.sh
```

After at least 2,000 blocks (about 36 hours at 64-second spacing):

```bash
docker compose -f docker-compose.testnet.yml run --rm tools testnet/report.py
```

The report is written to `testnet/out/testnet-report.md`, alongside
`testnet-metrics.json`. Tear down, deleting all chain data, with
`docker compose -f docker-compose.testnet.yml down -v`.

## Files

| File | Runs in | Purpose |
|---|---|---|
| `ficrpc.py` | tools | JSON-RPC client using cookie auth; Decimal amounts throughout |
| `monitor.py` | monitor | samples tips, forks, peers and mempools every 5 s into `out/monitor.jsonl`; logs every reorg with its depth |
| `bootstrap.py` | tools | imports the genesis key, distributes the premine to five staking wallets in tranches; resumable |
| `stress.py` | tools | fund, 10,000-transaction spray, reindex check, txindex lookups, invalidateblock/reconsiderblock |
| `run-stress.sh` | host | runs the stress steps and the node restarts between them; records the `-prune` check |
| `rolling-upgrade.sh` | host | moves the nodes to a new `fic-node` image one at a time while the chain keeps running, recording each node's downtime and catch-up time; non-consensus changes only |
| `report.py` | tools | re-reads every block to check reward and spacing; merges monitor and stress records into the report |

## Why `-maxtipage`

The testnet genesis block is dated 2026-09-12. A node whose tip is older than
`-maxtipage` (default 24 hours) stays in initial block download, and the staker
does not run during IBD, so on a fresh network no block could ever be produced.
The nodes run with a one-year `-maxtipage`. Once the chain has recent blocks this
no longer matters. The same applies to the first stakers at mainnet launch
(TODO-HUMAN 3 in `docs/CHANGELOG-FIC.md`).
