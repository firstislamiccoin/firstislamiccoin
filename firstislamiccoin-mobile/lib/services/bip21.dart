/// Parses a `firstislamiccoin:<address>[?amount=X]` URI, mirroring
/// web-wallet/app.js's parseBip21. Returns the input unchanged as the
/// address (with a null amount) if given a bare address instead of a
/// URI, so callers can pass either through this same function.
library;

class ParsedBip21 {
  final String address;
  final double? amount;
  const ParsedBip21(this.address, this.amount);
}

ParsedBip21 parseBip21(String text) {
  final trimmed = text.trim();
  if (!trimmed.toLowerCase().startsWith('firstislamiccoin:')) {
    return ParsedBip21(trimmed, null);
  }
  final withoutScheme = trimmed.substring('firstislamiccoin:'.length);
  final parts = withoutScheme.split('?');
  final address = parts[0];
  double? amount;
  if (parts.length > 1) {
    final query = Uri.splitQueryString(parts[1]);
    final amountStr = query['amount'];
    if (amountStr != null) amount = double.tryParse(amountStr);
  }
  return ParsedBip21(address, amount);
}

String buildBip21Uri(String address, {double? amount}) {
  if (amount == null || amount <= 0) return address;
  return 'firstislamiccoin:$address?amount=$amount';
}
