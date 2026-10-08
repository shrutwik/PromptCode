import { describe, it, expect, beforeEach } from 'vitest';
import request from 'supertest';
import { createApp } from '../server/app.js';
import * as db from '../server/db.js';
const app = createApp();
beforeEach(() => {
  db.resetDb();
  db.seedWorkspace('ws1', [{ id: 'lbl_bug', name: 'Bug' }, { id: 'lbl_urgent', name: 'Urgent' }]);
  db.seedTicket({ id: 't1', workspaceId: 'ws1', title: 'Login broken', labelIds: ['lbl_bug'] });
});
describe('API', () => {
  it('rejects mixed foreign labels without erasing saved labels', async () => {
    db.seedWorkspace('other', [{ id: 'private', name: 'Private' }]);
    const before = db.getTicket('t1');
    const response = await request(app).put('/tickets/t1/labels').send({ labelIds: ['lbl_urgent', 'private'] });
    expect(response.status).toBe(400);
    expect(db.getTicket('t1')).toEqual(before);
    expect((await request(app).get('/tickets/t1')).body.labelIds).toEqual(['lbl_bug']);
  });
  it('clears persisted labels with an empty list', async () => {
    expect((await request(app).put('/tickets/t1/labels').send({ labelIds: [] })).status).toBe(200);
    expect((await request(app).get('/tickets/t1')).body.labelIds).toEqual([]);
  });
  it('gets core fields', async () => {
    const res = await request(app).get('/tickets/t1');
    expect(res.status).toBe(200);
    expect(res.body.title).toBe('Login broken');
  });
  it('rejects unknown labels', async () => {
    expect((await request(app).put('/tickets/t1/labels').send({ labelIds: ['nope'] })).status).toBe(400);
  });
  it('lists labels', async () => {
    expect((await request(app).get('/workspaces/ws1/labels')).body).toHaveLength(2);
  });
});
