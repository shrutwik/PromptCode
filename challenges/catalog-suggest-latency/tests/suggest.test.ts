import { describe, it, expect, beforeEach } from 'vitest';
import { buildCatalog } from '../src/catalog.js';
import { suggest } from '../src/suggest.js';
import { scoreProduct, compareRank } from '../src/rank.js';
import { globalCounter } from '../src/queryCounter.js';
import { resetCatalog, suggestProducts, scanCount } from '../src/service.js';
beforeEach(() => { globalCounter.reset(); resetCatalog(10_000); });
describe('ranking', () => {
  it('handles empty input, whitespace queries, and an explicit zero limit', () => {
    const rows = [{ id: 'a', title: 'A', category: 'phone', popularity: 1, tokens: ['phone'] }];
    expect(suggest([], 'phone')).toEqual([]);
    expect(suggest(rows, '   ')).toEqual([]);
    expect(suggest(rows, 'phone', { limit: 0 })).toEqual([]);
  });
  it('ranks multiple normalized tokens without mutating the catalog', () => {
    const rows = [{ id: 'b', title: 'B', category: 'x', popularity: 100, tokens: ['phone'] },
      { id: 'a', title: 'A', category: 'case', popularity: 1, tokens: ['phone', 'case'] }];
    const before = JSON.stringify(rows);
    expect(suggest(rows, ' PHONE   case ').map(row => row.id)).toEqual(['a', 'b']);
    expect(JSON.stringify(rows)).toBe(before);
  });
  it('deterministic ids', () => {
    const catalog = buildCatalog(500);
    globalCounter.reset();
    const a = suggest(catalog, 'kitchen item', { limit: 5 }).map((p) => p.id);
    globalCounter.reset();
    const b = suggest(catalog, 'kitchen item', { limit: 5 }).map((p) => p.id);
    expect(a).toEqual(b);
  });
  it('compareRank ordering', () => {
    const catalog = buildCatalog(20);
    const rows = catalog.map((product) => ({ score: scoreProduct(['tools'], product), product }));
    rows.sort(compareRank);
    for (let i = 1; i < rows.length; i++) expect(compareRank(rows[i - 1], rows[i])).toBeLessThanOrEqual(0);
  });
});
describe('latency and scans', () => {
  it('warmed median suggest latency stays under 200ms on 10k', () => {
    for (let i = 0; i < 3; i++) suggestProducts('electronics item', 10);
    const samples = Array.from({ length: 7 }, () => {
      const start = performance.now();
      const results = suggestProducts('electronics item', 10);
      const elapsed = performance.now() - start;
      expect(results.length).toBe(10);
      return elapsed;
    }).sort((a, b) => a - b);
    expect(samples[3]).toBeLessThan(200);
  });
  it('scan work grows linearly across catalog sizes', () => {
    for (const size of [100, 1000, 10000]) {
      resetCatalog(size);
      suggestProducts('garden item', 10);
      expect(scanCount()).toBeGreaterThanOrEqual(size);
      expect(scanCount()).toBeLessThanOrEqual(size * 2);
    }
  });
  it('fewer than 20k scans on 10k catalog', () => {
    suggestProducts('garden item', 10);
    expect(scanCount()).toBeLessThan(20_000);
  });
});
