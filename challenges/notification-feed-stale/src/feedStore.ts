/**
 * In-memory notification feed.
 * items is the list subscribers see. unreadCount is how many rows have read === false.
 * loadFeed replaces items from the server. markAsRead asks the server to mark one id, then updates items and emits.
 * subscribe returns an unsubscribe function.
 */
import type { Notification } from './types';
import { fetchNotifications, markReadOnServer } from './api';
type Listener = () => void;
let items: Notification[] = [];
let listeners: Listener[] = [];
function emit(): void { listeners.forEach((l) => l()); }
export function subscribe(listener: Listener): () => void {
  listeners.push(listener);
  return () => { listeners = listeners.filter((l) => l !== listener); };
}
export function getSnapshot(): Notification[] { return items; }
export function unreadCount(): number { return items.filter((n) => !n.read).length; }
export async function loadFeed(): Promise<void> { items = await fetchNotifications(); emit(); }
export async function markAsRead(id: string): Promise<void> {
  const snapshot = items.map((n) => ({ ...n }));
  await markReadOnServer(id);
  items = snapshot.map((n) => (n.id === id ? { ...n, read: true } : n));
  emit();
}
export function resetStore(): void { items = []; listeners = []; }
