export function recordAudit(event: string, meta: Record<string, unknown>): void {
  if (process.env.AUDIT_DEBUG === '1') console.log(JSON.stringify({ event, meta }));
}
