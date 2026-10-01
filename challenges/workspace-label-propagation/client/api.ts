export interface Ticket { id: string; workspaceId: string; title: string; labelIds?: string[]; }
export interface Label { id: string; name: string; }
let baseUrl = '';
export function setBaseUrl(url: string): void { baseUrl = url.replace(/\/$/, ''); }
export async function getTicket(id: string): Promise<Ticket> {
  const res = await fetch(`${baseUrl}/tickets/${id}`);
  if (!res.ok) throw new Error('failed');
  return res.json();
}
export async function getLabels(workspaceId: string): Promise<Label[]> {
  const res = await fetch(`${baseUrl}/workspaces/${workspaceId}/labels`);
  if (!res.ok) throw new Error('failed');
  return res.json();
}
export async function setTicketLabels(id: string, labelIds: string[]): Promise<Ticket> {
  const res = await fetch(`${baseUrl}/tickets/${id}/labels`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ labelIds }),
  });
  if (!res.ok) throw new Error('failed');
  return res.json();
}
