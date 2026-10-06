/**
 * In-memory invoice rows, keyed by id.
 * getInvoice and saveInvoice return copies so callers cannot mutate the map by accident.
 * resetStore and seedInvoice exist so tests start from a known set.
 */
import type { Invoice } from './types.js';
const invoices = new Map<string, Invoice>();
export function resetStore(): void { invoices.clear(); }
export function seedInvoice(invoice: Invoice): void { invoices.set(invoice.id, { ...invoice }); }
export function getInvoice(id: string): Invoice | undefined { const row = invoices.get(id); return row ? { ...row } : undefined; }
export function saveInvoice(invoice: Invoice): Invoice { const copy = { ...invoice }; invoices.set(invoice.id, copy); return { ...copy }; }
