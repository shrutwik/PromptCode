/**
 * Invoice vocabulary.
 * amountCents is an integer. issuedAt and updatedAt are ISO strings.
 * TransitionError is the domain error for a missing invoice or a refused move.
 */
export type InvoiceStatus = 'draft' | 'sent' | 'paid' | 'void';
export interface Invoice {
  id: string; customerId: string; amountCents: number; status: InvoiceStatus; issuedAt: string; updatedAt: string;
}
export class TransitionError extends Error {
  constructor(message: string) { super(message); this.name = 'TransitionError'; }
}
