/**
 * Display helper for issuedAt.
 * timeZone is an IANA name such as America/Chicago. The return value is a human string, not a status.
 */
export function formatInvoiceDate(iso: string, timeZone = 'UTC'): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) throw new Error(`Invalid date: ${iso}`);
  return new Intl.DateTimeFormat('en-US', { timeZone, year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(d);
}
