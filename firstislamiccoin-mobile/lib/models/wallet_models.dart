/// Plain data models for gateway API responses (see ../../docs/mobile-api.md).
library;

class Balance {
  final BigInt confirmed;
  final BigInt unconfirmed;
  const Balance(this.confirmed, this.unconfirmed);

  factory Balance.fromJson(Map<String, dynamic> json) => Balance(
        BigInt.parse(json['confirmed'] as String),
        BigInt.parse(json['unconfirmed'] as String),
      );

  BigInt get total => confirmed + unconfirmed;
}

class TxSummary {
  final String txid;
  // Null for a pending/unconfirmed transaction -- the gateway's history
  // endpoint genuinely returns a JSON null here (see
  // vps-gateway/app.py's address_history: height = t.get("blockheight"),
  // which is None until the tx is mined), so this must stay nullable
  // rather than force-cast to int.
  final int? height;
  final int? fee;
  const TxSummary({required this.txid, required this.height, this.fee});

  factory TxSummary.fromJson(Map<String, dynamic> json) => TxSummary(
        txid: json['txid'] as String,
        height: json['height'] as int?,
        fee: json['fee'] as int?,
      );

  bool get isPending => height == null || height! <= 0;
}

class TxDetail {
  final String txid;
  // Null for a pending transaction -- same reasoning as TxSummary.height
  // (vps-gateway/app.py's tx_detail: height = None until a blockhash
  // exists for it).
  final int? height;
  final int confirmations;
  final bool isCoinstake;
  final BigInt? rewardSatoshis;
  const TxDetail({
    required this.txid,
    required this.height,
    required this.confirmations,
    required this.isCoinstake,
    this.rewardSatoshis,
  });

  bool get isPending => height == null || height! <= 0;

  factory TxDetail.fromJson(Map<String, dynamic> json) => TxDetail(
        txid: json['txid'] as String,
        height: json['height'] as int?,
        confirmations: json['confirmations'] as int? ?? 0,
        isCoinstake: json['is_coinstake'] as bool? ?? false,
        rewardSatoshis: json['reward_satoshis'] != null
            ? BigInt.parse(json['reward_satoshis'] as String)
            : null,
      );
}

/// See docs/mobile-api.md §5. `mode` distinguishes 6A (custodial) from 6B
/// (non-custodial delegation) once that phase ships; no real backend
/// exists yet for either.
class StakingStatus {
  final String mode;
  final BigInt delegatedAmount;
  final BigInt accruedRewards;
  final int effectiveMonthlyRateBp;
  final int poolFeeBp;
  final bool canWithdraw;

  const StakingStatus({
    required this.mode,
    required this.delegatedAmount,
    required this.accruedRewards,
    required this.effectiveMonthlyRateBp,
    required this.poolFeeBp,
    required this.canWithdraw,
  });

  factory StakingStatus.fromJson(Map<String, dynamic> json) => StakingStatus(
        mode: json['mode'] as String,
        delegatedAmount: BigInt.parse(json['delegated_amount'] as String),
        accruedRewards: BigInt.parse(json['accrued_rewards'] as String),
        effectiveMonthlyRateBp: json['effective_monthly_rate_bp'] as int,
        poolFeeBp: json['pool_fee_bp'] as int,
        canWithdraw: json['can_withdraw'] as bool,
      );

  /// Not opted in to staking at all (distinct from "opted in, zero balance").
  /// `final`, not `const` -- BigInt.zero is a runtime static getter, not a
  /// compile-time constant, so this class's const constructor can't be
  /// invoked in a const context here.
  static final notOptedIn = StakingStatus(
    mode: 'none',
    delegatedAmount: BigInt.zero,
    accruedRewards: BigInt.zero,
    effectiveMonthlyRateBp: 114, // 1368 bp / 12
    poolFeeBp: 500,
    canWithdraw: false,
  );
}

/// Formats a satoshi amount (8 decimals) as a FIC display string.
String formatFic(BigInt satoshis) {
  final coin = BigInt.from(100000000);
  final whole = satoshis ~/ coin;
  final frac = (satoshis % coin).abs().toString().padLeft(8, '0');
  return '$whole.$frac';
}
