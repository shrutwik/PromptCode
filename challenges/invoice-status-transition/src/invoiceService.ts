/**
 * Application operations on one invoice.
 * transitionInvoice loads the row, asks the state machine, and saves status plus updatedAt.
 * describeInvoice is a human sentence. It formats issuedAt; it does not change status.
 */
import { assertTransition } from './statusMachine.js';
import { getInvoice, saveInvoice } from './store.js';
import { TransitionError, type Invoice, type InvoiceStatus } from './types.js';
import { formatInvoiceDate } from './timezoneFormat.js';
export function transitionInvoice(id: string, next: InvoiceStatus): Invoice {
  const current = getInvoice(id);
  if (!current) throw new TransitionError(`Invoice ${id} not found`);
  try { assertTransition(current.status, next); }
  catch (err) { throw new TransitionError((err as Error).message); }
  return saveInvoice({ ...current, status: next, updatedAt: new Date().toISOString() });
}
export function describeInvoice(id: string, timeZone = 'America/Chicago'): string {
  const inv = getInvoice(id);
  if (!inv) throw new TransitionError(`Invoice ${id} not found`);
  return `${inv.id} ${inv.status} issued ${formatInvoiceDate(inv.issuedAt, timeZone)}`;
}
