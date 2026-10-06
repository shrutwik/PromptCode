/**
 * Optional debug sink. Prints one JSON line only when AUDIT_DEBUG=1.
 * It is not on the transition path unless a caller records an event.
 */
export function recordAudit(event: string, meta: Record<string, unknown>): void {
  if (process.env.AUDIT_DEBUG === '1') console.log(JSON.stringify({ event, meta }));
}
