// @vitest-environment jsdom
import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react';
import { TicketLabels } from '../client/TicketLabels';
import { setBaseUrl } from '../client/api';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
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

it('hydrates persisted checkboxes after saving and remounting', async () => {
  let saved = ['lbl_bug'];
  vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => {
    if (options?.method === 'PUT') saved = JSON.parse(String(options.body)).labelIds;
    const labels = [{ id: 'lbl_bug', name: 'Bug' }, { id: 'lbl_urgent', name: 'Urgent' }];
    return { ok: true, json: async () => String(url).includes('/workspaces/') ? labels
      : { id: 't1', workspaceId: 'ws1', title: 'Login broken', labelIds: [...saved] } };
  }));
  const first = render(<TicketLabels ticketId="t1" />);
  await waitFor(() => expect(screen.getByTestId('selected').textContent).toBe('lbl_bug'));
  await waitFor(() => expect(screen.getByTestId('label-lbl_urgent')).toBeTruthy());
  fireEvent.click(screen.getByTestId('label-lbl_urgent'));
  await waitFor(() => expect(saved).toEqual(['lbl_bug', 'lbl_urgent']));
  first.unmount();
  render(<TicketLabels ticketId="t1" />);
  await waitFor(() => expect(screen.getByTestId('selected').textContent).toBe('lbl_bug,lbl_urgent'));
  expect((screen.getByTestId('label-lbl_bug') as HTMLInputElement).checked).toBe(true);
  expect((screen.getByTestId('label-lbl_urgent') as HTMLInputElement).checked).toBe(true);
});
