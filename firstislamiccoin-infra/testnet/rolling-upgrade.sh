#!/usr/bin/env bash
# Rolling upgrade of the testnet nodes to a new fic-node image, one node at a
# time, with the chain kept running: recreate the node's container on the new
# image, wait until it has peers again and has caught up with the network's
# tip, then move to the next. node0 (genesis wallet, bootstrap's RPC target)
# goes last. Each node's downtime and catch-up time is recorded in
# testnet/out/stress.jsonl for the report.
#
# Only for changes that do not alter consensus; a consensus change needs a
# fresh chain. Run it while testnet/bootstrap.py is waiting between tranches
# (or after it finishes): its RPC calls retry through a restart, but a
# sendmany interrupted mid-call makes it exit (it resumes when rerun).
#
# Usage (from anywhere): firstislamiccoin-infra/testnet/rolling-upgrade.sh <image-tag>
set -euo pipefail
cd "$(dirname "$0")/.."
TAG=${1:?usage: rolling-upgrade.sh <fic-node image tag, e.g. 1a2b3c4>}
DC=(docker compose -f docker-compose.testnet.yml)
CLI="firstislamiccoin-cli -testnet"

docker image inspect "fic-node:$TAG" >/dev/null
old_id=$(docker image inspect fic-node:latest --format '{{.Id}}')
new_id=$(docker image inspect "fic-node:$TAG" --format '{{.Id}}')
[ "$old_id" != "$new_id" ] || { echo "fic-node:latest is already $TAG"; exit 0; }
docker tag "fic-node:$TAG" fic-node:latest
if docker image inspect "fic-tools:$TAG" >/dev/null 2>&1; then docker tag "fic-tools:$TAG" fic-tools:latest; fi

node_cli() { docker exec "fic-testnet-$1-1" $CLI "${@:2}"; }

network_tip() {
  local best=0 h
  for n in node0 node1 node2 node3; do
    [ "$n" = "$1" ] && continue
    h=$(node_cli "$n" getblockcount 2>/dev/null || echo 0)
    [ "$h" -gt "$best" ] && best=$h
  done
  echo "$best"
}

for node in node3 node2 node1 node0; do
  echo "=== $node -> fic-node:$TAG ($(date -u +%FT%TZ))"
  before=$(node_cli "$node" getblockcount)
  wallets=$(node_cli "$node" listwallets | tr -d ' \n')
  t0=$(date +%s)
  "${DC[@]}" up -d --no-build --no-deps --force-recreate "$node"

  rpc_up=""
  for _ in $(seq 1 300); do
    if node_cli "$node" getblockcount >/dev/null 2>&1; then rpc_up=$(date +%s); break; fi
    sleep 1
  done
  [ -n "$rpc_up" ] || { echo "$node: RPC did not return within 300 s"; exit 1; }

  caught_up=""
  for _ in $(seq 1 600); do
    h=$(node_cli "$node" getblockcount 2>/dev/null || echo 0)
    peers=$(node_cli "$node" getconnectioncount 2>/dev/null || echo 0)
    if [ "$peers" -ge 1 ] && [ "$h" -ge "$(network_tip "$node")" ]; then caught_up=$(date +%s); break; fi
    sleep 1
  done
  [ -n "$caught_up" ] || { echo "$node: did not catch up within 600 s"; exit 1; }

  after=$(node_cli "$node" getblockcount)
  version=$(node_cli "$node" getnetworkinfo | grep '"subversion"' | cut -d'"' -f4)
  wallets_after=$(node_cli "$node" listwallets | tr -d ' \n')
  echo "$node: rpc back after $((rpc_up - t0)) s, caught up after $((caught_up - t0)) s, height $before -> $after, wallets $wallets_after"
  "${DC[@]}" run --rm tools testnet/stress.py record "$(printf '{"step": "rolling-upgrade", "node": "%s", "image": "%s", "subversion": "%s", "rpc_back_s": %d, "caught_up_s": %d, "height_before": %d, "height_after": %d, "wallets_reloaded": %s}' \
    "$node" "$TAG" "$version" "$((rpc_up - t0))" "$((caught_up - t0))" "$before" "$after" "$([ "$wallets" = "$wallets_after" ] && echo true || echo false)")" >/dev/null
done
echo "=== rolling upgrade to $TAG complete ($(date -u +%FT%TZ))"
