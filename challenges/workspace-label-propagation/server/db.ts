/**
 * In-memory tickets and the label set for each workspace.
 * TicketRow.labelIds is optional on input and stored as an array.
 * listLabels returns a copy of that workspace's labels, or [] if the workspace was never seeded.
 */
export interface TicketRow { id: string; workspaceId: string; title: string; labelIds?: string[]; }
const tickets = new Map<string, TicketRow>();
const workspaceLabels = new Map<string, { id: string; name: string }[]>();
export function resetDb(): void { tickets.clear(); workspaceLabels.clear(); }
export function seedWorkspace(workspaceId: string, labels: { id: string; name: string }[]): void { workspaceLabels.set(workspaceId, labels); }
export function seedTicket(row: TicketRow): void { tickets.set(row.id, { ...row, labelIds: row.labelIds ? [...row.labelIds] : [] }); }
export function getTicket(id: string): TicketRow | undefined {
  const row = tickets.get(id);
  return row ? { ...row, labelIds: [...(row.labelIds ?? [])] } : undefined;
}
export function saveTicket(row: TicketRow): TicketRow {
  const copy = { ...row, labelIds: [...(row.labelIds ?? [])] };
  tickets.set(row.id, copy); return getTicket(row.id)!;
}
export function listLabels(workspaceId: string) { return [...(workspaceLabels.get(workspaceId) ?? [])]; }
