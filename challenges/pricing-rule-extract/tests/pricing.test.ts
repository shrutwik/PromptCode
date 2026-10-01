import { describe, it, expect } from 'vitest';
import { quote, applyRules } from '../src/pricingEngine.js';
import { roundHalfUp } from '../src/money.js';
describe('golden quotes', () => {
  it('applies percent then amount then surcharge', () => {
    const result = quote({
      baseCents: 10000,
      rules: [
        { type: 'surcharge_percent', pct: 10, code: 'surch' },
        { type: 'amount_off', cents: 500, code: 'flat' },
        { type: 'percent_off', pct: 15, code: 'vip' },
      ],
    });
    expect(result.finalCents).toBe(8800);
    expect(result.applied).toEqual(['vip', 'flat', 'surch']);
  });
  it('half-up rounding', () => {
    expect(roundHalfUp(2.5)).toBe(3);
    const result = quote({ baseCents: 1001, rules: [{ type: 'percent_off', pct: 10, code: 'p' }] });
    expect(result.finalCents).toBe(1001 - roundHalfUp((1001 * 10) / 100));
  });
  it('empty rules', () => { expect(quote({ baseCents: 42, rules: [] }).finalCents).toBe(42); });
  it('zero base non-negative', () => {
    expect(quote({ baseCents: 0, rules: [{ type: 'amount_off', cents: 50, code: 'x' }] }).finalCents).toBe(0);
  });
  it('applyRules matches quote', () => {
    const rules = [{ type: 'percent_off' as const, pct: 5, code: 'a' }, { type: 'amount_off' as const, cents: 10, code: 'b' }];
    expect(applyRules(2000, rules)).toEqual(quote({ baseCents: 2000, rules }));
  });
});
