import type { Product } from './catalog.js';
export function scoreProduct(queryTokens: string[], product: Product): number {
  let score = 0;
  for (const qt of queryTokens) {
    if (product.tokens.includes(qt)) score += 10;
    if (product.category === qt) score += 5;
  }
  return score;
}
export function compareRank(a: { score: number; product: Product }, b: { score: number; product: Product }): number {
  if (b.score !== a.score) return b.score - a.score;
  if (b.product.popularity !== a.product.popularity) return b.product.popularity - a.product.popularity;
  return a.product.id.localeCompare(b.product.id);
}
