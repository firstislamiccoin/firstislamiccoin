#!/usr/bin/env python3
# Copyright (c) 2014-2022 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test mempool limiting together/eviction with the wallet."""

from decimal import Decimal

from test_framework.blocktools import COINBASE_MATURITY
from test_framework.fic import get_min_fee_sat
from test_framework.p2p import P2PTxInvStore
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import (
    assert_equal,
    assert_fee_amount,
    assert_greater_than,
    assert_raises_rpc_error,
    create_lots_of_big_transactions,
    gen_return_txouts,
)
from test_framework.wallet import (
    COIN,
    MiniWallet,
)


class MempoolLimitTest(BitcoinTestFramework):
    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 1
        self.extra_args = [[
            "-datacarriersize=100000",
            "-maxmempool=5",
        ]]
        self.supports_cli = False

    def fill_mempool(self):
        """Fill mempool until eviction."""
        self.log.info("Fill the mempool until eviction is triggered and the mempoolminfee rises")
        txouts = gen_return_txouts()
        node = self.nodes[0]
        miniwallet = self.wallet
        relayfee = node.getnetworkinfo()['relayfee']

        tx_batch_size = 1
        num_of_batches = 75
        # Generate UTXOs to flood the mempool
        # 1 to create a tx initially that will be evicted from the mempool later
        # 75 transactions each with a fee rate higher than the previous one
        # And 1 more to verify that this tx does not get added to the mempool with a fee rate less than the mempoolminfee
        # And 2 more for the package cpfp test
        self.generate(miniwallet, 1 + (num_of_batches * tx_batch_size))

        # Mine 99 blocks so that the UTXOs are allowed to be spent
        self.generate(node, COINBASE_MATURITY - 1)

        self.log.debug("Create a mempool tx that will be evicted")
        tx_to_be_evicted_id = miniwallet.send_self_transfer(from_node=node, fee_rate=relayfee)["txid"]

        # Increase the tx fee rate to give the subsequent transactions a higher priority in the mempool
        # The tx has an approx. vsize of 65k, i.e. multiplying the previous fee rate (in sats/kvB)
        # by 130 should result in a fee that corresponds to 2x of that fee rate
        #
        # FirstIslamicCoin: upstream scales base_fee off of relayfee itself,
        # which works there because relayfee is ~0.00001 BTC/kvB. This fork's
        # relayfee floor is 100x higher (0.001), so the same multiplier makes
        # the last of the 75 batches' absolute fee exceed a ~65 kvB tx's
        # share of testmempoolaccept/sendrawtransaction's fixed 0.10 BTC/kvB
        # default max-fee-rate ceiling (unrelated to relayfee, so it didn't
        # scale up with it) -- every batch past roughly #50 was then rejected
        # outright instead of accepted, and create_lots_of_big_transactions()
        # blew up on the missing 'fees' key of a rejected testmempoolaccept
        # result. Use a fixed absolute base fee instead: still above
        # relayfee's rate (so batch 0 outranks the tx meant to be evicted)
        # and comfortably below the ceiling for batch 74, the last one.
        base_fee = Decimal('0.08')

        # FirstIslamicCoin: upstream expects eviction to log "rolling minimum
        # fee bumped" and raise mempoolminfee, via CTxMemPool::trackPackageRemoved()
        # feeding a decaying rolling-fee estimate that GetMinFee() then reports.
        # In this fork that whole mechanism -- GetMinFee(), trackPackageRemoved(),
        # and the log line itself -- is commented-out dead code in
        # TrimToSize()/txmempool.cpp (inherited unmodified from the CodexaCoin
        # import), replaced by this fork's fixed 100 sat/vB fee floor. Eviction
        # by mempool size (TrimToSize()'s RemoveStaged(..., SIZELIMIT) loop)
        # still runs and still drops the lowest-feerate entries first -- only
        # the "raise the acceptance bar afterwards" half is gone -- so we still
        # exercise and check eviction below, just not the fee-bump/log side.
        self.log.debug("Fill up the mempool with txs with higher fee rate")
        for batch_of_txid in range(num_of_batches):
            fee = (batch_of_txid + 1) * base_fee
            create_lots_of_big_transactions(miniwallet, node, fee, tx_batch_size, txouts)

        self.log.debug("The tx should be evicted by now")
        # The number of transactions created should be greater than the ones present in the mempool
        assert_greater_than(tx_batch_size * num_of_batches, len(node.getrawmempool()))
        # Initial tx created should not be present in the mempool anymore as it had a lower fee rate
        assert tx_to_be_evicted_id not in node.getrawmempool()

        # FirstIslamicCoin: minrelaytxfee reports this fork's real fixed
        # 100 sat/vB floor (0.001 BTC/kvB), not upstream's 1 sat/vB default.
        # mempoolminfee no longer rises above it after eviction either (see
        # the dead rolling-fee mechanism noted above), so it stays equal
        # rather than upstream's greater-than.
        self.log.debug("Check that mempoolminfee equals minrelaytxfee")
        assert_equal(node.getmempoolinfo()['minrelaytxfee'], Decimal('0.00100000'))
        assert_equal(node.getmempoolinfo()['mempoolminfee'], Decimal('0.00100000'))

    def test_rbf_carveout_disallowed(self):
        node = self.nodes[0]

        self.log.info("Check that individually-evaluated transactions in a package don't increase package limits for other subpackage parts")

        # We set chain limits to 2 ancestors, 1 descendant, then try to get a parents-and-child chain of 2 in mempool
        #
        # FirstIslamicCoin: RBF is fully removed from this fork (no
        # IsRBFOptIn, no prioritisetransaction RPC), so upstream's "tx_B
        # RBFs tx_A" step to earn the CPFP carve-out's +1 descendant
        # allowance isn't available. The carve-out mechanism itself is
        # still there though (src/validation.cpp's cpfp_carve_out_limits,
        # already fixed in an earlier pass of this project to not depend on
        # RBF at all -- see the FirstIslamicCoin comment right above it),
        # and it isn't RBF-specific to begin with: it fires whenever a
        # small, single-ancestor tx would otherwise push its one parent
        # over the parent's descendant limit. Trigger it the same way
        # without replacement: give tx_A two outputs, let one already-
        # confirmed-into-the-mempool descendant fill tx_A's descendant
        # limit (1), then have tx_B spend tx_A's *other* output -- a
        # sibling, not a replacement -- which needs the same carve-out to
        # be individually accepted. tx_C still spends tx_B and is still
        # too big to qualify for carve-out itself, so it should still make
        # the package hit the same "too-long-mempool-chain" the carve-out
        # is meant to guard against leaking into.
        #
        # A: Parent with two outputs
        # A_desc: Already-confirmed-into-mempool descendant spending output 0, filling A's descendant limit
        # B: First transaction in package, spends A's output 1; needs the carve-out to be individually accepted
        # C: Second transaction in package, spends B. If the +1 descendant limit persisted, would make it into mempool

        self.restart_node(0, extra_args=self.extra_args[0] + ["-limitancestorcount=2", "-limitdescendantcount=1"])

        # Generate a confirmed utxo to fund tx_A
        grandparent_utxo = self.wallet.send_self_transfer(
            from_node=node,
            confirmed_only=True
        )["new_utxo"]
        self.generate(node, 1)

        A_weight = 1000
        mempoolmin_feerate = node.getmempoolinfo()["mempoolminfee"]
        # FirstIslamicCoin: target_weight//4 undercounts create_self_transfer[_multi]'s
        # real vsize slightly once _bulk_tx() pads it out to the target (confirmed
        # empirically elsewhere in this file), so use this fork's own floor helper
        # with a generous margin rather than a tight upstream-style +0.000001 one.
        tx_A = self.wallet.send_self_transfer_multi(
            from_node=node,
            utxos_to_spend=[grandparent_utxo],
            num_outputs=2,
            fee_per_output=get_min_fee_sat(A_weight // 4) + 1000,
        )

        # Fills tx_A's one allowed descendant slot.
        self.wallet.send_self_transfer(
            from_node=node,
            fee=Decimal(get_min_fee_sat(A_weight // 4) + 1000) / COIN,
            target_weight=A_weight,
            utxo_to_spend=tx_A["new_utxos"][0],
            confirmed_only=True
        )

        # A sibling of that descendant, not a replacement -- needs the carve-out to be
        # individually accepted, since tx_A is already at its descendant limit.
        tx_B = self.wallet.create_self_transfer(
            fee=Decimal(get_min_fee_sat(A_weight // 4) * 4 + 1000) / COIN,
            target_weight=A_weight,
            utxo_to_spend=tx_A["new_utxos"][1],
            confirmed_only=True
        )

        # Spends tx_B's output, too big for cpfp carveout (because that would also increase the descendant limit by 1)
        non_cpfp_carveout_weight = 40001 # EXTRA_DESCENDANT_TX_SIZE_LIMIT + 1
        tx_C = self.wallet.create_self_transfer(
            target_weight=non_cpfp_carveout_weight,
            fee=Decimal(get_min_fee_sat(non_cpfp_carveout_weight // 4) + 1000) / COIN,
            utxo_to_spend=tx_B["new_utxo"],
            confirmed_only=True
        )

        assert_raises_rpc_error(-26, "too-long-mempool-chain", node.submitpackage, [tx_B["hex"], tx_C["hex"]])

    def test_mid_package_eviction(self):
        node = self.nodes[0]
        self.log.info("Check a package where each parent passes the current mempoolminfee but would cause eviction before package submission terminates")

        self.restart_node(0, extra_args=self.extra_args[0])

        # Restarting the node resets mempool minimum feerate
        assert_equal(node.getmempoolinfo()['minrelaytxfee'], Decimal('0.00100000'))
        assert_equal(node.getmempoolinfo()['mempoolminfee'], Decimal('0.00100000'))

        self.fill_mempool()
        current_info = node.getmempoolinfo()
        mempoolmin_feerate = current_info["mempoolminfee"]

        package_hex = []
        # UTXOs to be spent by the ultimate child transaction
        parent_utxos = []

        evicted_weight = 8000
        # Mempool transaction which is evicted due to being at the "bottom" of the mempool when the
        # mempool overflows and evicts by descendant score. It's important that the eviction doesn't
        # happen in the middle of package evaluation, as it can invalidate the coins cache.
        # FirstIslamicCoin: target_weight//4 undercounts create_self_transfer's
        # real vsize slightly once _bulk_tx() pads it out to the target (same
        # gap noted below for the 200000-weight case), so the small
        # +0.000001 margin upstream uses isn't reliably enough to clear this
        # fork's floor for the real, padded size.
        mempool_evicted_tx = self.wallet.send_self_transfer(
            from_node=node,
            fee=Decimal(get_min_fee_sat(evicted_weight // 4) + 1000) / COIN,
            target_weight=evicted_weight,
            confirmed_only=True
        )
        # Already in mempool when package is submitted.
        assert mempool_evicted_tx["txid"] in node.getrawmempool()

        # This parent spends the above mempool transaction that exists when its inputs are first
        # looked up, but disappears later. Its inputs are cached; when the mempool transaction is
        # evicted, its coin is no longer available, but the cache could still contain the tx.
        #
        # FirstIslamicCoin: upstream deliberately prices cpfp_parent just
        # below mempoolmin_feerate here -- individually rejected ("mempool
        # min fee not met"), "eligible for reconsideration" once the child
        # below bumps the package above that threshold. Confirmed
        # empirically (see the note on the earlier submitpackage case
        # above) that a parent below this fork's fixed fee floor is
        # rejected outright inside a package too, CPFP or not -- if
        # cpfp_parent stayed below it, submitpackage would reject it before
        # ever reaching the big-parents/eviction machinery this test is
        # actually about, defeating the point. Price it to individually
        # clear the floor instead; the coins-cache-invalidation mechanic
        # under test doesn't depend on cpfp_parent being temporarily
        # invalid, only on mempool_evicted_tx disappearing out from under
        # it mid-package-evaluation.
        cpfp_parent = self.wallet.create_self_transfer(
            utxo_to_spend=mempool_evicted_tx["new_utxo"],
            fee_rate=mempoolmin_feerate,
            confirmed_only=True)
        package_hex.append(cpfp_parent["hex"])
        parent_utxos.append(cpfp_parent["new_utxo"])
        assert node.testmempoolaccept([cpfp_parent["hex"]])[0]["allowed"]

        self.wallet.rescan_utxos()

        # Series of parents that don't need CPFP and are submitted individually. Each one is large and
        # high feerate, which means they should trigger eviction but not be evicted.
        parent_weight = 100000
        num_big_parents = 3
        assert_greater_than(parent_weight * num_big_parents, current_info["maxmempool"] - current_info["bytes"])
        parent_fee = (100 * mempoolmin_feerate / 1000) * (parent_weight // 4)

        big_parent_txids = []
        for i in range(num_big_parents):
            parent = self.wallet.create_self_transfer(fee=parent_fee, target_weight=parent_weight, confirmed_only=True)
            parent_utxos.append(parent["new_utxo"])
            package_hex.append(parent["hex"])
            big_parent_txids.append(parent["txid"])
            # There is room for each of these transactions independently
            assert node.testmempoolaccept([parent["hex"]])[0]["allowed"]

        # FirstIslamicCoin: upstream fine-tunes the child's fee to a narrow
        # window relative to mempoolminfee -- just enough to still meet it
        # if it rises during mid-package eviction, but not so much that
        # mempool_evicted_tx survives. That window doesn't exist on this
        # fork: mempoolminfee never rises above the fixed floor (the dead
        # rolling-fee mechanism noted in fill_mempool()), so there's no
        # "before vs. after" gap to walk. cpfp_parent is already
        # individually valid now (see above), so the child just needs its
        # own comfortably-valid fee to be accepted.
        approx_child_vsize = self.wallet.create_self_transfer_multi(utxos_to_spend=parent_utxos)["tx"].get_vsize()
        cpfp_satoshis = get_min_fee_sat(approx_child_vsize) * 2

        child = self.wallet.create_self_transfer_multi(utxos_to_spend=parent_utxos, fee_per_output=cpfp_satoshis)
        package_hex.append(child["hex"])

        # Package should be submitted, temporarily exceeding maxmempool, and then evicted.
        # FirstIslamicCoin: dropped the assert_debug_log(["rolling minimum
        # fee bumped"]) wrapper upstream has here -- that log line is dead
        # code on this fork (see the note in fill_mempool()), so it would
        # never appear regardless of whether eviction itself works.
        assert_raises_rpc_error(-26, "mempool full", node.submitpackage, package_hex)

        # Maximum size must never be exceeded.
        assert_greater_than(node.getmempoolinfo()["maxmempool"], node.getmempoolinfo()["bytes"])

        # Evicted transaction and its descendants must not be in mempool.
        resulting_mempool_txids = node.getrawmempool()
        assert mempool_evicted_tx["txid"] not in resulting_mempool_txids
        assert cpfp_parent["txid"] not in resulting_mempool_txids
        assert child["txid"] not in resulting_mempool_txids
        for txid in big_parent_txids:
            assert txid in resulting_mempool_txids

    def test_mid_package_replacement(self):
        # FirstIslamicCoin: this test's whole premise is a coin going stale
        # mid-package because replacement_tx replaces replaced_tx while
        # cpfp_parent (which spends replaced_tx's output) is already queued
        # in the same package -- checking that the now-dangling cpfp_parent
        # is correctly rejected (bad-txns-inputs-missingorspent) rather than
        # accepted off a stale cached coin.
        #
        # Replacement is hard-disabled on this fork: src/validation.cpp's
        # PreChecks() has an unconditional early return -- "FirstIslamicCoin:
        # Disable replacement feature for now" -- the moment it sees a
        # transaction conflicting with an existing mempool entry
        # (txn-mempool-conflict), with no fallback path. So replacement_tx
        # could never actually replace replaced_tx here; it would just be
        # rejected outright, replaced_tx would stay put, and cpfp_parent's
        # input would never go stale in the first place -- there's nothing
        # left of the scenario to construct.
        #
        # This is a different situation from test_mid_package_eviction just
        # above: that one tests the same *class* of bug (a coin going stale
        # mid-package) but through mempool-size eviction, a mechanism that's
        # very much still present here and unrelated to replacement. Reusing
        # that same trick here would just re-test test_mid_package_eviction
        # under a different name, not this test's actual subject.
        self.log.info("SKIPPED: test_mid_package_replacement -- replacement is fully disabled on this fork, so this scenario cannot occur (see comment above)")


    def run_test(self):
        node = self.nodes[0]
        self.wallet = MiniWallet(node)
        miniwallet = self.wallet

        # Generate coins needed to create transactions in the subtests (excluding coins used in fill_mempool).
        self.generate(miniwallet, 20)

        relayfee = node.getnetworkinfo()['relayfee']
        self.log.info('Check that mempoolminfee is minrelaytxfee')
        assert_equal(node.getmempoolinfo()['minrelaytxfee'], Decimal('0.00100000'))
        assert_equal(node.getmempoolinfo()['mempoolminfee'], Decimal('0.00100000'))

        self.fill_mempool()

        # Deliberately try to create a tx with a fee less than the minimum mempool fee to assert that it does not get added to the mempool
        self.log.info('Create a mempool tx that will not pass mempoolminfee')
        # FirstIslamicCoin: upstream sends at exactly relayfee here because
        # fill_mempool() drove mempoolminfee above it via eviction, so
        # relayfee itself is now below the bar, and gets rejected by the
        # *dynamic* mempoolminfee check ("mempool min fee not met"). This
        # fork's mempoolminfee doesn't rise above relayfee (see the dead
        # rolling-fee mechanism noted in fill_mempool()), so relayfee itself
        # would be accepted; send below it instead, at this fork's fixed
        # fee-floor level, which is enforced by a different, earlier
        # consensus-level check with its own rejection reason.
        assert_raises_rpc_error(-26, "bad-txns-fee-not-enough", miniwallet.send_self_transfer, from_node=node, fee_rate=relayfee / 2)

        # FirstIslamicCoin: upstream's version of this scenario relies on a
        # parent that's below the *dynamic* mempool minimum feerate (bumped
        # up by the earlier fill_mempool() eviction) but still above this
        # chain's minRelayTxFee, so a fee-bumping child can rescue it via
        # package CPFP. On this fork mempoolminfee never rises above
        # minRelayTxFee (the dead rolling-fee mechanism noted in
        # fill_mempool()), and confirmed empirically, a parent below this
        # fork's fixed fee floor gets "bad-txns-fee-not-enough" even inside
        # a submitpackage call with a rescuing child -- the floor is a
        # per-tx, unconditional check that package-level CPFP evaluation
        # doesn't get a chance to relax. So there's no way to construct a
        # "genuinely below the bar, rescued by its child" parent here at
        # all; every package member ends up independently viable instead,
        # and submitpackage reports each one's fees standalone rather than
        # combined. Test that reporting, not the no-longer-reachable rescue.
        self.log.info("Check that submitpackage correctly reports fees for a package of independently-valid transactions")
        node = self.nodes[0]
        peer = node.add_p2p_connection(P2PTxInvStore())

        # Package with 2 parents and 1 child. One parent has a high feerate due to modified fees,
        # another is below the mempool minimum feerate but bumped by the child.
        #
        # FirstIslamicCoin: RBF (and prioritisetransaction with it) is fully
        # removed from this fork, so "high feerate due to modified fees" via
        # a virtual fee-delta bump isn't available. Give tx_rich a real,
        # actually-paid fee instead -- everything downstream reads its
        # resulting fees/effective-feerate the same way regardless of
        # whether that fee was real or simulated. It can't just be
        # DEFAULT_FEE (10,000 sats) though: MiniWallet's RAW_OP_TRUE mode
        # (the default) always produces a 104 vbyte tx, and 10,000 sats/104vB
        # is ~96 sat/vB, just under this fork's fixed 100 sat/vB floor --
        # upstream's DEFAULT_FEE only needed to clear its ~1 sat/vB default
        # relay fee. Compute a real fee from this fork's own floor helper
        # instead (with a safety margin), and check against that real value
        # everywhere below. Same story for tx_child's explicit
        # fee_per_output=10000: its 2-input, 1-output tx is bigger (154
        # vbytes), so 10,000 sats clears neither upstream's assumption nor
        # this fork's floor for it either.
        tx_rich_fee_sat = get_min_fee_sat(104) * 2
        tx_rich_fee = Decimal(tx_rich_fee_sat) / COIN
        tx_poor = miniwallet.create_self_transfer(fee_rate=relayfee)
        tx_rich = miniwallet.create_self_transfer(fee=tx_rich_fee)
        package_txns = [tx_rich, tx_poor]
        coins = [tx["new_utxo"] for tx in package_txns]
        tx_child_fee_per_output_sat = get_min_fee_sat(154) * 2
        tx_child = miniwallet.create_self_transfer_multi(utxos_to_spend=coins, fee_per_output=tx_child_fee_per_output_sat)
        tx_child_fee = Decimal(tx_child_fee_per_output_sat) / COIN
        package_txns.append(tx_child)

        submitpackage_result = node.submitpackage([tx["hex"] for tx in package_txns])

        rich_parent_result = submitpackage_result["tx-results"][tx_rich["wtxid"]]
        poor_parent_result = submitpackage_result["tx-results"][tx_poor["wtxid"]]
        child_result = submitpackage_result["tx-results"][tx_child["tx"].getwtxid()]
        assert_fee_amount(poor_parent_result["fees"]["base"], tx_poor["tx"].get_vsize(), relayfee)
        assert_equal(rich_parent_result["fees"]["base"], tx_rich_fee)
        assert_equal(child_result["fees"]["base"], tx_child_fee)
        # None of the three needs CPFP -- each clears this fork's fee floor
        # on its own -- so each one's effective feerate is just its own
        # individual feerate, and effective-includes is just itself.
        assert_fee_amount(tx_rich_fee, tx_rich["tx"].get_vsize(), rich_parent_result["fees"]["effective-feerate"])
        assert_equal(rich_parent_result["fees"]["effective-includes"], [tx_rich["wtxid"]])
        assert_fee_amount(poor_parent_result["fees"]["base"], tx_poor["tx"].get_vsize(), poor_parent_result["fees"]["effective-feerate"])
        assert_equal(poor_parent_result["fees"]["effective-includes"], [tx_poor["wtxid"]])
        assert_fee_amount(tx_child_fee, tx_child["tx"].get_vsize(), child_result["fees"]["effective-feerate"])
        assert_equal(child_result["fees"]["effective-includes"], [tx_child["tx"].getwtxid()])

        # The node will broadcast each transaction, still abiding by its peer's fee filter
        peer.wait_for_broadcast([tx["tx"].getwtxid() for tx in package_txns])

        self.log.info("Check a package that passes mempoolminfee but is evicted immediately after submission")
        mempoolmin_feerate = node.getmempoolinfo()["mempoolminfee"]
        current_mempool = node.getrawmempool(verbose=False)
        worst_feerate_btcvb = Decimal("21000000")
        for txid in current_mempool:
            entry = node.getmempoolentry(txid)
            worst_feerate_btcvb = min(worst_feerate_btcvb, entry["fees"]["descendant"] / entry["descendantsize"])
        # Needs to be large enough to trigger eviction
        target_weight_each = 200000
        assert_greater_than(target_weight_each * 2, node.getmempoolinfo()["maxmempool"] - node.getmempoolinfo()["bytes"])
        # FirstIslamicCoin: upstream builds a parent deliberately just below
        # mempoolmin_feerate (rescued into the mempool only by the child's
        # fee, i.e. real CPFP), betting that the package still ranks below
        # everything else already there and gets evicted right back out.
        # Confirmed empirically (see the note on the earlier submitpackage
        # case above): a parent below this fork's fixed fee floor is
        # rejected outright, CPFP or not, so that specific construction
        # isn't possible here, and mempoolmin_feerate is just that same
        # floor now anyway (it doesn't ride above it the way upstream's
        # does). Give both parent and child their own minimal-but-valid fee
        # instead -- individually acceptable, but still low enough that the
        # existing (much higher-paying) mempool content outranks them,
        # which is enough to exercise the same "accepted then immediately
        # evicted" path.
        # FirstIslamicCoin: target_weight//4 undercounts create_self_transfer's
        # real vsize slightly once _bulk_tx() pads it out to target_weight_each
        # (confirmed empirically: 50000 assumed vs. 50004 real for a 200000
        # weight target) -- a bigger margin than a few sats is needed to
        # reliably clear the floor for the real, padded size.
        parent_vsize = target_weight_each // 4
        parent_fee = Decimal(get_min_fee_sat(parent_vsize) + 1000) / COIN
        child_fee = Decimal(get_min_fee_sat(parent_vsize) + 1000) / COIN
        # However, when eviction is triggered, these transactions should be at the bottom.
        # This assertion assumes parent and child are the same size.
        miniwallet.rescan_utxos()
        tx_parent_just_below = miniwallet.create_self_transfer(fee=parent_fee, target_weight=target_weight_each)
        tx_child_just_above = miniwallet.create_self_transfer(utxo_to_spend=tx_parent_just_below["new_utxo"], fee=child_fee, target_weight=target_weight_each)
        # This package ranks below the lowest descendant package in the mempool
        assert_greater_than(worst_feerate_btcvb, (parent_fee + child_fee) / (tx_parent_just_below["tx"].get_vsize() + tx_child_just_above["tx"].get_vsize()))
        assert_raises_rpc_error(-26, "mempool full", node.submitpackage, [tx_parent_just_below["hex"], tx_child_just_above["hex"]])

        self.log.info('Test passing a value below the minimum (5 MB) to -maxmempool throws an error')
        self.stop_node(0)
        self.nodes[0].assert_start_raises_init_error(["-maxmempool=4"], "Error: -maxmempool must be at least 5 MB")

        self.test_mid_package_replacement()
        self.test_mid_package_eviction()
        self.test_rbf_carveout_disallowed()


if __name__ == '__main__':
    MempoolLimitTest().main()
