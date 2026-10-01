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
/** Candidate: make this the shared implementation used by quote. */
export function applyRules(baseCents: number, rules: Rule[]): QuoteResult {
  return quote({ baseCents, rules });
}
