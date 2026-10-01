import { transitionInvoice, describeInvoice } from './invoiceService.js';
import type { InvoiceStatus } from './types.js';
export interface HttpRequest { method: string; path: string; body?: { status?: InvoiceStatus; timeZone?: string }; }
export interface HttpResponse { status: number; body: unknown; }
export function handleRequest(req: HttpRequest): HttpResponse {
  const match = req.path.match(/^\/invoices\/([^/]+)(?:\/(transition|describe))?$/);
  if (!match) return { status: 404, body: { error: 'not found' } };
  const id = match[1]; const action = match[2];
  try {
    if (req.method === 'POST' && action === 'transition') {
      if (!req.body?.status) return { status: 400, body: { error: 'status required' } };
      return { status: 200, body: transitionInvoice(id, req.body.status) };
    }
    if (req.method === 'GET' && action === 'describe') {
      return { status: 200, body: { text: describeInvoice(id, req.body?.timeZone) } };
    }
    return { status: 405, body: { error: 'method not allowed' } };
  } catch (err) {
    const message = (err as Error).message;
    return { status: message.includes('not found') ? 404 : 409, body: { error: message } };
  }
}
