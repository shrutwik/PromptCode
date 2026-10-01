import React, { useEffect, useState, useSyncExternalStore } from 'react';
import { getSnapshot, subscribe, loadFeed, markAsRead, unreadCount } from './feedStore';
export function NotificationList(): React.ReactElement {
  const items = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const [busy, setBusy] = useState<string | null>(null);
  useEffect(() => { void loadFeed(); }, []);
  return (
    <div>
      <div data-testid="unread-count">{unreadCount()}</div>
      <ul>
        {items.map((n) => (
          <li key={n.id}>
            <span data-testid={`read-${n.id}`}>{n.read ? 'read' : 'unread'}</span>
            {!n.read && (
              <button data-testid={`mark-${n.id}`} disabled={busy===n.id}
                onClick={() => { setBusy(n.id); void markAsRead(n.id).finally(() => setBusy(null)); }}>
                Mark read
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
