// Copyright (c) 2026 The FirstIslamicCoin developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.
//
// The fixed per-block staking reward. Every proof-of-stake block must mint
// exactly nFixedStakeReward plus the fees it collects -- whatever the amount or
// age of the coins staked. These cases drive IsValidCoinstakeReward(), the
// check ConnectBlock() applies, with real coinstake transactions measured
// against a coins view the same way ConnectBlock() measures them.

#include <arith_uint256.h>
#include <chainparams.h>
#include <coins.h>
#include <consensus/amount.h>
#include <consensus/params.h>
#include <pos.h>
#include <primitives/transaction.h>
#include <script/script.h>
#include <test/util/setup_common.h>
#include <uint256.h>
#include <validation.h>

#include <boost/test/unit_test.hpp>

#include <limits>
#include <memory>
#include <vector>

namespace {

struct StakeInput {
    CAmount value;
    int height;    //!< block the coin was created in
    uint32_t time; //!< coin timestamp
};

/**
 * Builds a coinstake spending fresh coins described by `inputs`, whose outputs
 * return the staked value plus `mint`, and returns the reward ConnectBlock()
 * would measure for it: value out minus value in.
 */
CAmount MeasureCoinstake(const std::vector<StakeInput>& inputs, CAmount mint)
{
    static uint64_t next_txid{1};
    CCoinsView base;
    CCoinsViewCache view{&base};
    const CScript script{CScript() << OP_TRUE};

    CMutableTransaction coinstake;
    coinstake.nTime = 1'800'000'000;
    CAmount staked{0};
    for (const StakeInput& in : inputs) {
        const COutPoint prevout{ArithToUint256(arith_uint256(next_txid++)), 0};
        view.AddCoin(prevout, Coin{CTxOut{in.value, script}, in.height, /*fCoinBaseIn=*/false, /*fCoinStakeIn=*/true, static_cast<int>(in.time)}, /*possible_overwrite=*/false);
        coinstake.vin.emplace_back(prevout);
        staked += in.value;
    }
    coinstake.vout.emplace_back(0, CScript{}); // empty first output marks a coinstake
    coinstake.vout.emplace_back(staked + mint, script);

    const CTransaction tx{coinstake};
    BOOST_REQUIRE(tx.IsCoinStake());
    return tx.GetValueOut() - view.GetValueIn(tx);
}

std::vector<std::unique_ptr<const CChainParams>> AllNetworks()
{
    std::vector<std::unique_ptr<const CChainParams>> networks;
    networks.push_back(CChainParams::Main());
    networks.push_back(CChainParams::TestNet());
    networks.push_back(CChainParams::SigNet({}));
    networks.push_back(CChainParams::RegTest({}));
    return networks;
}

const CAmount FIXED_REWARD{10 * COIN};

} // namespace

BOOST_FIXTURE_TEST_SUITE(fic_reward_tests, BasicTestingSetup)

BOOST_AUTO_TEST_CASE(fixed_reward_on_every_network)
{
    for (const auto& chain : AllNetworks()) {
        const Consensus::Params& params{chain->GetConsensus()};
        BOOST_CHECK_EQUAL(params.nFixedStakeReward, FIXED_REWARD);
        BOOST_CHECK_EQUAL(params.nRewardHalvingInterval, 0); // disabled at launch
        for (int height : {1, 2, 500, 492'750, 10'000'000, std::numeric_limits<int>::max()}) {
            BOOST_CHECK_EQUAL(GetBlockSubsidy(height, params, /*fProofOfStake=*/true), FIXED_REWARD);
        }
    }
}

BOOST_AUTO_TEST_CASE(reward_equals_fixed_amount_plus_fees)
{
    const Consensus::Params& params{Params().GetConsensus()};
    const int height{1'000};
    for (CAmount fees : {CAmount{0}, CAmount{1}, CAmount{2'260}, 5 * COIN, 1'000'000 * COIN}) {
        BOOST_CHECK_EQUAL(GetProofOfStakeReward(height, fees, params), FIXED_REWARD + fees);

        const std::vector<StakeInput> stake{{1'000 * COIN, 1, 1'700'000'000}};
        BOOST_CHECK(IsValidCoinstakeReward(MeasureCoinstake(stake, FIXED_REWARD + fees), fees, height, params));
        // Not a ceiling but an exact amount: one satoshi either way is invalid.
        BOOST_CHECK(!IsValidCoinstakeReward(MeasureCoinstake(stake, FIXED_REWARD + fees + 1), fees, height, params));
        BOOST_CHECK(!IsValidCoinstakeReward(MeasureCoinstake(stake, FIXED_REWARD + fees - 1), fees, height, params));
        // Claiming the fees twice -- which upstream's ConnectBlock allowed -- is invalid.
        if (fees > 0) {
            BOOST_CHECK(!IsValidCoinstakeReward(MeasureCoinstake(stake, FIXED_REWARD + 2 * fees), fees, height, params));
        }
    }
}

BOOST_AUTO_TEST_CASE(reward_constant_regardless_of_stake_amount)
{
    const Consensus::Params& params{Params().GetConsensus()};
    const int height{50'000};
    const CAmount fees{12'345};

    const std::vector<std::vector<StakeInput>> stakes{
        {{1, 1, 1'700'000'000}},                          // one satoshi
        {{COIN / 10, 1, 1'700'000'000}},                  // -minstakingamount default
        {{100 * COIN, 1, 1'700'000'000}},
        {{14'000'000 * COIN, 0, 1'789'171'200}},          // a whole genesis output
        {{14'000'000'000 * COIN, 1, 1'700'000'000}},      // the entire premine
        {{3 * COIN, 1, 1'700'000'000}, {400 * COIN, 7, 1'700'000'100}, {9 * COIN, 20, 1'700'000'200}}, // combined inputs
    };
    for (const auto& stake : stakes) {
        BOOST_CHECK(IsValidCoinstakeReward(MeasureCoinstake(stake, FIXED_REWARD + fees), fees, height, params));

        // Upstream CAC's model minted in proportion to the value staked; any such
        // amount that differs from the fixed reward is now rejected.
        CAmount staked{0};
        for (const auto& in : stake) staked += in.value;
        const CAmount proportional{staked / 100};
        if (proportional != FIXED_REWARD) {
            BOOST_CHECK(!IsValidCoinstakeReward(MeasureCoinstake(stake, proportional + fees), fees, height, params));
        }
    }
}

BOOST_AUTO_TEST_CASE(reward_constant_regardless_of_coin_age)
{
    const Consensus::Params& params{Params().GetConsensus()};
    const int height{600'000};
    const CAmount fees{0};
    const uint32_t now{1'800'000'000};
    const CAmount value{250'000 * COIN};

    // From a coin at the maturity boundary to one untouched for years, and a
    // genesis output: same value, very different ages, identical reward.
    const std::vector<StakeInput> ages{
        {value, height - params.nCoinbaseMaturity, now - 500 * 64},
        {value, height - 20'000, now - 16 * 24 * 60 * 60},
        {value, height - 60 * 1'350, now - 60 * 24 * 60 * 60},     // upstream CAC's former 60-day cap
        {value, 1, now - 4 * 365 * 24 * 60 * 60},
        {value, 0, 1'789'171'200},
    };
    for (const StakeInput& in : ages) {
        BOOST_CHECK(IsValidCoinstakeReward(MeasureCoinstake({in}, FIXED_REWARD + fees), fees, height, params));
        BOOST_CHECK(!IsValidCoinstakeReward(MeasureCoinstake({in}, 2 * FIXED_REWARD + fees), fees, height, params));
    }
}

BOOST_AUTO_TEST_CASE(halving_path_when_enabled_on_regtest)
{
    Consensus::Params params{CChainParams::RegTest({})->GetConsensus()};
    BOOST_REQUIRE_EQUAL(params.nRewardHalvingInterval, 0);

    params.nRewardHalvingInterval = 1'000;
    BOOST_CHECK_EQUAL(GetBlockSubsidy(1, params, true), 10 * COIN);
    BOOST_CHECK_EQUAL(GetBlockSubsidy(999, params, true), 10 * COIN);
    BOOST_CHECK_EQUAL(GetBlockSubsidy(1'000, params, true), 5 * COIN);
    BOOST_CHECK_EQUAL(GetBlockSubsidy(1'999, params, true), 5 * COIN);
    BOOST_CHECK_EQUAL(GetBlockSubsidy(2'000, params, true), 250'000'000);
    BOOST_CHECK_EQUAL(GetBlockSubsidy(3'000, params, true), 125'000'000);

    // Never increases, never goes negative, and reaches zero.
    CAmount previous{10 * COIN};
    for (int era = 1; era < 70; ++era) {
        const CAmount reward{GetBlockSubsidy(era * 1'000, params, true)};
        BOOST_CHECK(reward <= previous);
        BOOST_CHECK(reward >= 0);
        previous = reward;
    }
    BOOST_CHECK_EQUAL(previous, 0);
    BOOST_CHECK_EQUAL(GetBlockSubsidy(std::numeric_limits<int>::max(), params, true), 0);

    // Consensus then requires the halved amount, not the original one.
    const std::vector<StakeInput> stake{{1'000 * COIN, 1, 1'700'000'000}};
    BOOST_CHECK(IsValidCoinstakeReward(MeasureCoinstake(stake, 5 * COIN + 7), 7, 1'500, params));
    BOOST_CHECK(!IsValidCoinstakeReward(MeasureCoinstake(stake, 10 * COIN + 7), 7, 1'500, params));

    // Disabling it restores the fixed reward at any height.
    params.nRewardHalvingInterval = 0;
    BOOST_CHECK_EQUAL(GetBlockSubsidy(std::numeric_limits<int>::max(), params, true), 10 * COIN);
}

BOOST_AUTO_TEST_SUITE_END()
