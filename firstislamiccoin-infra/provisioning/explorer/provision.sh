#!/bin/bash
# FirstIslamicCoin block explorer provisioning script.
#
# Target: fresh Ubuntu 22.04/24.04 or Debian 12 VPS, with a fully-synced
# firstislamiccoind already running on it (or reachable via
# FIC_RPC_HOST/PORT) -- txindex is on by default on this fork, so no
# extra flag is needed for it. Idempotent -- safe to re-run.
#
# This service holds no keys and needs no persistent data directory --
# it's stateless, read-only RPC passthrough plus a static frontend.
#
# No default REPO_URL: no public FirstIslamicCoin GitHub org exists yet
# (see docs/CHANGELOG-FIC.md) -- set it once one does, or point SOURCE_DIR
# at a local checkout instead of cloning.
#
# Usage (as root or via sudo), authenticating either with the node's RPC
# cookie file (matches how firstislamiccoin-infra's own testnet nodes run,
# no fixed RPC password) or a fixed user/password:
#
#   REPO_URL=https://github.com/<org>/<repo>.git \
#   FIC_RPC_COOKIEFILE=/root/.firstislamiccoin/.cookie \
#   ./provision.sh
# or:
#   REPO_URL=... FIC_RPC_USER=explorerrpc FIC_RPC_PASSWORD=changeme ./provision.sh
#
# SOURCE_DIR=/path/to/checkout ./provision.sh skips the git clone/fetch step
# entirely and copies firstislamiccoin-explorer/ from there instead.

set -euo pipefail

REPO_URL="${REPO_URL:-}"
REPO_REF="${REPO_REF:-main}"
SOURCE_DIR="${SOURCE_DIR:-}"
FIC_RPC_HOST="${FIC_RPC_HOST:-127.0.0.1}"
FIC_RPC_PORT="${FIC_RPC_PORT:-19771}"  # mainnet; 29771 testnet
FIC_RPC_COOKIEFILE="${FIC_RPC_COOKIEFILE:-}"
FIC_RPC_USER="${FIC_RPC_USER:-}"
FIC_RPC_PASSWORD="${FIC_RPC_PASSWORD:-}"
EXPLORER_CORS_ORIGINS="${EXPLORER_CORS_ORIGINS:-*}"
FIC_USER="fic-explorer"
FIC_GROUP="fic-explorer"
BUILD_DIR="/opt/fic-explorer"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root (or with sudo)." >&2
    exit 1
fi
if [ -z "$SOURCE_DIR" ] && [ -z "$REPO_URL" ]; then
    echo "Set REPO_URL (a real FirstIslamicCoin repository) or SOURCE_DIR (a local checkout)." >&2
    exit 1
fi
if [ -z "$FIC_RPC_COOKIEFILE" ] && { [ -z "$FIC_RPC_USER" ] || [ -z "$FIC_RPC_PASSWORD" ]; }; then
    echo "Set FIC_RPC_COOKIEFILE, or both FIC_RPC_USER and FIC_RPC_PASSWORD." >&2
    exit 1
fi

echo "=== [1/6] Checking txindex is enabled ==="
# Best-effort check only -- firstislamiccoind may be on a different host
# (FIC_RPC_HOST != 127.0.0.1), in which case this just can't confirm it
# locally and the script proceeds anyway.
if [ "$FIC_RPC_HOST" = "127.0.0.1" ] && command -v firstislamiccoin-cli >/dev/null 2>&1; then
    if ! firstislamiccoin-cli getindexinfo 2>/dev/null | grep -q '"txindex"'; then
        echo "WARNING: txindex does not appear to be enabled on this node."
        echo "It is this fork's default, but if it was disabled, block/tx"
        echo "lookups by hash/txid will fail for anything not in the wallet."
    fi
fi

echo "=== [2/6] Installing system dependencies ==="
apt-get update
apt-get install -y python3 python3-venv python3-dev build-essential git

echo "=== [3/6] Creating service user ==="
if ! id "$FIC_USER" >/dev/null 2>&1; then
    useradd --system --create-home --shell /usr/sbin/nologin --user-group "$FIC_USER"
fi

echo "=== [4/6] Fetching explorer source ==="
if [ -n "$SOURCE_DIR" ]; then
    rm -rf "$BUILD_DIR"
    mkdir -p "$BUILD_DIR"
    cp -a "$SOURCE_DIR/firstislamiccoin-explorer" "$BUILD_DIR/explorer"
elif [ -d "$BUILD_DIR/.git" ]; then
    git -C "$BUILD_DIR" fetch --depth 1 origin "$REPO_REF"
    git -C "$BUILD_DIR" checkout FETCH_HEAD -- firstislamiccoin-explorer
    mv "$BUILD_DIR/firstislamiccoin-explorer" "$BUILD_DIR/explorer.new" && rm -rf "$BUILD_DIR/explorer" && mv "$BUILD_DIR/explorer.new" "$BUILD_DIR/explorer"
else
    rm -rf "$BUILD_DIR"
    git clone --depth 1 --branch "$REPO_REF" --no-checkout "$REPO_URL" "$BUILD_DIR"
    git -C "$BUILD_DIR" sparse-checkout set firstislamiccoin-explorer
    git -C "$BUILD_DIR" checkout "$REPO_REF"
    mv "$BUILD_DIR/firstislamiccoin-explorer" "$BUILD_DIR/explorer.new" && rm -rf "$BUILD_DIR/explorer" 2>/dev/null; mv "$BUILD_DIR/explorer.new" "$BUILD_DIR/explorer"
fi
BUILD_DIR="$BUILD_DIR/explorer"
chown -R "$FIC_USER:$FIC_GROUP" "$BUILD_DIR"

echo "=== [5/6] Building venv and writing config ==="
python3 -m venv "$BUILD_DIR/venv"
"$BUILD_DIR/venv/bin/pip" install --quiet --upgrade pip
"$BUILD_DIR/venv/bin/pip" install --quiet -r "$BUILD_DIR/requirements.txt"
{
    echo "FIC_RPC_HOST=$FIC_RPC_HOST"
    echo "FIC_RPC_PORT=$FIC_RPC_PORT"
    [ -n "$FIC_RPC_COOKIEFILE" ] && echo "FIC_RPC_COOKIEFILE=$FIC_RPC_COOKIEFILE"
    [ -n "$FIC_RPC_USER" ] && echo "FIC_RPC_USER=$FIC_RPC_USER"
    [ -n "$FIC_RPC_PASSWORD" ] && echo "FIC_RPC_PASSWORD=$FIC_RPC_PASSWORD"
    echo "EXPLORER_CORS_ORIGINS=$EXPLORER_CORS_ORIGINS"
} > /etc/fic-explorer.conf
chmod 640 /etc/fic-explorer.conf
chown "root:$FIC_GROUP" /etc/fic-explorer.conf

echo "=== [6/6] Installing systemd unit ==="
install -m 644 "$SCRIPT_DIR/explorer.service" /etc/systemd/system/explorer.service
sed -i "s|__BUILD_DIR__|$BUILD_DIR|g; s|__USER__|$FIC_USER|g; s|__GROUP__|$FIC_GROUP|g" \
    /etc/systemd/system/explorer.service
systemctl daemon-reload
systemctl enable explorer
systemctl restart explorer

echo ""
echo "Done. journalctl -u explorer -f to watch it. Serve explorer/index.html,"
echo "app.js, style.css as static files and reverse-proxy /api/ to"
echo "127.0.0.1:8081 -- see nginx-example.conf. app.js's API_BASE defaults"
echo "to that same origin's /api path when served this way (override via"
echo "localStorage 'fic_explorer_api' otherwise)."
