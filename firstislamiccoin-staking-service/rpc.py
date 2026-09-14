"""Minimal JSON-RPC client for firstislamiccoind, matching
../firstislamiccoin-explorer/rpc.py's two auth modes (cookie file or
fixed user/password) plus CAC's vps-gateway/rpc.py's per-wallet path
routing (this service, unlike the explorer, holds real private keys in
named wallets -- see staking.py/referral.py).

Configuration is via environment variables:
    FIC_RPC_HOST, FIC_RPC_PORT
    FIC_RPC_COOKIEFILE          (preferred if set)
    FIC_RPC_USER, FIC_RPC_PASSWORD   (used if no cookie file)
    FIC_RPC_WALLET              (default wallet context; usually left
                                  unset here since callers pass wallet=
                                  explicitly per call -- see app.py)
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
RPC_WALLET = os.environ.get("FIC_RPC_WALLET", "")


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
    raise RpcError(-1, "Gateway is not configured (set FIC_RPC_COOKIEFILE, or FIC_RPC_USER/FIC_RPC_PASSWORD)")


def call(method, params=None, wallet=None):
    auth = _auth_header()
    path = "/"
    w = RPC_WALLET if wallet is None else wallet
    if w:
        path = f"/wallet/{w}"
    payload = json.dumps({"jsonrpc": "1.0", "id": "gateway", "method": method, "params": params or []})
    conn = http.client.HTTPConnection(RPC_HOST, RPC_PORT, timeout=30)
    try:
        conn.request("POST", path, payload, {"Content-Type": "application/json", "Authorization": auth})
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
