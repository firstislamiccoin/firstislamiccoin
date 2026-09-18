#!/usr/bin/env python3
# Copyright (c) 2019-2022 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test basic signet functionality"""

from decimal import Decimal

from test_framework.authproxy import JSONRPCException
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import assert_equal

# FirstIslamicCoin: upstream hardcodes 10 real historical blocks from the
# actual public Bitcoin default signet chain here. Those blocks' coinbase
# transactions have nVersion=1, and this fork's transaction deserializer
# reads an extra 4-byte nTime field whenever nVersion<2 (see
# CTransaction::(De)Serialize in src/primitives/transaction.h -- a
# permanent, intentional Peercoin/PoS-style design difference, not a
# upstream-parity bug). Reading upstream's raw bytes with that extra field
# misinterprets the segwit marker/flag as part of a timestamp and corrupts
# everything after it, so IsCoinBase() fails and submitblock rejects with
# -22 "Block does not start with a coinbase".
#
# We also don't have -- and can never obtain -- the private keys behind the
# real default signet challenge's two pubkeys
# (03ad5e0edad18cb1f0fc0d28a3d4f1f3e445640337489abb10404f2d1e086be4 /
# 0359ef5021964fe22d6f8e05b2463c9540ce96883fe3b278760f048f5189f2e6, see
# SigNetParams in src/kernel/chainparams.cpp), so we cannot forge new
# signatures for that exact challenge either.
#
# Instead these 10 blocks are a real, fork-native signet chain we mined and
# signed ourselves (nVersion=2 transactions, genuine scrypt PoW under this
# fork's actual signet consensus difficulty -- no shortcuts) using this
# fork's own contrib/signet/miner, for a single-key p2wpkh challenge
# ("0014c46c97834f6a1a27794af382f97a241fdcbde98b") controlled by the
# throwaway test-only private key int 1001 (privkey.set((1001).to_bytes(32,
# 'big'), True) via test_framework.key.ECKey, same pattern as
# tool_signet_miner.py's CHALLENGE_PRIVATE_KEY). This exercises the same
# coverage as upstream: a real multi-block chain accepted one block at a
# time via submitblock, on a challenge type distinct from both the OP_TRUE
# network (nodes 0/1) and the mandatory 2-of-2 multisig network (nodes 4/5)
# below, so it still demonstrates cross-signet incompatibility
# ('bad-signet-blksig') when replayed against the latter.
signet_blocks = [
    '00000020ed7a8fb1acc3a4057907fccc7d0680aa3cc38e50cb3a4ee9bd97bbcbfff828a05eea70c908c4f34a35e33ebc9fb0510d4d415234c91988b369b14677cfd6e76df8d5ac6affff001fb335000001020000000001010000000000000000000000000000000000000000000000000000000000000000ffffffff025151feffffff0200000000000000001976a914ba969fba71846b815bc201d77167c15a2b8e2b5d88ac0000000000000000986a24aa21a9ede2f61c3f71d1defd3fa999dfa36953755c690689799962b48bebd836974e8cf94c70ecc7daa200024730440220541e3e0e42982a6d4b3d90bc11e895825fef96373d24678f6faf88fc877c69340220319e472d451eb2c355a5a6a177e124b9756a130e3c0b52131b4e3f2a969778e10121039d1abaec9f5715a15c7628244170951e0f85e87f68ca5393d3f9fc3fa23a69c8012000000000000000000000000000000000000000000000000000000000000000000000000000',
    '000000209a7106ba937ddb141cd2670fbcb86676720960b6693d270a3d3ad4dc504dac3c8f5407ee2558e3ec14b02dd301c400bfe3870a799354db57c54e0724664fcfacfbd5ac6affff001f39cc000001020000000001010000000000000000000000000000000000000000000000000000000000000000ffffffff025251feffffff0200000000000000001976a914ba969fba71846b815bc201d77167c15a2b8e2b5d88ac0000000000000000986a24aa21a9ede2f61c3f71d1defd3fa999dfa36953755c690689799962b48bebd836974e8cf94c70ecc7daa20002473044022035dd21d045c0fcc085c9a5093057823f79456dc4761ae1fed6b00e1b7c9afdca022073b5fa1b8b0b6984b42a20a6208f76703c224077d7919d6ede5750e52d045dae0121039d1abaec9f5715a15c7628244170951e0f85e87f68ca5393d3f9fc3fa23a69c8012000000000000000000000000000000000000000000000000000000000000000000000000000',
    '000000208542a1d944b8f2140fc40044e02cd4c0cf0fdab5d1cbc17413ae8931325572c741f77f1e822f7c256d9698f654c9876eab8fb5ab3fb25e20579bccbe7d0661c002d6ac6a7fe1001f5f40020001020000000001010000000000000000000000000000000000000000000000000000000000000000ffffffff025351feffffff0200000000000000001976a914ba969fba71846b815bc201d77167c15a2b8e2b5d88ac0000000000000000986a24aa21a9ede2f61c3f71d1defd3fa999dfa36953755c690689799962b48bebd836974e8cf94c70ecc7daa20002473044022010ba62dd362eca9ea547af66475f2e6385a8b87aa4f2520aabbc550b8021e28d0220195eaf1866daadb7992fa0dede011f9418ad0c74a5d9e2627e6eb20d33a6a0c10121039d1abaec9f5715a15c7628244170951e0f85e87f68ca5393d3f9fc3fa23a69c8012000000000000000000000000000000000000000000000000000000000000000000000000000',
    '0000002019bb8ecc69a1f5b64f8a49a2556b6694a375a86970fe01cf284ebd24cc19e3ba4f8a1ac32e1c71b84fad1defb269c24f60f5ad38c4a897456d96d3ccaf1cbade11d6ac6a64c8001f9d24000001020000000001010000000000000000000000000000000000000000000000000000000000000000ffffffff025451feffffff0200000000000000001976a914ba969fba71846b815bc201d77167c15a2b8e2b5d88ac0000000000000000986a24aa21a9ede2f61c3f71d1defd3fa999dfa36953755c690689799962b48bebd836974e8cf94c70ecc7daa20002473044022036274ced4c797073433527c2b21d915defe52fa5e58ee53ed11ab1fa605407bf022070dcf4e7f96bc35212cd6fcb41af3139e0895f58614f42fa89a8e7a8502159b10121039d1abaec9f5715a15c7628244170951e0f85e87f68ca5393d3f9fc3fa23a69c8012000000000000000000000000000000000000000000000000000000000000000000000000000',
    '00000020cfcabbc0d3bd8fcc2d0fbb4cb83f7d4e5e98a9632caaad0088096325d37c75e0a8e5150ad94648b207c1af23eec2ae1ccc50ff110e25fd80d39bec758c53468614d6ac6a36b5001f4d57000001020000000001010000000000000000000000000000000000000000000000000000000000000000ffffffff025551feffffff0200000000000000001976a914ba969fba71846b815bc201d77167c15a2b8e2b5d88ac0000000000000000986a24aa21a9ede2f61c3f71d1defd3fa999dfa36953755c690689799962b48bebd836974e8cf94c70ecc7daa20002473044022007f8ca2ba6876fe684eb67427c96db9446f51656ed6104c852111ff38751591302203f489704f2a038f5928862202c82f611d72270bebe850d7222674f25b68a24d40121039d1abaec9f5715a15c7628244170951e0f85e87f68ca5393d3f9fc3fa23a69c8012000000000000000000000000000000000000000000000000000000000000000000000000000',
    '00000020fdeb6b6b547ef4ce41306efd21147d72667e6f88af750dfbf1877a15629267454f6b8b615b136ea308d8cfd74d0dc83c55302409cb744ef9377928c179affb0117d6ac6a9f9f001f42fc000001020000000001010000000000000000000000000000000000000000000000000000000000000000ffffffff025651feffffff0200000000000000001976a914ba969fba71846b815bc201d77167c15a2b8e2b5d88ac0000000000000000986a24aa21a9ede2f61c3f71d1defd3fa999dfa36953755c690689799962b48bebd836974e8cf94c70ecc7daa2000247304402201402391bd88204cc8c5795c7947c44e057bd0c818e57b4f16cbee56ddb669e4002205f3a158f311ddfbb2ced18e3c3df60a52b00d9b0d2e114463ce2261f083101ce0121039d1abaec9f5715a15c7628244170951e0f85e87f68ca5393d3f9fc3fa23a69c8012000000000000000000000000000000000000000000000000000000000000000000000000000',
    '000000208a7ed557aef35ba16d0b46cb8e21ea8c78434f44cc0adbc3afa71b98f62c3758bd2522d35d51f95db2f459a4267e2ed8c1cba886c5e08c5dea525203e25f252c1fd6ac6a9a8c001f6559020001020000000001010000000000000000000000000000000000000000000000000000000000000000ffffffff025751feffffff0200000000000000001976a914ba969fba71846b815bc201d77167c15a2b8e2b5d88ac0000000000000000986a24aa21a9ede2f61c3f71d1defd3fa999dfa36953755c690689799962b48bebd836974e8cf94c70ecc7daa20002473044022071488a5d6c57f068789a09ff07240e65790ca074131675cc587d7a9d01f68332022062e6679f2e17f5c4b9a73b6366ac140ca6e7af36e6ccc22c72017ae81dea09d10121039d1abaec9f5715a15c7628244170951e0f85e87f68ca5393d3f9fc3fa23a69c8012000000000000000000000000000000000000000000000000000000000000000000000000000',
    '00000020588e85cc62962510e482a2f9f118285426d06779faa90932c2651378d7e25a6cb58ebe8480c863b1065234fbbd531779e8e3fdc50e5ae3c2053675ca47b049c531d6ac6a28397d1eee48070001020000000001010000000000000000000000000000000000000000000000000000000000000000ffffffff025851feffffff0200000000000000001976a914ba969fba71846b815bc201d77167c15a2b8e2b5d88ac0000000000000000986a24aa21a9ede2f61c3f71d1defd3fa999dfa36953755c690689799962b48bebd836974e8cf94c70ecc7daa200024730440220489531d8b9be4a3cef1c4e09e2cdddd6e89cc2545e96018908fa0635b9d3c356022017c187861b609f8542db1648f2492c9ae7cf243a61c1c1b9505e842fb1099cf90121039d1abaec9f5715a15c7628244170951e0f85e87f68ca5393d3f9fc3fa23a69c8012000000000000000000000000000000000000000000000000000000000000000000000000000',
    '00000020fd3c23ce9849948979a8c3dd5003d9d8af4b593c357972db031c0a5e1869c5e95658e2b88cf286177a7bc8b65cae5db6b3147e788930b5c91b3d05da6ee5cac85cd6ac6a05f9711e220b000001020000000001010000000000000000000000000000000000000000000000000000000000000000ffffffff025951feffffff0200000000000000001976a914ba969fba71846b815bc201d77167c15a2b8e2b5d88ac0000000000000000986a24aa21a9ede2f61c3f71d1defd3fa999dfa36953755c690689799962b48bebd836974e8cf94c70ecc7daa2000247304402203a6ed6f37939bd21428fafdcfda2902171700f0865d5e2ada33f6e942f20f91302200e66384f9b078ca8c96e26261c0a8033c17313bf967603541d610674dacb03c80121039d1abaec9f5715a15c7628244170951e0f85e87f68ca5393d3f9fc3fa23a69c8012000000000000000000000000000000000000000000000000000000000000000000000000000',
    '000000202f91dbe41df1ff7cfe3cbc8891051f9480eb567afc2ad80e1b0f21ec1275462e565a504440ec187c20fa139ae63eb228e97762c0abee847144e846568aeca7505fd6ac6a4e4c6d1e72fa020001020000000001010000000000000000000000000000000000000000000000000000000000000000ffffffff025a51feffffff0200000000000000001976a914ba969fba71846b815bc201d77167c15a2b8e2b5d88ac0000000000000000986a24aa21a9ede2f61c3f71d1defd3fa999dfa36953755c690689799962b48bebd836974e8cf94c70ecc7daa2000247304402202b5d0e0b39cba1c431ad593d3718638d90bf57b124f199106340f06dfc2e262902204745f6c929416fbb285b2e618c08bad55c7248448c5e839bcc5904e997c4c55d0121039d1abaec9f5715a15c7628244170951e0f85e87f68ca5393d3f9fc3fa23a69c8012000000000000000000000000000000000000000000000000000000000000000000000000000',
]


class SignetBasicTest(BitcoinTestFramework):
    def set_test_params(self):
        self.chain = "signet"
        self.num_nodes = 6
        self.setup_clean_chain = True
        # FirstIslamicCoin: consensus-level PoW here is scrypt (see
        # CBlockHeader::GetPoWHash() in src/primitives/block.cpp), not
        # upstream's sha256d, but signet's powLimit (src/kernel/chainparams.cpp)
        # is still calibrated for real Bitcoin's much faster sha256d hashrate.
        # Mining a single block at this difficulty genuinely takes several
        # minutes on reference hardware (~3m14s observed), which blows past
        # the framework's default 60s RPC socket timeout (test_framework/
        # authproxy.py's HTTP_TIMEOUT, applied via self.rpc_timeout) well
        # before the blocking `generate` RPC call can return. Changing
        # signet's powLimit itself is out of scope here, so just give RPC
        # calls in this test enough real wall-clock time to complete, with
        # comfortable margin for VPS load variance (same pattern as e.g.
        # feature_dbcrash.py's self.rpc_timeout = 480 for its own
        # long-running RPC calls).
        self.rpc_timeout = 600
        shared_args1 = ["-signetchallenge=51"]  # OP_TRUE
        # FirstIslamicCoin: upstream leaves this as [] to use the real
        # chainparams.cpp default signet challenge (a 1-of-2 multisig over
        # two specific pubkeys). We can't sign new blocks for that -- the
        # private keys belong to the actual Bitcoin signet operators and
        # were never ours to have -- so instead this network uses an
        # explicit single-key p2wpkh challenge whose private key we do
        # control, matching the challenge signet_blocks above was actually
        # mined and signed against. See signet_blocks' comment for details.
        shared_args2 = ["-signetchallenge=0014c46c97834f6a1a27794af382f97a241fdcbde98b"]
        # we use a different challenge (2-of-2 multisig, unrelated to the p2wpkh
        # key above), which means blocks valid on shared_args2 should fail here
        shared_args3 = ["-signetchallenge=522103ad5e0edad18cb1f0fc0d28a3d4f1f3e445640337489abb10404f2d1e086be430210359ef5021964fe22d6f8e05b2463c9540ce96883fe3b278760f048f5189f2e6c452ae"]

        self.extra_args = [
            shared_args1, shared_args1,
            shared_args2, shared_args2,
            shared_args3, shared_args3,
        ]

    def setup_network(self):
        self.setup_nodes()

        # Setup the three signets, which are incompatible with each other
        self.connect_nodes(0, 1)
        self.connect_nodes(2, 3)
        self.connect_nodes(4, 5)

    def run_test(self):
        self.log.info("basic tests using OP_TRUE challenge")

        self.log.info('getmininginfo')
        mining_info = self.nodes[0].getmininginfo()
        assert_equal(mining_info['blocks'], 0)
        assert_equal(mining_info['chain'], 'signet')
        assert 'currentblocktx' not in mining_info
        assert 'currentblockweight' not in mining_info
        assert_equal(mining_info['networkhashps'], Decimal('0'))
        assert_equal(mining_info['pooledtx'], 0)

        self.generate(self.nodes[0], 1, sync_fun=self.no_op)

        self.log.info("pregenerated signet blocks check")

        height = 0
        for block in signet_blocks:
            assert_equal(self.nodes[2].submitblock(block), None)
            height += 1
            assert_equal(self.nodes[2].getblockcount(), height)

        self.log.info("pregenerated signet blocks check (incompatible solution)")

        # FirstIslamicCoin: submitblock (src/rpc/mining.cpp) runs a
        # stateless CheckBlock() before ProcessNewBlock and *throws* on
        # failure there, instead of returning a BIP22 rejection string like
        # upstream does for every failure -- bad-signet-blksig is exactly
        # such a CheckBlock()-level failure here (see mining_basic.py's
        # submitblock_result() for the same pattern), so catch it instead
        # of asserting on a plain return value.
        try:
            result = self.nodes[4].submitblock(signet_blocks[0])
            assert_equal(result, 'bad-signet-blksig')
        except JSONRPCException as e:
            assert 'bad-signet-blksig' in e.error['message']

        self.log.info("test that signet logs the network magic on node start")
        with self.nodes[0].assert_debug_log(["Signet derived magic (message start)"]):
            self.restart_node(0)
        self.stop_node(0)
        self.nodes[0].assert_start_raises_init_error(extra_args=["-signetchallenge=abc"], expected_msg="Error: -signetchallenge must be hex, not 'abc'.")
        self.nodes[0].assert_start_raises_init_error(extra_args=["-signetchallenge=abc"] * 2, expected_msg="Error: -signetchallenge cannot be multiple values.")


if __name__ == '__main__':
    SignetBasicTest().main()
