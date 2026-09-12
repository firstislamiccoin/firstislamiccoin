// Copyright (c) 2026 The FirstIslamicCoin developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.
//
// Statistical check that PoS kernel eligibility (CheckStakeKernelHash) is
// amount-only and independent of coin age.
//
// FirstIslamicCoin: this suite also held upstream CAC's coin-age reward cases
// (ComputeCoinAgeReward). That formula no longer exists; the fixed reward that
// replaced it is covered by fic_reward_tests.cpp.

#include <arith_uint256.h>
#include <chain.h>
#include <consensus/amount.h>
#include <pos.h>
#include <primitives/transaction.h>
#include <uint256.h>

#include <boost/test/unit_test.hpp>

#include <cmath>

BOOST_AUTO_TEST_SUITE(pos_tests)

// Kernel-independence statistical test: CheckStakeKernelHash's weighted
// target (bnTarget = SetCompact(nBits) * arith_uint256(nValueIn)) is
// structurally amount-only -- blockFromTime/nTimeTx feed only the
// hash-scramble that decides *which particular* attempt passes, not the
// threshold itself. If that ever regressed (e.g. someone added an age term
// to bnWeight), older coins would pass at a different rate than younger
// ones for the same value. Confirm empirically, across many trials, that
// they don't.
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
    const int64_t oldAge = 55 * 24 * 60 * 60;

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
