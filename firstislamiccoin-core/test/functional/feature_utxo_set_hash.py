#!/usr/bin/env python3
# Copyright (c) 2020-2022 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test UTXO set hash value calculation in gettxoutsetinfo."""

import struct

from test_framework.messages import (
    CBlock,
    COutPoint,
    from_rpc_hex,
)
from test_framework.muhash import MuHash3072
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import assert_equal
from test_framework.wallet import MiniWallet

class UTXOSetHashTest(BitcoinTestFramework):
    def set_test_params(self):
        self.num_nodes = 1
        self.setup_clean_chain = True

    def test_muhash_implementation(self):
        self.log.info("Test MuHash implementation consistency")

        node = self.nodes[0]
        wallet = MiniWallet(node)
        mocktime = node.getblockheader(node.getblockhash(0))['time'] + 1
        node.setmocktime(mocktime)

        # Generate 100 blocks and remove the first since we plan to spend its
        # coinbase
        block_hashes = self.generate(wallet, 1) + self.generate(node, 99)
        blocks = list(map(lambda block: from_rpc_hex(CBlock(), node.getblock(block, False)), block_hashes))
        blocks.pop(0)

        # Create a spending transaction and mine a block which includes it
        txid = wallet.send_self_transfer(from_node=node)['txid']
        tx_block = self.generateblock(node, output=wallet.get_address(), transactions=[txid])
        blocks.append(from_rpc_hex(CBlock(), node.getblock(tx_block['hash'], False)))

        # Serialize the outputs that should be in the UTXO set and add them to
        # a MuHash object
        muhash = MuHash3072()

        # FirstIslamicCoin: unlike Bitcoin, the genesis coinbase outputs (the premine) are part of the UTXO set
        genesis_tx = from_rpc_hex(CBlock(), node.getblock(node.getblockhash(0), False)).vtx[0]
        for n, tx_out in enumerate(genesis_tx.vout):
            data = COutPoint(int(genesis_tx.rehash(), 16), n).serialize()
            data += struct.pack("<i", 0 * 2 + 1)
            data += tx_out.serialize()
            muhash.insert(data)

        for height, block in enumerate(blocks):
            # We spent the coinbase of the first mined block (height 1)
            height += 2

            for tx in block.vtx:
                for n, tx_out in enumerate(tx.vout):
                    coinbase = 1 if not tx.vin[0].prevout.hash else 0

                    # Skip witness commitment
                    if (coinbase and n > 0):
                        continue

                    data = COutPoint(int(tx.rehash(), 16), n).serialize()
                    data += struct.pack("<i", height * 2 + coinbase)
                    data += tx_out.serialize()

                    muhash.insert(data)

        finalized = muhash.digest()
        node_muhash = node.gettxoutsetinfo("muhash")['muhash']

        assert_equal(finalized[::-1].hex(), node_muhash)

        self.log.info("Test deterministic UTXO set hash results")
        # FirstIslamicCoin: values differ from Bitcoin (premine outputs, 28,000,000 subsidy, scrypt/regtest params)
        assert_equal(node.gettxoutsetinfo()['hash_serialized_3'], "7ddcd239551a70aba65e7c7b38d83136370fcab7d1d0b6b51955934be5b8d966")
        assert_equal(node.gettxoutsetinfo("muhash")['muhash'], "6a17e3306b89ee62f2b4386571a8666fde13cd668e82dc296adfaa8b9d88b4a0")

    def run_test(self):
        self.test_muhash_implementation()


if __name__ == '__main__':
    UTXOSetHashTest().main()
