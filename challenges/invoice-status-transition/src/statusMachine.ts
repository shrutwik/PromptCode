import type { InvoiceStatus } from './types.js';
const ALLOWED: Record<InvoiceStatus, readonly InvoiceStatus[]> = {
  draft: ['sent', 'void'], sent: ['paid', 'void'], paid: ['void'], void: [],
};
export function canTransition(from: InvoiceStatus, to: InvoiceStatus): boolean {
  if (from === to) return false;
  // BUG: paid allows any non-void target (including draft)
  if (from === 'paid' && to !== 'void') return true;
  return ALLOWED[from].includes(to);
}
export function assertTransition(from: InvoiceStatus, to: InvoiceStatus): void {
  if (!canTransition(from, to)) throw new Error(`Illegal transition ${from} -> ${to}`);
}
export function allowedTargets(from: InvoiceStatus): InvoiceStatus[] { return [...ALLOWED[from]]; }
