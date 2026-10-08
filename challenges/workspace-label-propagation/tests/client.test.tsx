// @vitest-environment jsdom
import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { TicketLabels } from '../client/TicketLabels';
import { setBaseUrl } from '../client/api';
beforeEach(() => {
  setBaseUrl('http://example.test');
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/tickets/t1') && !u.includes('/labels')) {
      return { ok: true, json: async () => ({ id: 't1', workspaceId: 'ws1', title: 'Login broken', labelIds: ['lbl_bug'] }) };
    }
    if (u.includes('/workspaces/')) {
      return { ok: true, json: async () => [{ id: 'lbl_bug', name: 'Bug' }, { id: 'lbl_urgent', name: 'Urgent' }] };
    }
    return { ok: true, json: async () => ({}) };
  }));
});
it('loads selected from ticket.labelIds', async () => {
  render(<TicketLabels ticketId="t1" />);
  await waitFor(() => expect(screen.getByTestId('title').textContent).toBe('Login broken'));
  await waitFor(() => expect(screen.getByTestId('selected').textContent).toBe('lbl_bug'));
});
