/**
 * Counts rows a suggest pass reports via recordScan.
 * totalScans is what tests read. reset() zeroes it. globalCounter is the shared instance.
 */
export class QueryCounter {
  private scans = 0;
  reset(): void { this.scans = 0; }
  recordScan(n = 1): void { this.scans += n; }
  get totalScans(): number { return this.scans; }
}
export const globalCounter = new QueryCounter();
