import { describe, it, expect, beforeEach } from 'vitest';
import { canTransition, allowedTargets } from '../src/statusMachine.js';
import { transitionInvoice } from '../src/invoiceService.js';
import { resetStore, seedInvoice } from '../src/store.js';
import { handleRequest } from '../src/api.js';
beforeEach(() => {
  resetStore();
  seedInvoice({ id: 'inv_1', customerId: 'cus_1', amountCents: 5000, status: 'draft', issuedAt: '2024-06-01T15:00:00.000Z', updatedAt: '2024-06-01T15:00:00.000Z' });
  seedInvoice({ id: 'inv_paid', customerId: 'cus_1', amountCents: 1200, status: 'paid', issuedAt: '2024-05-01T12:00:00.000Z', updatedAt: '2024-05-02T12:00:00.000Z' });
});
describe('allowed transitions', () => {
  it('draft can go to sent', () => { expect(canTransition('draft', 'sent')).toBe(true); expect(transitionInvoice('inv_1', 'sent').status).toBe('sent'); });
  it('sent can go to paid', () => { transitionInvoice('inv_1', 'sent'); expect(transitionInvoice('inv_1', 'paid').status).toBe('paid'); });
  it('paid can go to void', () => { expect(transitionInvoice('inv_paid', 'void').status).toBe('void'); });
  it('void has no targets', () => { expect(allowedTargets('void')).toEqual([]); });
  it('API returns 409 for sent -> draft', () => {
    transitionInvoice('inv_1', 'sent');
    expect(handleRequest({ method: 'POST', path: '/invoices/inv_1/transition', body: { status: 'draft' } }).status).toBe(409);
  });
  it('rejects paid -> draft', () => {
    expect(canTransition('paid', 'draft')).toBe(false);
    expect(() => transitionInvoice('inv_paid', 'draft')).toThrow(/Illegal transition/);
  });
});
