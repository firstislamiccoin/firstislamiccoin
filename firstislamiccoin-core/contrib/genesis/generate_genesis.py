#!/usr/bin/env python3
# Copyright (c) 2026 The FirstIslamicCoin developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Mine a FirstIslamicCoin genesis block.

The genesis coinbase carries the whole premine as N equal outputs (see
docs/genesis.md for why it is split rather than a single output). This tool
serializes that coinbase exactly as src/kernel/chainparams.cpp's
CreateGenesisBlock() does, brute-forces nNonce against the scrypt PoW hash,
and prints the values to paste into chainparams.cpp.

Serialization is not taken on trust: --self-test rebuilds CodexaCoin's live
genesis blocks from their published parameters and checks every hash, which
exercises the coinbase, merkle root, header hash (SHA256d) and PoW hash
(scrypt) code paths. The node itself also assert()s the resulting hashes at
startup, so a mistake here cannot silently ship.

Usage:
  generate_genesis.py --self-test
  generate_genesis.py --network regtest --time 1789171200 --bits 207fffff \\
      --script 76a914...88ac
"""

import argparse
import hashlib
import multiprocessing
import os
import struct
import sys

COIN = 100_000_000
FIC_PHRASE = ("FirstIslamicCoin 12/Sep/2026 — Bismillah, the first "
              "Shariah-conscious Proof-of-Stake network")
GENESIS_VERSION = 7  # CheckBlockHeader rejects nVersion < 7 after ProtocolV2
MAX_COINBASE_SCRIPTSIG = 100  # consensus/tx_check.cpp
CHUNK = 4096


def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def compact_size(n: int) -> bytes:
    if n < 0xfd:
        return bytes([n])
    if n <= 0xffff:
        return b"\xfd" + struct.pack("<H", n)
    if n <= 0xffffffff:
        return b"\xfe" + struct.pack("<I", n)
    return b"\xff" + struct.pack("<Q", n)


def push_data(data: bytes) -> bytes:
    """CScript::operator<<(span): minimal push opcode for raw bytes."""
    n = len(data)
    if n < 0x4c:
        return bytes([n]) + data
    if n <= 0xff:
        return b"\x4c" + bytes([n]) + data
    if n <= 0xffff:
        return b"\x4d" + struct.pack("<H", n) + data
    return b"\x4e" + struct.pack("<I", n) + data


def script_num(value: int) -> bytes:
    """CScriptNum::serialize."""
    if value == 0:
        return b""
    neg = value < 0
    absval = -value if neg else value
    out = bytearray()
    while absval:
        out.append(absval & 0xff)
        absval >>= 8
    if out[-1] & 0x80:
        out.append(0x80 if neg else 0)
    elif neg:
        out[-1] |= 0x80
    return bytes(out)


def coinbase_script_sig(phrase: bytes) -> bytes:
    # CScript() << 0 << CScriptNum(42) << phrase
    return b"\x00" + push_data(script_num(42)) + push_data(phrase)


def serialize_coinbase(n_time: int, script_sig: bytes, outputs) -> bytes:
    # nVersion 1 < 2, so SerializeTransaction writes nTime after nVersion.
    tx = struct.pack("<i", 1) + struct.pack("<I", n_time)
    tx += compact_size(1)
    tx += b"\x00" * 32 + struct.pack("<I", 0xffffffff)
    tx += compact_size(len(script_sig)) + script_sig
    tx += struct.pack("<I", 0xffffffff)
    tx += compact_size(len(outputs))
    for value, script in outputs:
        tx += struct.pack("<q", value) + compact_size(len(script)) + script
    tx += struct.pack("<I", 0)  # nLockTime
    return tx


def header_prefix(version: int, merkle_root: bytes, n_time: int, n_bits: int) -> bytes:
    """The 76 header bytes before nNonce."""
    return (struct.pack("<i", version) + b"\x00" * 32 + merkle_root +
            struct.pack("<II", n_time, n_bits))


def target_from_compact(n_bits: int) -> int:
    exponent = n_bits >> 24
    mantissa = n_bits & 0x007fffff
    if exponent <= 3:
        return mantissa >> (8 * (3 - exponent))
    return mantissa << (8 * (exponent - 3))


def pow_hash(header: bytes) -> bytes:
    # GetPoWHash(): scrypt_1024_1_1_256 over the 80-byte header.
    return hashlib.scrypt(header, salt=header, n=1024, r=1, p=1, dklen=32)


def display(h: bytes) -> str:
    return h[::-1].hex()


def search(args):
    prefix, start, target = args
    for nonce in range(start, min(start + CHUNK, 1 << 32)):
        header = prefix + struct.pack("<I", nonce)
        if int.from_bytes(pow_hash(header), "little") <= target:
            return nonce
    return None


def build(phrase: bytes, n_time: int, n_bits: int, outputs, version=GENESIS_VERSION):
    script_sig = coinbase_script_sig(phrase)
    if not 2 <= len(script_sig) <= MAX_COINBASE_SCRIPTSIG:
        sys.exit(f"coinbase scriptSig is {len(script_sig)} bytes; consensus allows 2..100")
    coinbase = serialize_coinbase(n_time, script_sig, outputs)
    merkle_root = sha256d(coinbase)  # single transaction: merkle root == txid
    return script_sig, merkle_root, header_prefix(version, merkle_root, n_time, n_bits)


def mine(prefix: bytes, target: int, workers: int) -> int:
    with multiprocessing.Pool(workers) as pool:
        starts = ((prefix, s, target) for s in range(0, 1 << 32, CHUNK))
        for i, found in enumerate(pool.imap(search, starts, chunksize=1)):
            if found is not None:
                pool.terminate()
                return found
            if i and i % 256 == 0:
                print(f"  ... {i * CHUNK:,} nonces tried", file=sys.stderr)
    sys.exit("nonce space exhausted; choose a different nTime")


def self_test() -> None:
    """Rebuild known genesis blocks from their published parameters and check every hash.

    CodexaCoin's genesis output has an EMPTY scriptPubKey: its
    CreateGenesisBlock() built a P2PK script but never assigned it to the
    output. Blackcoin's has an empty output too, and a version-1 header, whose
    GetHash() is the scrypt PoW hash -- so that case exercises scrypt directly.
    """
    ok = True

    def check(label, good, detail):
        nonlocal ok
        ok &= good
        print(f"{'PASS' if good else 'FAIL'}  {label}: {detail}")

    cac_phrase = b"CNBC 29/Jul/2026 Fed meeting recap: July 2026"
    cac_merkle = "089c9664d716a35a805093b15b0dd6e9f58e84ca21a176c2783a377d23ef6b22"
    for name, nonce, bits, want_hash in [
        ("mainnet", 2473299, 0x1e0fffff, "ecf4dfc81beeb2a992ee169e1fc349144e48108d7a03f7fb6d619c2bd845038e"),
        ("testnet", 73100, 0x1f00ffff, "719ff8d5c4773340ff014d12c0bbc623aa6fc2abc2b4ecd6dc7e93ef4f609b95"),
        ("regtest", 1, 0x207fffff, "66a3b7f4db8f62053c717aab1d5ff9fa8cfed4f7b27f2583b438ee8f4c9c12d1"),
    ]:
        _, merkle, prefix = build(cac_phrase, 1785326400, bits, [(0, b"")])
        header = prefix + struct.pack("<I", nonce)
        got_hash = display(sha256d(header))
        pow_ok = int.from_bytes(pow_hash(header), "little") <= target_from_compact(bits)
        check(f"CAC {name}", display(merkle) == cac_merkle and got_hash == want_hash and pow_ok,
              f"hash={got_hash} merkle={display(merkle)} pow={'ok' if pow_ok else 'BAD'}")

    blk_phrase = b"20 Feb 2014 Bitcoin ATMs come to USA"
    _, merkle, prefix = build(blk_phrase, 1393221600, 0x1e0fffff, [(0, b"")], version=1)
    got_hash = display(pow_hash(prefix + struct.pack("<I", 164482)))
    check("Blackcoin mainnet",
          display(merkle) == "12630d16a97f24b287c8c2594dda5fb98c9e6c70fc61d44191931ea2aa08dc90"
          and got_hash == "000001faef25dec4fbcf906e6242621df2c183bf232f263d0ba5b101911e4563",
          f"hash={got_hash} merkle={display(merkle)}")

    if not ok:
        sys.exit("self-test failed: serialization does not match the node")
    print("self-test passed: serialization matches CodexaCoin's and Blackcoin's genesis blocks")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--network", default="mainnet", help="label for the output only")
    ap.add_argument("--time", type=int, default=1789171200)
    ap.add_argument("--bits", type=lambda s: int(s, 16), default=0x1e0fffff)
    ap.add_argument("--phrase", default=FIC_PHRASE)
    ap.add_argument("--script", help="premine output scriptPubKey, hex")
    ap.add_argument("--outputs", type=int, default=1000, help="number of equal premine outputs")
    ap.add_argument("--premine", type=int, default=14_000_000_000, help="total premine, whole coins")
    ap.add_argument("--nonce", type=int, help="verify this nonce instead of mining")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return
    if not args.script:
        ap.error("--script is required unless --self-test")

    total = args.premine * COIN
    if total % args.outputs:
        sys.exit(f"premine {total} sat does not divide evenly into {args.outputs} outputs")
    script = bytes.fromhex(args.script)
    outputs = [(total // args.outputs, script)] * args.outputs
    phrase = args.phrase.encode("utf-8")

    script_sig, merkle, prefix = build(phrase, args.time, args.bits, outputs)
    target = target_from_compact(args.bits)
    print(f"Genesis for {args.network}: nTime={args.time} nBits=0x{args.bits:08x} "
          f"outputs={args.outputs} x {total // args.outputs / COIN:,.8f}")
    print(f"  phrase {len(phrase)} bytes, scriptSig {len(script_sig)}/{MAX_COINBASE_SCRIPTSIG} bytes")

    nonce = args.nonce if args.nonce is not None else mine(prefix, target, args.workers)
    header = prefix + struct.pack("<I", nonce)
    if int.from_bytes(pow_hash(header), "little") > target:
        sys.exit(f"nonce {nonce} does not satisfy nBits 0x{args.bits:08x}")

    print(f"  nNonce           = {nonce}")
    print(f"  hashGenesisBlock = 0x{display(sha256d(header))}")
    print(f"  hashMerkleRoot   = 0x{display(merkle)}")


if __name__ == "__main__":
    main()
