import { describe, it, expect, beforeEach } from 'vitest';
import { buildCatalog } from '../src/catalog.js';
import { suggest } from '../src/suggest.js';
import { scoreProduct, compareRank } from '../src/rank.js';
import { globalCounter } from '../src/queryCounter.js';
import { resetCatalog, suggestProducts, scanCount } from '../src/service.js';
beforeEach(() => { globalCounter.reset(); resetCatalog(10_000); });
describe('ranking', () => {
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
  it('suggest under 200ms on 10k', () => {
    const start = performance.now();
    const results = suggestProducts('electronics item', 10);
    const elapsed = performance.now() - start;
    expect(results.length).toBeGreaterThan(0);
    expect(elapsed).toBeLessThan(200);
  });
  it('fewer than 20k scans on 10k catalog', () => {
    suggestProducts('garden item', 10);
    expect(scanCount()).toBeLessThan(20_000);
  });
});
