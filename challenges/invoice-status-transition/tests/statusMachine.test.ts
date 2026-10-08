import { describe, it, expect, beforeEach } from 'vitest';
import { canTransition, allowedTargets } from '../src/statusMachine.js';
import { transitionInvoice } from '../src/invoiceService.js';
import { resetStore, seedInvoice, getInvoice } from '../src/store.js';
import { handleRequest } from '../src/api.js';
beforeEach(() => {
  resetStore();
  seedInvoice({ id: 'inv_1', customerId: 'cus_1', amountCents: 5000, status: 'draft', issuedAt: '2024-06-01T15:00:00.000Z', updatedAt: '2024-06-01T15:00:00.000Z' });
  seedInvoice({ id: 'inv_paid', customerId: 'cus_1', amountCents: 1200, status: 'paid', issuedAt: '2024-05-01T12:00:00.000Z', updatedAt: '2024-05-02T12:00:00.000Z' });
});
describe('allowed transitions', () => {
  it('refused API changes preserve the invoice including money', () => {
    const before = { ...getInvoice('inv_paid')! };
    expect(handleRequest({ method: 'POST', path: '/invoices/inv_paid/transition', body: { status: 'draft' } }).status).toBe(409);
    expect(getInvoice('inv_paid')).toEqual(before);
  });
  it('missing status is a validation error with no mutation', () => {
    const before = { ...getInvoice('inv_1')! };
    expect(handleRequest({ method: 'POST', path: '/invoices/inv_1/transition', body: {} }).status).toBe(400);
    expect(getInvoice('inv_1')).toEqual(before);
  });
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

it('matches the entire legal graph rather than one patched paid edge', () => {
  const statuses = ['draft', 'sent', 'paid', 'void'] as const;
  const legal = new Set(['draft:sent', 'draft:void', 'sent:paid', 'sent:void', 'paid:void']);
  for (const from of statuses) for (const to of statuses) {
    expect(canTransition(from, to)).toBe(legal.has(`${from}:${to}`));
  }
});

it('Part 3: terminal-sequence-preserves',async()=>{
const {handleRequest}=await import('../src/api');
const {resetStore,seedInvoice,getInvoice}=await import('../src/store');
const result=await (async()=>{resetStore();seedInvoice({id:'chain',customerId:'c',status:'draft',amountCents:3001,issuedAt:'2026-01-01',updatedAt:'2026-01-01'});const statuses=(['sent','paid','void'] as const).map(status=>handleRequest({method:'POST',path:'/invoices/chain/transition',body:{status}}).status);const before=JSON.stringify(getInvoice('chain'));const denied=handleRequest({method:'POST',path:'/invoices/chain/transition',body:{status:'paid'}}).status;return [statuses,denied,getInvoice('chain')!.status,getInvoice('chain')!.amountCents,JSON.stringify(getInvoice('chain'))===before];})();
expect(result).toEqual([[200, 200, 200], 409, "void", 3001, true]);
});
