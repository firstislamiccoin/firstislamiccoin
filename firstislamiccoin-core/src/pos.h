// Copyright (c) 2014-2018 The BlackCoin Developers
// Copyright (c) 2011-2013 The PPCoin developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

// Stake cache by Qtum
// Copyright (c) 2016-2018 The Qtum developers

#ifndef CODEXACOIN_POS_H
#define CODEXACOIN_POS_H

#include <chain.h>
#include <primitives/transaction.h>
#include <txdb.h>
#include <validation.h>
#include <arith_uint256.h>
#include <consensus/validation.h>
#include <hash.h>
#include <timedata.h>
#include <chainparams.h>
#include <script/sign.h>
#include <consensus/consensus.h>
#include <stdint.h>

using namespace std;

/** Compute the hash modifier for proof-of-stake */
uint256 ComputeStakeModifier(const CBlockIndex* pindexPrev, const uint256& kernel);

struct CStakeCache{
    CStakeCache(uint32_t blockFromTime_, CAmount amount_) : blockFromTime(blockFromTime_), amount(amount_){
    }
    uint32_t blockFromTime;
    CAmount amount;
};

// Check whether the coinstake timestamp meets protocol
bool CheckCoinStakeTimestamp(int64_t nTimeBlock, int64_t nTimeTx);
bool CheckStakeBlockTimestamp(int64_t nTimeBlock);
bool CheckKernel(CBlockIndex* pindexPrev, unsigned int nBits, uint32_t nTime, const COutPoint& prevout, CCoinsViewCache& view);
bool CheckKernel(CBlockIndex* pindexPrev, unsigned int nBits, uint32_t nTime, const COutPoint& prevout, CCoinsViewCache& view, const std::map<COutPoint, CStakeCache>& cache);
bool CheckStakeKernelHash(const CBlockIndex* pindexPrev, unsigned int nBits, uint32_t blockFromTime, CAmount prevoutValue, const COutPoint& prevout, unsigned int nTimeTx, bool fPrintProofOfStake = false);
bool CheckProofOfStake(CBlockIndex* pindexPrev, const CTransaction& tx, unsigned int nBits, BlockValidationState& state, CCoinsViewCache& view, unsigned int nTimeTx);
void CacheKernel(std::map<COutPoint, CStakeCache>& cache, const COutPoint& prevout, CBlockIndex* pindexPrev, CCoinsViewCache& view);

/**
 * FirstIslamicCoin: whether a coin created at nCoinHeight may be used as a
 * stake kernel, or spent, in a block at nSpendHeight. Coins need
 * nCoinbaseMaturity confirmations, except genesis outputs. The genesis block
 * can never be reorganised away, which is the only thing maturity guards
 * against; and without the exemption the chain could not start, since no
 * other coin exists to produce blocks while the premine matures.
 */
inline bool IsStakeMature(int nCoinHeight, int nSpendHeight, const Consensus::Params& params)
{
    return nCoinHeight == 0 || nSpendHeight - nCoinHeight >= params.nCoinbaseMaturity;
}

/**
 * FirstIslamicCoin: the fixed-reward invariant. nActualStakeReward is the
 * coinstake's value out minus value in; it must equal the fixed block reward
 * plus nFees exactly, whatever the amount or age of the coins staked.
 */
bool IsValidCoinstakeReward(CAmount nActualStakeReward, CAmount nFees, int nHeight, const Consensus::Params& params);

#endif // CODEXACOIN_POS_H
