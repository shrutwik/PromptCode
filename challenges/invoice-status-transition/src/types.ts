export type InvoiceStatus = 'draft' | 'sent' | 'paid' | 'void';
export interface Invoice {
  id: string; customerId: string; amountCents: number; status: InvoiceStatus; issuedAt: string; updatedAt: string;
}
export class TransitionError extends Error {
  constructor(message: string) { super(message); this.name = 'TransitionError'; }
}
