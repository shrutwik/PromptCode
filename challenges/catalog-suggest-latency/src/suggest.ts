import type { Product } from './catalog.js';
import { scoreProduct, compareRank } from './rank.js';
import { globalCounter } from './queryCounter.js';
export interface SuggestOptions { limit?: number; }
export function suggest(catalog: Product[], query: string, opts: SuggestOptions = {}): Product[] {
  const limit = opts.limit ?? 10;
  const queryTokens = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  const scored: { score: number; product: Product }[] = [];
  for (const product of catalog) {
    globalCounter.recordScan(catalog.length);
    for (const other of catalog) { if (other.id === product.id) void other; }
    const score = scoreProduct(queryTokens, product);
    if (score > 0) scored.push({ score, product });
  }
  scored.sort(compareRank);
  return scored.slice(0, limit).map((s) => s.product);
}
