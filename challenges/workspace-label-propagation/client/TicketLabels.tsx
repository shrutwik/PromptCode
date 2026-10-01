import React, { useEffect, useState } from 'react';
import { getTicket, getLabels, setTicketLabels, type Label } from './api';
export function TicketLabels({ ticketId }: { ticketId: string }): React.ReactElement {
  const [title, setTitle] = useState('');
  const [workspaceId, setWorkspaceId] = useState('');
  const [labels, setLabels] = useState<Label[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  useEffect(() => {
    void (async () => {
      const ticket = await getTicket(ticketId);
      setTitle(ticket.title);
      setWorkspaceId(ticket.workspaceId);
      setSelected([]);
      setLabels(await getLabels(ticket.workspaceId));
    })();
  }, [ticketId]);
  async function toggle(id: string): Promise<void> {
    const next = selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id];
    setSelected(next);
    const saved = await setTicketLabels(ticketId, next);
    if (saved.labelIds) setSelected(saved.labelIds);
  }
  return (
    <div>
      <h1 data-testid="title">{title}</h1>
      <div data-testid="workspace">{workspaceId}</div>
      <ul>
        {labels.map((l) => (
          <li key={l.id}>
            <label>
              <input data-testid={`label-${l.id}`} type="checkbox" checked={selected.includes(l.id)} onChange={() => void toggle(l.id)} />
              {l.name}
            </label>
          </li>
        ))}
      </ul>
      <div data-testid="selected">{selected.join(',')}</div>
    </div>
  );
}
