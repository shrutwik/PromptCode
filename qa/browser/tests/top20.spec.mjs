import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const registry = JSON.parse(readFileSync(new URL('../../../challenges/interview-registry.json', import.meta.url)));
const quality = JSON.parse(readFileSync(new URL('../../../backend/benchmarks/interview_quality_contract.json', import.meta.url)));

async function signedIn(page) {
  await page.addInitScript(() => {
    sessionStorage.setItem('access_token', 'qa-disposable-token');
    sessionStorage.setItem('pc_user', JSON.stringify({ id: 'qa-owner', email: 'qa@example.test' }));
  });
  await page.context().route('https://**', route => route.abort());
}

test('catalogue shows exactly twenty ordered core questions and retains additional practice', async ({ page }) => {
  await signedIn(page);
  await page.route('**/api/interview/challenges**', route => {
    const path = new URL(route.request().url()).pathname;
    const detail = registry.challenges.find(item => path.endsWith('/' + item.slug));
    return route.fulfill({ json: detail ? { ...detail, readme: 'Review this repository task.' } : registry.challenges });
  });
  await page.goto('/challenges');
  const rows = page.locator('#tableWrap tbody tr');
  await expect(rows).toHaveCount(25);
  for (let i = 0; i < 20; i++) {
    await expect(rows.nth(i)).toContainText(`Core #${i + 1}`);
    await expect(rows.nth(i).locator('.title-cell a')).toHaveAttribute('href', '/challenges/' + registry.challenges[i].slug);
  }
  for (let i = 20; i < 25; i++) await expect(rows.nth(i)).toContainText('More practice');
  await page.locator('#searchFilter').fill(registry.challenges[0].title);
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText('Core #1');
  await rows.first().locator('.title-cell a').click();
  await expect(page).toHaveURL(new RegExp('/challenges/' + registry.challenges[0].slug + '$'));
});

test('workspace shows four distinct parts and explicitly marks the ungraded discussion', async ({ page }) => {
  await signedIn(page);
  const id = '22222222-2222-4222-8222-222222222222';
  const challenge = registry.challenges[0];
  const parts = quality.questions[challenge.slug].parts.map(({ number, title, task, acceptance, mode }) => ({ number, title, task, acceptance, mode }));
  const session = { id, challenge_slug: challenge.slug, status: 'completed', elapsed_ms: 0, timer_running: false, timer_lease_ms: 0 };
  const level = { index: 0, total: 1, kind: challenge.type, title: challenge.title,
    problem: challenge.summary, body: 'Complete the repository task.', guide: [], parts,
    can_advance: false, is_last: true, earlier: [] };
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/bootstrap')) return route.fulfill({ json: { session, files: [], level, readme: null } });
    if (path.endsWith('/level')) return route.fulfill({ json: level });
    if (path === '/api/interview/sessions/' + id) return route.fulfill({ json: session });
    return route.fulfill({ json: {} });
  });
  await page.goto('/session/' + id);
  const rendered = page.locator('#questionBody .brief-part');
  await expect(rendered).toHaveCount(4);
  for (let i = 0; i < 4; i++) {
    await expect(rendered.nth(i).locator('h4')).toHaveText(`Part ${i + 1} — ${parts[i].title}`);
    await expect(rendered.nth(i)).toContainText(parts[i].task);
    for (const item of parts[i].acceptance) await expect(rendered.nth(i)).toContainText(item);
  }
  await expect(rendered.nth(3)).toContainText('Optional discussion. No extra coding requirement or automated score.');
  await expect(page.locator('#testBtn')).toBeDisabled();
});
