#!/usr/bin/env bash
# Host-side driver for the Phase 2 stress steps: runs each step of
# testnet/stress.py in the tools container and performs the node restarts
# between them (the tools container has no Docker access, by design).
#
# Usage (from anywhere): firstislamiccoin-infra/testnet/run-stress.sh [step ...]
# With no arguments runs every step in order. Needs the network bootstrapped.
set -euo pipefail
cd "$(dirname "$0")/.."
DC=(docker compose -f docker-compose.testnet.yml)

tools() { "${DC[@]}" run --rm tools testnet/stress.py "$@"; }

# restart <service> [extra args...]: recreate one node with extra arguments
# (none = its normal configuration). Chain data lives in the named volume.
restart() {
  local svc=$1; shift
  local var
  var="$(echo "$svc" | tr '[:lower:]' '[:upper:]')_EXTRA_ARGS"
  env "$var=$*" "${DC[@]}" up -d --no-build --no-deps "$svc"
}

prune_check() {
  # FIC's node does not register -prune (TxIndex, which staking needs, cannot
  # prune). Record what an operator gets when they ask for it.
  local out
  out=$(docker run --rm fic-node:latest -testnet -prune=2000 -datadir=/tmp/prune-check 2>&1 || true)
  out=$(echo "$out" | tr -d '"' | tail -3 | tr '\n' ' ')
  tools record "{\"step\": \"prune\", \"args\": \"-testnet -prune=2000\", \"output\": \"$out\"}"
}

run_step() {
  case "$1" in
    fund) tools fund ;;
    spray) restart node1 -maxmempool=5; tools spray; restart node1 ;;
    reindex)
      tools reindex-before
      restart node2 -reindex
      tools reindex-after
      restart node2 ;;
    txindex) tools txindex ;;
    reorg) tools reorg ;;
    prune) prune_check ;;
    *) echo "unknown step: $1" >&2; exit 2 ;;
  esac
}

steps=("$@")
[ ${#steps[@]} -gt 0 ] || steps=(fund spray reindex txindex reorg prune)
for s in "${steps[@]}"; do
  echo "=== stress step: $s ($(date -u +%FT%TZ))"
  run_step "$s"
done
