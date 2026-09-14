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
        // back into range -- impossible upstream. Widen the multiply so the
        // division sees the true product; only clamp if the final rate
        // itself doesn't fit back in a CAmount.
#ifdef __SIZEOF_INT128__
        // Precedent already in this codebase: util/fastrange.h, crypto/muhash.h.
        const __int128 rate = (static_cast<__int128>(nFeePaid) * 1000) / nSize;
        nSatoshisPerK = rate > std::numeric_limits<CAmount>::max()
                            ? std::numeric_limits<CAmount>::max()
                            : static_cast<CAmount>(rate);
#else
        // No native 128-bit integer on this target (e.g. 32-bit builds --
        // this is the branch that caught linux-32-bit/linux-arm-32-bit
        // failing to even compile the __int128 one). Fall back to double
        // precision: only the pathological near-MAX_MONEY fee this exists
        // for at all can lose exactness here, and even then only in the
        // low bits -- real fees (always tiny relative to MAX_MONEY, see
        // consensus/tx_verify.cpp's TX_FEE_PER_KB) round-trip exactly
        // either way.
        const double rate = (static_cast<double>(nFeePaid) * 1000.0) / static_cast<double>(nSize);
        nSatoshisPerK = rate > static_cast<double>(std::numeric_limits<CAmount>::max())
                            ? std::numeric_limits<CAmount>::max()
                            : static_cast<CAmount>(rate);
#endif
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
