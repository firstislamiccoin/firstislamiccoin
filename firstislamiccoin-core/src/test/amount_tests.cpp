// Copyright (c) 2016-2021 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <consensus/amount.h>
#include <consensus/tx_check.h>
#include <consensus/validation.h>
#include <key_io.h>
#include <policy/feerate.h>
#include <primitives/transaction.h>
#include <script/interpreter.h>
#include <script/script.h>
#include <test/util/setup_common.h>
#include <validation.h>

#include <limits>
#include <stdexcept>

#include <boost/test/unit_test.hpp>

BOOST_AUTO_TEST_SUITE(amount_tests)

BOOST_AUTO_TEST_CASE(MoneyRangeTest)
{
    BOOST_CHECK_EQUAL(MoneyRange(CAmount(-1)), false);
    BOOST_CHECK_EQUAL(MoneyRange(CAmount(0)), true);
    BOOST_CHECK_EQUAL(MoneyRange(CAmount(1)), true);
    BOOST_CHECK_EQUAL(MoneyRange(MAX_MONEY), true);
    // FirstIslamicCoin: MAX_MONEY is INT64_MAX here (no fixed cap, unlike
    // Bitcoin's small 21e6*COIN), so plain `MAX_MONEY + CAmount(1)` is
    // signed-integer overflow (UB) rather than a representable CAmount one
    // past the top of the range. Compute it via well-defined unsigned
    // wraparound instead -- this lands on the same value (CAmount's
    // negative INT64_MIN bit pattern) the original expression already
    // informally relied on, which MoneyRange()'s own `nValue >= 0` check
    // correctly rejects either way.
    BOOST_CHECK_EQUAL(MoneyRange(static_cast<CAmount>(static_cast<uint64_t>(MAX_MONEY) + 1)), false);
}

BOOST_AUTO_TEST_CASE(GetFeeTest)
{
    CFeeRate feeRate, altFeeRate;

    feeRate = CFeeRate(0);
    // Must always return 0
    BOOST_CHECK_EQUAL(feeRate.GetFee(0), CAmount(0));
    BOOST_CHECK_EQUAL(feeRate.GetFee(1e5), CAmount(0));

    feeRate = CFeeRate(1000);
    // Must always just return the arg
    BOOST_CHECK_EQUAL(feeRate.GetFee(0), CAmount(0));
    BOOST_CHECK_EQUAL(feeRate.GetFee(1), CAmount(1));
    BOOST_CHECK_EQUAL(feeRate.GetFee(121), CAmount(121));
    BOOST_CHECK_EQUAL(feeRate.GetFee(999), CAmount(999));
    BOOST_CHECK_EQUAL(feeRate.GetFee(1e3), CAmount(1e3));
    BOOST_CHECK_EQUAL(feeRate.GetFee(9e3), CAmount(9e3));

    feeRate = CFeeRate(-1000);
    // Must always just return -1 * arg
    BOOST_CHECK_EQUAL(feeRate.GetFee(0), CAmount(0));
    BOOST_CHECK_EQUAL(feeRate.GetFee(1), CAmount(-1));
    BOOST_CHECK_EQUAL(feeRate.GetFee(121), CAmount(-121));
    BOOST_CHECK_EQUAL(feeRate.GetFee(999), CAmount(-999));
    BOOST_CHECK_EQUAL(feeRate.GetFee(1e3), CAmount(-1e3));
    BOOST_CHECK_EQUAL(feeRate.GetFee(9e3), CAmount(-9e3));

    feeRate = CFeeRate(123);
    // Rounds up the result, if not integer
    BOOST_CHECK_EQUAL(feeRate.GetFee(0), CAmount(0));
    BOOST_CHECK_EQUAL(feeRate.GetFee(8), CAmount(1)); // Special case: returns 1 instead of 0
    BOOST_CHECK_EQUAL(feeRate.GetFee(9), CAmount(2));
    BOOST_CHECK_EQUAL(feeRate.GetFee(121), CAmount(15));
    BOOST_CHECK_EQUAL(feeRate.GetFee(122), CAmount(16));
    BOOST_CHECK_EQUAL(feeRate.GetFee(999), CAmount(123));
    BOOST_CHECK_EQUAL(feeRate.GetFee(1e3), CAmount(123));
    BOOST_CHECK_EQUAL(feeRate.GetFee(9e3), CAmount(1107));

    feeRate = CFeeRate(-123);
    // Truncates the result, if not integer
    BOOST_CHECK_EQUAL(feeRate.GetFee(0), CAmount(0));
    BOOST_CHECK_EQUAL(feeRate.GetFee(8), CAmount(-1)); // Special case: returns -1 instead of 0
    BOOST_CHECK_EQUAL(feeRate.GetFee(9), CAmount(-1));

    // check alternate constructor
    feeRate = CFeeRate(1000);
    altFeeRate = CFeeRate(feeRate);
    BOOST_CHECK_EQUAL(feeRate.GetFee(100), altFeeRate.GetFee(100));

    // Check full constructor
    BOOST_CHECK(CFeeRate(CAmount(-1), 0) == CFeeRate(0));
    BOOST_CHECK(CFeeRate(CAmount(0), 0) == CFeeRate(0));
    BOOST_CHECK(CFeeRate(CAmount(1), 0) == CFeeRate(0));
    // default value
    BOOST_CHECK(CFeeRate(CAmount(-1), 1000) == CFeeRate(-1));
    BOOST_CHECK(CFeeRate(CAmount(0), 1000) == CFeeRate(0));
    BOOST_CHECK(CFeeRate(CAmount(1), 1000) == CFeeRate(1));
    // lost precision (can only resolve satoshis per kB)
    BOOST_CHECK(CFeeRate(CAmount(1), 1001) == CFeeRate(0));
    BOOST_CHECK(CFeeRate(CAmount(2), 1001) == CFeeRate(1));
    // some more integer checks
    BOOST_CHECK(CFeeRate(CAmount(26), 789) == CFeeRate(32));
    BOOST_CHECK(CFeeRate(CAmount(27), 789) == CFeeRate(34));
    // Maximum size in bytes, should not crash
    CFeeRate(MAX_MONEY, std::numeric_limits<uint32_t>::max()).GetFeePerK();
}

BOOST_AUTO_TEST_CASE(BinaryOperatorTest)
{
    CFeeRate a, b;
    a = CFeeRate(1);
    b = CFeeRate(2);
    BOOST_CHECK(a < b);
    BOOST_CHECK(b > a);
    BOOST_CHECK(a == a);
    BOOST_CHECK(a <= b);
    BOOST_CHECK(a <= a);
    BOOST_CHECK(b >= a);
    BOOST_CHECK(b >= b);
    // a should be 0.00000002 BTC/kvB now
    a += a;
    BOOST_CHECK(a == b);
}

BOOST_AUTO_TEST_CASE(ToStringTest)
{
    CFeeRate feeRate;
    feeRate = CFeeRate(1);
    BOOST_CHECK_EQUAL(feeRate.ToString(), "0.00000001 FIC/kvB");
    BOOST_CHECK_EQUAL(feeRate.ToString(FeeEstimateMode::BTC_KVB), "0.00000001 FIC/kvB");
    BOOST_CHECK_EQUAL(feeRate.ToString(FeeEstimateMode::SAT_VB), "0.001 sat/vB");
}

// FirstIslamicCoin: MAX_MONEY is INT64_MAX, so "sum += value; MoneyRange(sum)"
// is signed overflow (UB), and optimising compilers drop the range check.
// Before the fix, CheckTransaction() accepted a tx whose outputs wrap past
// INT64_MAX, and a regtest block creating two INT64_MAX outputs from a 28M FIC
// input connected. These tests pin the overflow-safe checks.
static CMutableTransaction OutputOverflowTx(const COutPoint& prevout, const std::vector<CAmount>& values, const CScript& spk)
{
    CMutableTransaction mtx;
    mtx.nVersion = 2;
    mtx.vin.resize(1);
    mtx.vin[0].prevout = prevout;
    for (CAmount v : values) mtx.vout.emplace_back(v, spk);
    return mtx;
}

BOOST_AUTO_TEST_CASE(txout_total_overflow)
{
    const COutPoint prevout{Txid::FromUint256(uint256::ONE), 0};
    const CScript spk = CScript() << OP_TRUE;

    // A single MAX_MONEY output is in range.
    {
        CTransaction tx{OutputOverflowTx(prevout, {MAX_MONEY}, spk)};
        TxValidationState state;
        BOOST_CHECK(CheckTransaction(tx, state));
        BOOST_CHECK_EQUAL(tx.GetValueOut(), MAX_MONEY);
    }
    // Totals that wrap past INT64_MAX must be rejected, however they wrap.
    for (const auto& values : std::vector<std::vector<CAmount>>{
             {MAX_MONEY, 1},
             {MAX_MONEY, MAX_MONEY},
             {MAX_MONEY, MAX_MONEY, 2 * COIN + 2},
         }) {
        CTransaction tx{OutputOverflowTx(prevout, values, spk)};
        TxValidationState state;
        BOOST_CHECK(!CheckTransaction(tx, state));
        BOOST_CHECK_EQUAL(state.GetRejectReason(), "bad-txns-txouttotal-toolarge");
        BOOST_CHECK_THROW(tx.GetValueOut(), std::runtime_error);
    }
}

BOOST_FIXTURE_TEST_CASE(txout_total_overflow_block_rejected, TestChain100Setup)
{
    // Spend a mature coinbase into outputs whose total wraps to (input - 1 FIC),
    // i.e. a normal-looking 1 FIC fee.
    const CTransactionRef funding = m_coinbase_txns[1];
    const CAmount value_in = funding->vout[0].nValue;
    const CScript p2pk = funding->vout[0].scriptPubKey;
    const CScript dest = GetScriptForDestination(PKHash(coinbaseKey.GetPubKey()));
    CMutableTransaction mtx = OutputOverflowTx(COutPoint(funding->GetHash(), 0), {MAX_MONEY, MAX_MONEY, value_in - COIN + 2}, dest);
    std::vector<unsigned char> sig;
    BOOST_REQUIRE(coinbaseKey.Sign(SignatureHash(p2pk, mtx, 0, SIGHASH_ALL, 0, SigVersion::BASE), sig));
    sig.push_back((unsigned char)SIGHASH_ALL);
    mtx.vin[0].scriptSig = CScript() << sig;

    {
        LOCK(cs_main);
        const MempoolAcceptResult result = m_node.chainman->ProcessTransaction(MakeTransactionRef(mtx));
        BOOST_CHECK(result.m_result_type == MempoolAcceptResult::ResultType::INVALID);
        BOOST_CHECK_EQUAL(result.m_state.GetRejectReason(), "bad-txns-txouttotal-toolarge");
    }

    const uint256 tip_before = WITH_LOCK(cs_main, return m_node.chainman->ActiveChain().Tip()->GetBlockHash());
    const CBlock block = CreateAndProcessBlock({mtx}, p2pk);
    LOCK(cs_main);
    BOOST_CHECK(m_node.chainman->ActiveChain().Tip()->GetBlockHash() == tip_before);
    BOOST_CHECK(m_node.chainman->ActiveChain().Tip()->GetBlockHash() != block.GetHash());
    BOOST_CHECK(!m_node.chainman->ActiveChainstate().CoinsTip().HaveCoin(COutPoint(mtx.GetHash(), 0)));
}

BOOST_AUTO_TEST_SUITE_END()
