// Test-only loopback server. Serves real assets and reviewed question fixtures.
import { createServer } from 'node:http';
import { readFileSync, mkdtempSync, symlinkSync, rmSync } from 'node:fs';
import { resolve, join, extname, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';
import { execFileSync } from 'node:child_process';
import { buildSync } from 'esbuild';

const qa = fileURLToPath(new URL('.', import.meta.url));
const root = resolve(qa, '../..');
const frontend = join(root, 'frontend');
const monaco = join(qa, 'node_modules/monaco-editor/min');
const scratch = mkdtempSync(join(tmpdir(), 'promptcode-browser-'));
const questions = { feed: 'notification-feed-stale', labels: 'workspace-label-propagation',
  canvas: 'canvas-document-editor', search: 'movie-search-routing' };
const bundles = new Map();
const python = process.env.PROMPTCODE_QA_PYTHON || 'python3';
execFileSync(python, ['-c', `
import sys
from pathlib import Path
sys.path[:0] = [${JSON.stringify(join(root, 'backend'))}, ${JSON.stringify(join(root, 'backend/tests'))}]
from trusted_reference_fixtures import reference_snapshot
for slug in ['notification-feed-stale', 'workspace-label-propagation', 'canvas-document-editor', 'movie-search-routing']:
    reference_snapshot(slug, Path(${JSON.stringify(scratch)}) / slug)
`], { cwd: root });

for (const [name, slug] of Object.entries(questions)) {
  for (const variant of ['starter', 'reference']) {
    const source = variant === 'reference' ? join(scratch, slug) : join(root, 'challenges', slug);
    if (variant === 'reference') symlinkSync(join(root, 'challenges', slug, 'node_modules'), join(source, 'node_modules'), 'dir');
    const components = { feed: ['NotificationList', './src/NotificationList', '<NotificationList />'],
      labels: ['TicketLabels', './client/TicketLabels', '<TicketLabels ticketId="ticket" />'],
      canvas: ['CanvasEditor', './src/CanvasEditor', '<CanvasEditor />'],
      search: ['MovieApp', './src/MovieApp', '<MovieApp />'] };
    const [exportName, component, element] = components[name];
    const setup = name === 'feed'
      ? "import {seedServer} from './src/api';seedServer([{id:'a',title:'First',read:false},{id:'b',title:'Second',read:false}]);"
      : name === 'search' ? "history.replaceState({},'', '/movies');" : '';
    const entry = `import React from 'react';import {createRoot} from 'react-dom/client';import {${exportName}} from '${component}';${setup}createRoot(document.getElementById('root')).render(${element});`;
    const result = buildSync({ stdin: { contents: entry, resolveDir: source, loader: 'tsx' }, bundle: true, platform: 'browser', write: false });
    bundles.set(`${name}/${variant}`, result.outputFiles[0].contents);
  }
}

const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.ttf': 'font/ttf' };
const cdn = 'https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/';
const server = createServer((req, res) => {
  try {
    const url = new URL(req.url, 'http://127.0.0.1:4173');
    if (url.pathname === '/health') { res.end('ok'); return; }
    // Unload keepalive requests need a real response: WebKit cannot fulfill
    // an intercepted request after its initiating document has been destroyed.
    const timer = url.pathname.match(/^\/api\/interview\/sessions\/([a-f0-9-]+)\/timer$/);
    if (timer && req.method === 'POST') {
      let raw = '';
      req.on('data', chunk => { raw += chunk; if (raw.length > 4096) req.destroy(); });
      req.on('end', () => {
        try {
          const { action } = JSON.parse(raw);
          if (!['pause', 'resume', 'heartbeat'].includes(action)) { res.writeHead(400).end(); return; }
          res.setHeader('Content-Type', 'application/json');
          res.end(JSON.stringify({ id: timer[1], challenge_slug: 'order-hold-reason', status: 'active',
            elapsed_ms: 0, timer_running: action !== 'pause', timer_lease_ms: action === 'pause' ? 0 : 60000 }));
        } catch { res.writeHead(400).end(); }
      });
      return;
    }
    // Disposable, read-only API fixture for reload tests without interception.
    const fixtureSession = { id: '11111111-1111-4111-8111-111111111111',
      challenge_slug: 'order-hold-reason', status: 'active', elapsed_ms: 0,
      timer_running: false, timer_lease_ms: 60000 };
    const fixtureBase = '/api/interview/sessions/' + fixtureSession.id;
    if (url.pathname.startsWith(fixtureBase)) {
      res.setHeader('Content-Type', 'application/json');
      if (url.pathname === fixtureBase + '/bootstrap' && req.method === 'GET') {
        res.end(JSON.stringify({ session: fixtureSession, files: [{ path: 'README.md' }, { path: 'src/answer.py' }],
          level: null, readme: { content: '# Order hold', revision: 1 } })); return;
      }
      if (url.pathname === fixtureBase + '/files/src/answer.py' && req.method === 'GET') {
        res.end(JSON.stringify({ content: 'answer = 42\n', revision: 1 })); return;
      }
      if (url.pathname === fixtureBase + '/events' && req.method === 'POST') { res.end('{}'); return; }
      res.writeHead(404).end(); return;
    }
    const question = url.pathname.match(/^\/_questions\/(feed|labels|canvas|search)$/);
    if (question) {
      const variant = url.searchParams.get('variant') || 'starter';
      if (!['starter', 'reference'].includes(variant)) { res.writeHead(404).end(); return; }
      res.setHeader('Content-Type', 'text/html');
      res.end(`<html lang="en"><head><title>Question browser fixture</title></head><body><div id="root"></div><script src="/_bundle/${question[1]}/${variant}.js"></script></body></html>`);
      return;
    }
    if (url.pathname.startsWith('/_bundle/')) {
      const bundle = bundles.get(url.pathname.slice('/_bundle/'.length).replace(/\.js$/, ''));
      if (!bundle) { res.writeHead(404).end(); return; }
      res.setHeader('Content-Type', 'text/javascript'); res.end(bundle); return;
    }
    const assetRoot = url.pathname.startsWith('/_monaco/') ? monaco : frontend;
    let rel = url.pathname.startsWith('/_monaco/') ? url.pathname.slice(9) : url.pathname.replace(/^\/static\//, '');
    if (url.pathname === '/challenges') rel = 'interview-challenges.html';
    else if (url.pathname.startsWith('/challenges/')) rel = 'interview-challenge.html';
    if (url.pathname.startsWith('/session/')) rel = 'interview-session.html';
    const path = resolve(assetRoot, decodeURIComponent(rel).replace(/^\//, ''));
    if (!path.startsWith(assetRoot + sep)) { res.writeHead(404).end(); return; }
    let body = readFileSync(path);
    if (['.js', '.html'].includes(extname(path))) body = Buffer.from(body.toString().replaceAll(cdn, '/_monaco/'));
    res.setHeader('Content-Type', types[extname(path)] || 'application/octet-stream');
    res.end(body);
  } catch { res.writeHead(404).end(); }
});
server.listen(4173, '127.0.0.1');
function stop() { server.close(); rmSync(scratch, { recursive: true, force: true }); }
process.on('SIGTERM', () => { stop(); process.exit(0); });
process.on('SIGINT', () => { stop(); process.exit(0); });
