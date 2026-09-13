"""Minimal JSON-RPC client for the testnet containers.

Authenticates with each node's cookie file, mounted read-only at
/data/<node>/<chain dir>/.cookie, and re-reads it on every call so node
restarts are transparent. Amounts go out as strings (the node accepts them)
and come back as Decimal, so 14,000,000,000.00000000-scale values never pass
through a float.
"""
import base64
import decimal
import glob
import http.client
import json
import sys
import time
import urllib.parse

COIN_PLACES = decimal.Decimal("0.00000001")
RPC_PORT = 29771
NODES = ["node0", "node1", "node2", "node3"]


class RPCError(Exception):
    def __init__(self, method, error):
        super().__init__(f"{method}: {error.get('message')} ({error.get('code')})")
        self.code = error.get("code")
        self.message = error.get("message")


def log(*args):
    print(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), *args, flush=True)


def _encode(obj):
    if isinstance(obj, decimal.Decimal):
        return str(obj.quantize(COIN_PLACES))
    raise TypeError(f"cannot encode {type(obj)}")


class Node:
    def __init__(self, name, wallet=None):
        self.name = name
        self.wallet = wallet

    def w(self, wallet):
        return Node(self.name, wallet)

    def _auth(self):
        cookies = glob.glob(f"/data/{self.name}/*/.cookie")
        if not cookies:
            raise ConnectionError(f"{self.name}: no cookie file yet")
        token = open(cookies[0]).read().strip()
        return "Basic " + base64.b64encode(token.encode()).decode()

    def call(self, method, *params, timeout=600, retry_for=300):
        path = "/" if self.wallet is None else "/wallet/" + urllib.parse.quote(self.wallet)
        body = json.dumps({"jsonrpc": "1.0", "id": method, "method": method, "params": list(params)}, default=_encode)
        deadline = time.time() + retry_for
        while True:
            try:
                conn = http.client.HTTPConnection(self.name, RPC_PORT, timeout=timeout)
                conn.request("POST", path, body, {"Authorization": self._auth(), "Content-Type": "application/json"})
                resp = conn.getresponse()
                raw = resp.read()
                conn.close()
                if resp.status == 401:
                    raise ConnectionError(f"{self.name}: unauthorized (cookie rotated?)")
                data = json.loads(raw, parse_float=decimal.Decimal)
                # -28: warming up (loading block index, verifying blocks, rescanning)
                if data.get("error") and data["error"].get("code") == -28 and time.time() < deadline:
                    time.sleep(3)
                    continue
                if data.get("error"):
                    raise RPCError(method, data["error"])
                return data["result"]
            except (ConnectionError, OSError, http.client.HTTPException, json.JSONDecodeError) as e:
                if time.time() >= deadline:
                    raise
                time.sleep(3)

    def __getattr__(self, method):
        if method.startswith("_"):
            raise AttributeError(method)
        return lambda *params, **kw: self.call(method, *params, **kw)


def nodes():
    return {n: Node(n) for n in NODES}


def wait_for(predicate, what, timeout, interval=10):
    deadline = time.time() + timeout
    while True:
        result = predicate()
        if result:
            return result
        if time.time() >= deadline:
            log(f"timed out waiting for {what}")
            sys.exit(1)
        time.sleep(interval)
