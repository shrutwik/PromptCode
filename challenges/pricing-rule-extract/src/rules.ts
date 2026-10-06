/**
 * Pricing rules. percent_off and surcharge_percent carry pct (a number, not a fraction).
 * amount_off carries cents. Every rule has a code string.
 * sortRulesForApply orders percent_off, then amount_off, then surcharge_percent, then code.
 */
export type Rule =
  | { type: 'percent_off'; pct: number; code: string }
  | { type: 'amount_off'; cents: number; code: string }
  | { type: 'surcharge_percent'; pct: number; code: string };
export function sortRulesForApply(rules: Rule[]): Rule[] {
  const rank = (r: Rule) => (r.type === 'percent_off' ? 0 : r.type === 'amount_off' ? 1 : 2);
  return [...rules].sort((a, b) => {
    const d = rank(a) - rank(b);
    if (d !== 0) return d;
    return a.code.localeCompare(b.code);
  });
}
