import React from 'react';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react';
import { NotificationList } from '../src/NotificationList';
import { seedServer } from '../src/api';
import { resetStore, loadFeed, markAsRead, unreadCount, getSnapshot } from '../src/feedStore';
afterEach(() => { cleanup(); });
beforeEach(() => {
  resetStore();
  seedServer([
    { id: 'n1', title: 'Welcome', read: false },
    { id: 'n2', title: 'Invoice', read: false },
    { id: 'n3', title: 'Ship', read: true },
  ]);
});
describe('UI', () => {
  it('shows unread count', async () => {
    render(<NotificationList />);
    await waitFor(() => expect(screen.getByTestId('unread-count').textContent).toBe('2'));
  });
  it('marks one read', async () => {
    render(<NotificationList />);
    await waitFor(() => screen.getByTestId('mark-n1'));
    fireEvent.click(screen.getByTestId('mark-n1'));
    await waitFor(() => expect(screen.getByTestId('unread-count').textContent).toBe('1'));
  });
});
describe('concurrency', () => {
  it('marks two without clobber', async () => {
    await loadFeed();
    await Promise.all([markAsRead('n1'), markAsRead('n2')]);
    expect(unreadCount()).toBe(0);
    expect(getSnapshot().filter(n => n.id !== 'n3').every(n => n.read)).toBe(true);
  });
});
