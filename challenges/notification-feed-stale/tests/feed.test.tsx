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
  it('coalesces repeated concurrent marks without losing other updates', async () => {
    await loadFeed();
    await Promise.all(['n1', 'n2', 'n1', 'n3', 'n2'].map(markAsRead));
    expect(unreadCount()).toBe(0);
    expect(getSnapshot().map(n => [n.id, n.read])).toEqual([['n1', true], ['n2', true], ['n3', true]]);
  });
  it('keeps the snapshot intact when a mark fails', async () => {
    await loadFeed();
    const before = JSON.stringify(getSnapshot());
    await expect(markAsRead('missing')).rejects.toThrow('not found');
    expect(JSON.stringify(getSnapshot())).toBe(before);
    expect(unreadCount()).toBe(2);
  });
  it('marks two without clobber', async () => {
    await loadFeed();
    await Promise.all([markAsRead('n1'), markAsRead('n2')]);
    expect(unreadCount()).toBe(0);
    expect(getSnapshot().filter(n => n.id !== 'n3').every(n => n.read)).toBe(true);
  });
});

it('renders converged read rows and badge after two quick actions', async () => {
  render(<NotificationList />);
  await waitFor(() => expect(screen.getByTestId('unread-count').textContent).toBe('2'));
  fireEvent.click(screen.getByTestId('mark-n1'));
  fireEvent.click(screen.getByTestId('mark-n2'));
  await waitFor(() => {
    expect(screen.getByTestId('read-n1').textContent).toBe('read');
    expect(screen.getByTestId('read-n2').textContent).toBe('read');
    expect(screen.getByTestId('unread-count').textContent).toBe('0');
  });
});

it('Part 3: mixed-success-failure',async()=>{
const {seedServer}=await import('../src/api');
const {resetStore,loadFeed,markAsRead,getSnapshot,unreadCount}=await import('../src/feedStore');
const result=await (async()=>{resetStore();seedServer([{"id": "a", "title": "a", "read": false}, {"id": "b", "title": "b", "read": false}]);await loadFeed();const settled=await Promise.allSettled([markAsRead('a'),markAsRead('missing'),markAsRead('b')]);return [unreadCount(),getSnapshot().map(n=>n.read),settled.map(r=>r.status)];})();
expect(result).toEqual([0, [true, true], ["fulfilled", "rejected", "fulfilled"]]);
});
