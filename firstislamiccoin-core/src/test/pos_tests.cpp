// Copyright (c) 2026 The CodexaCoin developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.
//
// PARAMETERS.md Appendix A.5: unit tests for the coin-age-proportional
// staking reward formula (ComputeCoinAgeReward, pos.cpp) and a statistical
// check that PoS kernel eligibility (CheckStakeKernelHash) stays
// amount-only, independent of coin-age, as designed.

#include <arith_uint256.h>
#include <chain.h>
#include <consensus/amount.h>
#include <consensus/params.h>
#include <pos.h>
#include <primitives/transaction.h>
#include <uint256.h>

#include <boost/test/unit_test.hpp>

#include <cmath>
#include <cstdlib>
#include <limits>

namespace {
Consensus::Params MakeParams(int64_t annualBP = 1368, int64_t ageCapSeconds = 60 * 24 * 60 * 60)
{
    Consensus::Params params{};
    params.nStakeRewardAnnualBP = annualBP;
    params.nStakeRewardAgeCapSeconds = ageCapSeconds;
    return params;
}
} // namespace

BOOST_AUTO_TEST_SUITE(pos_tests)

// Cross-checked against a live regtest coinstake: a 28,000,000 CAC input
// aged 500s at the spec default 1368bp pays exactly 6,069,027,198 satoshis.
BOOST_AUTO_TEST_CASE(ComputeCoinAgeReward_KnownVector)
{
    const Consensus::Params params = MakeParams();
    const CAmount valueSat = 28'000'000 * COIN;
    BOOST_CHECK_EQUAL(ComputeCoinAgeReward(valueSat, 500, params), CAmount(6069027198LL));
}

BOOST_AUTO_TEST_CASE(ComputeCoinAgeReward_ZeroAndNegativeInputsReturnZero)
{
    const Consensus::Params params = MakeParams();
    BOOST_CHECK_EQUAL(ComputeCoinAgeReward(0, 1000, params), CAmount(0));
    BOOST_CHECK_EQUAL(ComputeCoinAgeReward(-1, 1000, params), CAmount(0));
    BOOST_CHECK_EQUAL(ComputeCoinAgeReward(100 * COIN, 0, params), CAmount(0));
    BOOST_CHECK_EQUAL(ComputeCoinAgeReward(100 * COIN, -1, params), CAmount(0));
}

// Reward must grow monotonically with age up to the cap, then plateau: any
// age at or beyond nStakeRewardAgeCapSeconds pays identically.
BOOST_AUTO_TEST_CASE(ComputeCoinAgeReward_AgeCapPlateaus)
{
    const Consensus::Params params = MakeParams();
    const CAmount valueSat = 500'000 * COIN;
    const int64_t cap = params.nStakeRewardAgeCapSeconds;

    const CAmount rewardHalfCap = ComputeCoinAgeReward(valueSat, cap / 2, params);
    const CAmount rewardAtCap = ComputeCoinAgeReward(valueSat, cap, params);
    const CAmount rewardBeyondCap = ComputeCoinAgeReward(valueSat, cap + 1, params);
    const CAmount rewardWayBeyondCap = ComputeCoinAgeReward(valueSat, cap * 100, params);

    BOOST_CHECK(rewardHalfCap > 0);
    BOOST_CHECK(rewardHalfCap < rewardAtCap);
    BOOST_CHECK_EQUAL(rewardAtCap, rewardBeyondCap);
    BOOST_CHECK_EQUAL(rewardAtCap, rewardWayBeyondCap);
}

// The 128-bit arith_uint256 intermediate is required precisely because
// valueSat * cappedAge overflows int64_t at CodexaCoin's premine scale
// (see the comment above ComputeCoinAgeReward in pos.cpp). Confirm that
// path is actually exercised here, not accidentally skipped.
BOOST_AUTO_TEST_CASE(ComputeCoinAgeReward_IntermediateMathOverflowsInt64)
{
    const CAmount valueSat = std::numeric_limits<int64_t>::max();
    const int64_t cappedAge = 60 * 24 * 60 * 60;
    const arith_uint256 coinSeconds = arith_uint256(static_cast<uint64_t>(valueSat)) * arith_uint256(static_cast<uint64_t>(cappedAge));
    static const arith_uint256 nMaxInt64 = arith_uint256(static_cast<uint64_t>(std::numeric_limits<int64_t>::max()));
    BOOST_CHECK(coinSeconds > nMaxInt64);

    // And yet, at any realistic (annualBP, ageCap) pair a real caller could
    // configure, the final reward -- after dividing back down -- lands
    // nowhere near overflowing CAmount:
    const Consensus::Params params = MakeParams();
    const CAmount reward = ComputeCoinAgeReward(valueSat, cappedAge, params);
    BOOST_CHECK(reward > 0);
    BOOST_CHECK(reward < std::numeric_limits<int64_t>::max());
}

// The defensive int64 clamp at the end of ComputeCoinAgeReward is meant to
// be unreachable through any (valueSat, params) combination this project
// actually ships -- confirmed above. Still, it must saturate rather than
// wrap negative if a future change to nStakeRewardAnnualBP/AgeCapSeconds
// ever pushes past int64 range. Force that path directly.
BOOST_AUTO_TEST_CASE(ComputeCoinAgeReward_DefensiveOverflowClamp)
{
    const Consensus::Params params = MakeParams(/*annualBP=*/std::numeric_limits<int64_t>::max(),
                                                  /*ageCapSeconds=*/std::numeric_limits<int64_t>::max());
    const CAmount reward = ComputeCoinAgeReward(std::numeric_limits<int64_t>::max(), std::numeric_limits<int64_t>::max(), params);
    BOOST_CHECK_EQUAL(reward, std::numeric_limits<int64_t>::max());
}

// "Full simulated year" calibration: rather than actually running ~492,000
// blocks, simulate a coin that stakes repeatedly, each time waiting exactly
// up to the age cap before restaking (the fastest a single UTXO can realize
// reward, since age beyond the cap earns nothing extra). Summed across a
// full calendar year this must reproduce the nominal annual rate
// (valueSat * annualBP / 10000) to within integer-rounding noise --
// confirming "1368bp = 13.68%/yr" is what a repeatedly-staked coin actually
// realizes, not just a label.
BOOST_AUTO_TEST_CASE(ComputeCoinAgeReward_FullYearCalibration)
{
    const Consensus::Params params = MakeParams();
    const CAmount valueSat = 1'000'000 * COIN;
    const int64_t cap = params.nStakeRewardAgeCapSeconds;

    CAmount total = 0;
    int64_t elapsed = 0;
    while (elapsed + cap <= SECONDS_PER_YEAR) {
        total += ComputeCoinAgeReward(valueSat, cap, params);
        elapsed += cap;
    }
    const int64_t remainder = SECONDS_PER_YEAR - elapsed;
    if (remainder > 0) {
        total += ComputeCoinAgeReward(valueSat, remainder, params);
    }

    const CAmount nominalAnnual = (valueSat * params.nStakeRewardAnnualBP) / 10000;

    // Integer-division rounding per stake event; a few satoshis of drift
    // across ~6 events on a 1,000,000 CAC input is expected and fine.
    const CAmount tolerance = 1000; // satoshis
    BOOST_CHECK_MESSAGE(std::abs(total - nominalAnnual) <= tolerance,
        "total=" << total << " nominalAnnual=" << nominalAnnual);
}

// Kernel-independence statistical test: CheckStakeKernelHash's weighted
// target (bnTarget = SetCompact(nBits) * arith_uint256(nValueIn)) is
// structurally amount-only -- blockFromTime/nTimeTx feed only the
// hash-scramble that decides *which particular* attempt passes, not the
// threshold itself. If that ever regressed (e.g. someone "helpfully" added
// an age term to bnWeight to match the reward-side coin-age logic above),
// older coins would pass at a different rate than younger ones for the same
// value. Confirm empirically, across many trials, that they don't.
BOOST_AUTO_TEST_CASE(CheckStakeKernelHash_EligibilityIndependentOfAge)
{
    const CAmount nValueIn = 1000 * COIN;

    // Pick nBits so the weighted target sits at ~half of the 256-bit hash
    // space for this nValueIn, i.e. an ~50% pass probability per attempt --
    // maximizes statistical power to detect an age-correlated skew.
    const arith_uint256 halfSpace = ~arith_uint256(0) >> 1;
    const arith_uint256 baseTarget = halfSpace / arith_uint256(static_cast<uint64_t>(nValueIn));
    const unsigned int nBits = baseTarget.GetCompact();

    CBlockIndex pindexPrev{};
    pindexPrev.nStakeModifier = uint256S("2f8f8a1c9b6e4d3a5c7b1e9f0a2d4c6e8b1a3f5d7c9e0b2a4d6f8c1e3a5b7d9f");

    const int64_t youngAge = 1;
    const int64_t oldAge = 55 * 24 * 60 * 60; // near the 60-day cap

    const int trials = 3000;
    int youngPasses = 0;
    int oldPasses = 0;
    const arith_uint256 seed = arith_uint256(0x1234567) ;
    for (int i = 0; i < trials; ++i) {
        const uint256 txHash = ArithToUint256(seed + arith_uint256(static_cast<uint64_t>(i)));
        const COutPoint prevout(txHash, 0);

        const uint32_t blockFromTimeYoung = 1'700'000'000;
        const uint32_t nTimeTxYoung = blockFromTimeYoung + static_cast<uint32_t>(youngAge);
        if (CheckStakeKernelHash(&pindexPrev, nBits, blockFromTimeYoung, nValueIn, prevout, nTimeTxYoung)) {
            ++youngPasses;
        }

        const uint32_t blockFromTimeOld = 1'700'000'000;
        const uint32_t nTimeTxOld = blockFromTimeOld + static_cast<uint32_t>(oldAge);
        if (CheckStakeKernelHash(&pindexPrev, nBits, blockFromTimeOld, nValueIn, prevout, nTimeTxOld)) {
            ++oldPasses;
        }
    }

    const double pYoung = static_cast<double>(youngPasses) / trials;
    const double pOld = static_cast<double>(oldPasses) / trials;

    // Generous tolerance (~6 standard errors on a p=0.5 binomial at this
    // sample size) to avoid flakiness while still catching any real
    // age-dependent effect, which would skew the two rates far apart.
    const double tolerance = 0.07;
    BOOST_CHECK_MESSAGE(std::abs(pYoung - pOld) < tolerance,
        "pYoung=" << pYoung << " pOld=" << pOld << " (young passes=" << youngPasses << " old passes=" << oldPasses << " / " << trials << " trials)");
}

BOOST_AUTO_TEST_SUITE_END()
