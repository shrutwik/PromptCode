import { describe, it, expect, beforeEach } from 'vitest';
import request from 'supertest';
import { createApp } from '../server/app.js';
import * as db from '../server/db.js';
const app = createApp();
beforeEach(() => {
  db.resetDb();
  db.seedWorkspace('ws1', [{ id: 'lbl_bug', name: 'Bug' }, { id: 'lbl_urgent', name: 'Urgent' }]);
  db.seedTicket({ id: 't1', workspaceId: 'ws1', title: 'Login broken', labelIds: [] });
});
it('round trips labelIds', async () => {
  const put = await request(app).put('/tickets/t1/labels').send({ labelIds: ['lbl_bug', 'lbl_urgent'] });
  expect(put.status).toBe(200);
  expect(put.body.labelIds).toEqual(['lbl_bug', 'lbl_urgent']);
  expect((await request(app).get('/tickets/t1')).body.labelIds).toEqual(['lbl_bug', 'lbl_urgent']);
});
