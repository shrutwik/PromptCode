/**
 * Quote a price in integer cents.
 * quote applies sortRulesForApply order: percent_off, then amount_off, then surcharge_percent.
 * Percent math uses roundHalfUp. The result is floored at 0.
 * QuoteResult.applied is the rule codes that ran, in that same order.
 */
import { roundHalfUp } from './money.js';
import { sortRulesForApply, type Rule } from './rules.js';
export interface QuoteInput { baseCents: number; rules: Rule[]; }
export interface QuoteResult { finalCents: number; applied: string[]; }
export function quote(input: QuoteInput): QuoteResult {
  let amount = input.baseCents;
  const applied: string[] = [];
  const ordered = sortRulesForApply(input.rules);
  for (const rule of ordered) {
    if (rule.type === 'percent_off') {
      amount -= roundHalfUp((amount * rule.pct) / 100);
      applied.push(rule.code);
    } else if (rule.type === 'amount_off') {
      amount -= rule.cents;
      applied.push(rule.code);
    } else if (rule.type === 'surcharge_percent') {
      amount += roundHalfUp((amount * rule.pct) / 100);
      applied.push(rule.code);
    }
  }
  if (amount < 0) amount = 0;
  return { finalCents: amount, applied };
}
/** baseCents plus rules in, finalCents and applied codes out. */
export function applyRules(baseCents: number, rules: Rule[]): QuoteResult {
  return quote({ baseCents, rules });
}
