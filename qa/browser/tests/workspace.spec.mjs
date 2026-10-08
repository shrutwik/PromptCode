import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const sessionId = '11111111-1111-4111-8111-111111111111';
const original = 'answer = 42\n';

async function workspace(page, options = {}) {
  const state = { saved: original, revision: 1, requests: [], runAttempts: 0, errors: [], unexpected: [] };
  const snapshot = { id: sessionId, challenge_slug: 'order-hold-reason', status: options.status || 'active',
    elapsed_ms: 0, timer_running: false, timer_lease_ms: 60000 };
  page.on('pageerror', error => state.errors.push(error.message));
  page.on('request', request => {
    if (new URL(request.url()).pathname.startsWith('/api/') && (options.liveFixture || new URL(request.url()).pathname.endsWith('/timer'))) {
      state.requests.push({ path: new URL(request.url()).pathname, method: request.method(), body: request.postDataJSON() });
    }
  });
  await page.addInitScript(() => {
    sessionStorage.setItem('access_token', 'qa-disposable-token');
    sessionStorage.setItem('pc_user', JSON.stringify({ id: 'qa-owner', email: 'qa@example.test' }));
  });
  if (!options.liveFixture) {
    // Remote fonts are irrelevant to behavior; editor assets are pinned and local.
    await page.context().route('https://**', route => route.abort());
    if (options.leaseConflict) {
      await page.context().route('**/api/interview/sessions/*/timer', route => route.fulfill({ status: 409,
        json: { detail: 'Another tab owns this session.' } }));
    }
    await page.context().route(/\/api\/(?!.*\/timer(?:\?|$)).*/, async route => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      const body = request.postDataJSON();
      state.requests.push({ path, method: request.method(), body });
      const reply = (value, status = 200, headers = {}) => route.fulfill({ status,
        headers: { 'Access-Control-Allow-Origin': 'http://127.0.0.1:4173', 'Access-Control-Allow-Credentials': 'true', ...headers },
        contentType: 'application/json', body: JSON.stringify(value) });
      const file = path.endsWith('/files/src/answer.py');
      if (path.endsWith('/bootstrap')) return reply({ session: snapshot,
        files: [{ path: 'README.md' }, { path: 'src/answer.py' }], level: null,
        readme: { content: '# Order hold\n\nPreserve the reason after a refresh.', revision: 1 } });
      if (file && request.method() === 'GET') return reply({ content: state.saved, revision: state.revision });
      if (file && request.method() === 'PUT') {
        if (options.saveConflict) return reply({ detail: 'A newer revision exists. Your draft is preserved.' }, 409);
        state.saved = body.content; state.revision++;
        return reply({ content: state.saved, revision: state.revision });
      }
      if (path.endsWith('/tests')) {
        state.runAttempts++;
        if (options.busy && state.runAttempts === 1) return reply({ detail: 'Execution busy' }, 429, { 'Retry-After': '0.1' });
        return reply({ ok: !options.failedRun, command: 'pytest -q', exit_code: options.failedRun ? 1 : 0, duration_ms: 25,
          stdout: options.failedRun ? '1 failed, 5 passed in 0.02s' : '6 passed in 0.02s', stderr: '',
          counts: { passed: options.failedRun ? 5 : 6, failed: options.failedRun ? 1 : 0, skipped: 0, total: 6 },
          advisory: true, authoritative: false, isolation: 'docker' });
      }
      if (path.endsWith('/level')) return reply(null);
      if (path.endsWith('/events')) return reply({});
      if (path === '/api/interview/sessions/' + sessionId) return reply(snapshot);
      state.unexpected.push(path);
      return reply({ detail: 'Unexpected fixture request: ' + path }, 500);
    });
  }
  await page.goto('/session/' + sessionId);
  await expect(page.locator('#pathLabel')).toHaveText('README.md');
  if (!options.leaseConflict && snapshot.status === 'active') await expect(page.locator('#testBtn')).toBeEnabled();
  return state;
}

async function edit(page, text) {
  await page.getByRole('button', { name: 'Code', exact: true }).click();
  await page.locator('#tree').getByRole('button', { name: 'answer.py', exact: true }).click();
  await expect(page.locator('#pathLabel')).toHaveText('src/answer.py');
  const input = page.locator('#monacoHost textarea.inputarea');
  await input.focus();
  await page.keyboard.press('Home');
  await page.keyboard.press('Shift+End');
  await page.keyboard.type(text);
  await expect(page.locator('#dirtyPill')).toBeVisible();
}

test('real editor saves the current revision before running advisory tests', async ({ page }) => {
  const state = await workspace(page);
  await edit(page, 'answer = 73');
  await page.getByRole('button', { name: 'Run tests', exact: true }).click();
  await expect(page.locator('#termMeta')).toContainText('ADVISORY PASS');
  expect(state.saved).toBe('answer = 73\n');
  const writes = state.requests.filter(r => r.method === 'PUT' || r.path.endsWith('/tests'));
  expect(writes.map(r => r.method)).toEqual(['PUT', 'POST']);
  expect(writes[0].body.base_revision).toBe(1);
  expect(writes[1].body).toEqual({ command_id: 'run_tests' });
  await expect(page.locator('.term-tab')).toHaveCSS('color', 'rgb(255, 255, 255)');
  expect(state.errors).toEqual([]);
  expect(state.unexpected).toEqual([]);
});

test('unsaved drafts survive a real reload without overwriting the saved file', async ({ page }) => {
  const state = await workspace(page, { liveFixture: true });
  await edit(page, 'answer = 91');
  page.once('dialog', dialog => dialog.accept());
  await page.reload();
  await expect(page.locator('#testBtn')).toBeEnabled();
  await expect.poll(() => page.evaluate(() => monaco.editor.getModels().find(m => m.uri.path.endsWith('/answer.py'))?.getValue())).toBe('answer = 91\n');
  expect(state.saved).toBe(original);
  expect(state.requests.filter(r => r.method === 'PUT')).toEqual([]);
  expect(state.errors).toEqual([]);
});

test('offline pauses editing; reconnect resumes the lease and preserves the draft', async ({ page, context }) => {
  const state = await workspace(page);
  await edit(page, 'answer = 17');
  await context.setOffline(true);
  await expect(page.locator('#testBtn')).toBeDisabled();
  await expect(page.locator('#submitBtn')).toBeDisabled();
  await context.setOffline(false);
  await expect(page.locator('#testBtn')).toBeEnabled();
  expect(await page.evaluate(() => monaco.editor.getModels().find(m => m.uri.path.endsWith('/answer.py')).getValue())).toBe('answer = 17\n');
  expect(state.saved).toBe(original);
  expect(state.errors).toEqual([]);
});

test('revision conflicts keep drafts and prevent execution of stale code', async ({ page }) => {
  const state = await workspace(page, { saveConflict: true });
  await edit(page, 'answer = 99');
  await page.getByRole('button', { name: 'Run tests', exact: true }).click();
  await expect(page.locator('#termLog')).toContainText('newer revision');
  expect(state.runAttempts).toBe(0);
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('pc_draft:qa-owner:11111111-1111-4111-8111-111111111111:src/answer.py')).value)).toBe('answer = 99\n');
  expect(state.errors).toEqual([]);
});

test('capacity retry runs once successfully and labels the result advisory', async ({ page }) => {
  const state = await workspace(page, { busy: true });
  await page.getByRole('button', { name: 'Run tests', exact: true }).click();
  await expect(page.locator('#termMeta')).toContainText('ADVISORY PASS');
  expect(state.runAttempts).toBe(2);
  expect(state.errors).toEqual([]);
});

test('a failed test run stays failed in the workspace status', async ({ page }) => {
  const state = await workspace(page, { failedRun: true });
  await page.getByRole('button', { name: 'Run tests', exact: true }).click();
  await expect(page.locator('#termMeta')).toContainText('ADVISORY FAIL');
  await expect(page.locator('#sessionStatus')).toHaveText('Tests failing');
  expect(state.errors).toEqual([]);
});

test('another editor lease cannot enable mutations in this tab', async ({ page }) => {
  const state = await workspace(page, { leaseConflict: true });
  await expect(page.locator('#testBtn')).toBeDisabled();
  await expect(page.locator('#submitBtn')).toBeDisabled();
  await expect(page.locator('#sessionStatus')).toHaveText('Paused');
  expect(state.requests.filter(r => r.method === 'PUT')).toEqual([]);
  expect(state.errors).toEqual([]);
});

test('submit dialog traps keyboard focus, closes with Escape, and has accessible controls', async ({ page }) => {
  const state = await workspace(page);
  await page.getByRole('button', { name: 'Submit', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Submit for advisory feedback' });
  await expect(dialog).toBeVisible();
  // Contrast must be measured after the translucent entrance animation finishes.
  await expect(dialog.locator('.modal-card')).toHaveCSS('opacity', '1');
  await page.keyboard.press('Tab');
  expect(await dialog.evaluate(el => el.contains(document.activeElement))).toBe(true);
  const audit = await new AxeBuilder({ page }).include('#submitModal').withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
  expect(audit.violations).toEqual([]);
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(page.locator('#submitBtn')).toBeFocused();
  expect(state.errors).toEqual([]);
});

test('completed attempts remain read only', async ({ page }) => {
  const state = await workspace(page, { status: 'submitted' });
  await expect(page.locator('#testBtn')).toBeDisabled();
  await expect(page.locator('#submitBtn')).toBeDisabled();
  expect(state.requests.filter(r => r.path.endsWith('/timer'))).toEqual([]);
  expect(state.errors).toEqual([]);
});
