/**
 * Live catalog used by the service entry points.
 * resetCatalog rebuilds N products and clears the scan counter.
 * suggestProducts queries that catalog. scanCount reads the counter.
 */
import { buildCatalog, type Product } from './catalog.js';
import { suggest } from './suggest.js';
import { globalCounter } from './queryCounter.js';
let catalog: Product[] = buildCatalog(10_000);
export function resetCatalog(size = 10_000): void { catalog = buildCatalog(size); globalCounter.reset(); }
export function suggestProducts(query: string, limit = 10): Product[] { return suggest(catalog, query, { limit }); }
export function scanCount(): number { return globalCounter.totalScans; }
