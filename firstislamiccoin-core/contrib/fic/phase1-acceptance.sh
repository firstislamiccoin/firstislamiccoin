#!/usr/bin/env bash
# Phase 1 acceptance on a real regtest node, outside the test framework:
# firstislamiccoind starts, reports the FIC genesis, stakes blocks from the
# genesis premine with proof of work disabled, getstakinginfo works, and the
# supply audit passes.
#
# Usage, from firstislamiccoin-core/ after building: contrib/fic/phase1-acceptance.sh [bindir]
# bindir defaults to ./src. Uses a throwaway datadir and regtest's default ports.
export LC_ALL=C
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
BIN=${1:-$ROOT/src}
# Regtest's genesis premine key is public by design (test_framework/fic.py).
WIF=cMup77fpH26t5EnVk7HtkNzhcBAbMaXCGFZxoUo6extVBqSSLhQM
EXPECTED_GENESIS=360afc3edc3e70f91452bbc7ece92fd4a18dbb9700aea612564636fadbd4e712
DATA=$(mktemp -d)
ARGS="-regtest -datadir=$DATA"
CLI="$BIN/firstislamiccoin-cli $ARGS"
# No -fallbackfee: this fork has no fallback fee estimation (fees follow GetMinFee),
# and an unregistered argument would stop the daemon from starting.
NODE_ARGS="$ARGS -lastpowblock=0 -txindex=1 -staking=1 -daemon"

json() { python3 -c "import sys, json; d = json.load(sys.stdin); print($1)"; }
wait_rpc() { for _ in $(seq 1 90); do $CLI getblockcount >/dev/null 2>&1 && return 0; sleep 1; done; echo "RPC never came up"; return 1; }
fail() { echo "ACCEPTANCE FAIL: $*"; $CLI stop >/dev/null 2>&1; exit 1; }

$BIN/firstislamiccoind $NODE_ARGS || fail "daemon did not start"
wait_rpc || fail "no RPC"

echo "=== getblockchaininfo ==="
$CLI getblockchaininfo | head -14
GOT=$($CLI getblockhash 0)
echo "genesis: $GOT"
[ "$GOT" = "$EXPECTED_GENESIS" ] || fail "genesis hash mismatch (expected $EXPECTED_GENESIS)"

echo "=== importing the regtest premine key and restarting with the wallet ==="
$CLI createwallet accept >/dev/null || fail "createwallet"
CHK=$($CLI getdescriptorinfo "combo($WIF)" | json 'd["checksum"]')
$CLI -rpcwallet=accept importdescriptors "[{\"desc\": \"combo($WIF)#$CHK\", \"timestamp\": 0}]" | json 'd[0]["success"]'
$CLI -rpcwallet=accept getbalances | json 'd["mine"]'
$CLI stop >/dev/null
for _ in $(seq 1 60); do [ -f "$DATA/regtest/firstislamiccoind.pid" ] || break; sleep 1; done
sleep 2
$BIN/firstislamiccoind $NODE_ARGS -wallet=accept || fail "daemon did not restart"
wait_rpc || fail "no RPC after restart"

echo "=== proof of work must be rejected ==="
POW=$($CLI -rpcwallet=accept generatetoaddress 1 "$($CLI -rpcwallet=accept getnewaddress)" 2>&1)
echo "$POW" | head -3
echo "$POW" | grep -q "reject-pow" || fail "proof-of-work block was not rejected"

echo "=== waiting for staked blocks ==="
for _ in $(seq 1 240); do
  [ "$($CLI getblockcount)" -ge 3 ] && break
  sleep 2
done
HEIGHT=$($CLI getblockcount)
echo "height: $HEIGHT"
[ "$HEIGHT" -ge 3 ] || fail "chain did not stake 3 blocks"

echo "=== getstakinginfo ==="
$CLI -rpcwallet=accept getstakinginfo || fail "getstakinginfo"

echo "=== block 1 ==="
$CLI getblock "$($CLI getblockhash 1)" 2 | json '{k: d[k] for k in ("height", "flags", "nTx")}'

echo "=== supply audit ==="
python3 "$ROOT/scripts/audit_premine_supply.py" --rpcport 39771 --rpccookiefile "$DATA/regtest/.cookie" --last-pow-block 0
AUDIT=$?

$CLI stop >/dev/null
[ $AUDIT -eq 0 ] || fail "supply audit"
echo "ACCEPTANCE PASS"
