// Copyright (c) 2009-2010 Satoshi Nakamoto
// Copyright (c) 2009-2022 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <consensus/amount.h>
#include <policy/feerate.h>
#include <tinyformat.h>

#include <cmath>
#include <limits>

CFeeRate::CFeeRate(const CAmount& nFeePaid, uint32_t num_bytes)
{
    const int64_t nSize{num_bytes};

    if (nSize > 0) {
        // FirstIslamicCoin: MAX_MONEY is INT64_MAX here (no fixed cap,
        // unlike Bitcoin's small 21e6*COIN), so a plain `nFeePaid * 1000`
        // can genuinely overflow CAmount before the /nSize ever brings it
        // back into range -- impossible upstream. Widen the multiply to
        // __int128 (already used elsewhere in this codebase, e.g.
        // util/fastrange.h) so the division sees the true product; only
        // clamp if the final rate itself doesn't fit back in a CAmount.
        const __int128 rate = (static_cast<__int128>(nFeePaid) * 1000) / nSize;
        nSatoshisPerK = rate > std::numeric_limits<CAmount>::max()
                            ? std::numeric_limits<CAmount>::max()
                            : static_cast<CAmount>(rate);
    } else {
        nSatoshisPerK = 0;
    }
}

CAmount CFeeRate::GetFee(uint32_t num_bytes) const
{
    const int64_t nSize{num_bytes};

    // Be explicit that we're converting from a double to int64_t (CAmount) here.
    // We've previously had issues with the silent double->int64_t conversion.
    CAmount nFee{static_cast<CAmount>(std::ceil(nSatoshisPerK * nSize / 1000.0))};

    if (nFee == 0 && nSize != 0) {
        if (nSatoshisPerK > 0) nFee = CAmount(1);
        if (nSatoshisPerK < 0) nFee = CAmount(-1);
    }

    return nFee;
}

std::string CFeeRate::ToString(const FeeEstimateMode& fee_estimate_mode) const
{
    switch (fee_estimate_mode) {
    case FeeEstimateMode::SAT_VB: return strprintf("%d.%03d %s/vB", nSatoshisPerK / 1000, nSatoshisPerK % 1000, CURRENCY_ATOM);
    default:                      return strprintf("%d.%08d %s/kvB", nSatoshisPerK / COIN, nSatoshisPerK % COIN, CURRENCY_UNIT);
    }
}
