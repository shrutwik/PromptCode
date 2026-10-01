import express from 'express';
import cors from 'cors';
import * as db from './db.js';
export function createApp() {
  const app = express();
  app.use(cors());
  app.use(express.json());
  app.get('/workspaces/:ws/labels', (req, res) => res.json(db.listLabels(req.params.ws)));
  app.get('/tickets/:id', (req, res) => {
    const ticket = db.getTicket(req.params.id);
    if (!ticket) return res.status(404).json({ error: 'not found' });
    const { id, workspaceId, title } = ticket;
    res.json({ id, workspaceId, title });
  });
  app.put('/tickets/:id/labels', (req, res) => {
    const ticket = db.getTicket(req.params.id);
    if (!ticket) return res.status(404).json({ error: 'not found' });
    const labelIds = Array.isArray(req.body?.labelIds) ? (req.body.labelIds as string[]) : [];
    const allowed = new Set(db.listLabels(ticket.workspaceId).map((l) => l.id));
    if (labelIds.some((id) => !allowed.has(id))) return res.status(400).json({ error: 'unknown label' });
    const saved = db.saveTicket({ ...ticket, labelIds });
    res.json({ id: saved.id, workspaceId: saved.workspaceId, title: saved.title });
  });
  return app;
}
