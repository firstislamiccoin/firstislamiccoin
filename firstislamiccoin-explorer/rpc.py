"""Minimal JSON-RPC client for firstislamiccoind.

FirstIslamicCoin: supports two auth modes, unlike CodexaCoin's explorer
(fixed RPC_USER/RPC_PASSWORD only): a cookie file (FIC_RPC_COOKIEFILE),
re-read on every call so a node restart is transparent, or a fixed
user/password. Cookie auth matches how firstislamiccoin-infra's testnet
nodes are actually run (no fixed RPC password -- see
firstislamiccoin-infra/docker-compose.testnet.yml); fixed user/password
remains for a typical mainnet deployment where an operator sets
-rpcuser/-rpcpassword deliberately. Otherwise identical in shape to
CodexaCoin's explorer/rpc.py and vps-gateway/rpc.py, kept as its own small
module rather than a shared library for the same reason those are: each
service here is deliberately independently deployable.

No RPC_WALLET default: the explorer only ever calls wallet-agnostic RPCs
(getblock, getrawtransaction, scantxoutset, etc.) -- it holds no keys and
needs no wallet context, which is the point of this being a separate,
lower-trust service from any future staking-service backend.

Configuration is via environment variables:
    FIC_RPC_HOST, FIC_RPC_PORT
    FIC_RPC_COOKIEFILE          (preferred if set)
    FIC_RPC_USER, FIC_RPC_PASSWORD   (used if no cookie file)
"""
import http.client
import json
import os
from base64 import b64encode

RPC_HOST = os.environ.get("FIC_RPC_HOST", "127.0.0.1")
RPC_PORT = int(os.environ.get("FIC_RPC_PORT", "29771"))  # testnet default; 19771 mainnet
RPC_COOKIEFILE = os.environ.get("FIC_RPC_COOKIEFILE")
RPC_USER = os.environ.get("FIC_RPC_USER")
RPC_PASSWORD = os.environ.get("FIC_RPC_PASSWORD")


class RpcError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _auth_header():
    if RPC_COOKIEFILE:
        try:
            token = open(RPC_COOKIEFILE).read().strip()
        except OSError as e:
            raise RpcError(-1, f"Cannot read RPC cookie file {RPC_COOKIEFILE}: {e}")
        return "Basic " + b64encode(token.encode()).decode()
    if RPC_USER and RPC_PASSWORD:
        return "Basic " + b64encode(f"{RPC_USER}:{RPC_PASSWORD}".encode()).decode()
    raise RpcError(-1, "Explorer is not configured (set FIC_RPC_COOKIEFILE, or FIC_RPC_USER/FIC_RPC_PASSWORD)")


def call(method, params=None):
    auth = _auth_header()
    payload = json.dumps({"jsonrpc": "1.0", "id": "explorer", "method": method, "params": params or []})
    conn = http.client.HTTPConnection(RPC_HOST, RPC_PORT, timeout=30)
    try:
        conn.request("POST", "/", payload, {"Content-Type": "application/json", "Authorization": auth})
        resp = conn.getresponse()
        body = json.loads(resp.read())
    except (OSError, json.JSONDecodeError) as e:
        raise RpcError(-1, f"RPC request failed: {e}")
    finally:
        conn.close()
    if resp.status == 401:
        raise RpcError(-1, "RPC authentication failed (stale cookie or wrong credentials)")
    if body.get("error"):
        err = body["error"]
        raise RpcError(err.get("code"), err.get("message"))
    return body["result"]
