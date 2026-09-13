/// Fiat value display: an honest placeholder, not a fetched number.
///
/// CAC's equivalent widget fetched a real (if thin) price from a
/// PancakeSwap pool on BNB Chain and a Stellar DEX order book -- both
/// only possible because CodexaCoin issues wrapped tokens on those
/// chains (`bnb-issuer/`, `stellar-issuer/`). FIC has neither: seeing no
/// wrapped-token/DEX component in the master prompt's own phase list,
/// and no reason this Shariah-conscious project should want one, this
/// build drops that whole category rather than porting it -- see
/// docs/CHANGELOG-FIC.md's "Decision 3" and docs/repo-map.md's
/// "Components with no FIC target". With it gone, there is no price
/// source of any kind to query, so this stays a plain, clearly-labeled
/// placeholder rather than fabricating a number.
library;

import 'package:flutter/material.dart';

class FiatPlaceholder extends StatelessWidget {
  final double ficAmount;
  const FiatPlaceholder({super.key, required this.ficAmount});

  @override
  Widget build(BuildContext context) {
    return Text(
      'Fiat value unavailable (no exchange listing exists for FIC yet)',
      style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey),
      textAlign: TextAlign.center,
    );
  }
}
