import type { Notification } from './types';
let serverState: Notification[] = [];
export function seedServer(rows: Notification[]): void { serverState = rows.map((r) => ({ ...r })); }
export async function fetchNotifications(): Promise<Notification[]> { return serverState.map((r) => ({ ...r })); }
export async function markReadOnServer(id: string): Promise<Notification> {
  const row = serverState.find((n) => n.id === id);
  if (!row) throw new Error('not found');
  row.read = true; return { ...row };
}
