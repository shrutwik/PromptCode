import { test, expect } from '@playwright/test';

for (const variant of ['starter', 'reference']) {
  test(`feed ${variant}: browser badge reveals or resolves concurrent updates`, async ({ page }) => {
    await page.goto('/_questions/feed?variant=' + variant);
    await expect(page.getByTestId('unread-count')).toHaveText('2');
    await page.locator('button').evaluateAll(buttons => buttons.forEach(button => button.click()));
    await expect(page.getByTestId('unread-count')).toHaveText(variant === 'reference' ? '0' : '1');
    if (variant === 'reference') {
      await expect(page.getByTestId('read-a')).toHaveText('read');
      await expect(page.getByTestId('read-b')).toHaveText('read');
    }
  });

  test(`labels ${variant}: selected values match saved API state across reload`, async ({ page }) => {
    let saved = ['a'];
    await page.route('**/tickets/ticket**', async route => {
      if (route.request().method() === 'PUT') saved = route.request().postDataJSON().labelIds;
      await route.fulfill({ json: { id: 'ticket', workspaceId: 'ours', title: 'Saved labels', labelIds: saved } });
    });
    await page.route('**/workspaces/ours/labels', route => route.fulfill({ json: [{ id: 'a', name: 'Urgent' }, { id: 'b', name: 'Review' }] }));
    await page.goto('/_questions/labels?variant=' + variant);
    await expect(page.getByTestId('title')).toHaveText('Saved labels');
    await expect(page.getByTestId('label-a')).toBeVisible();
    if (variant === 'starter') {
      await expect(page.getByTestId('selected')).toBeEmpty();
      await expect(page.getByTestId('label-a')).not.toBeChecked();
    } else {
      await expect(page.getByTestId('selected')).toHaveText('a');
      await expect(page.getByTestId('label-a')).toBeChecked();
      await page.getByTestId('label-a').uncheck();
      await expect.poll(() => saved).toEqual([]);
      await page.reload();
      await expect(page.getByTestId('label-a')).not.toBeChecked();
      await expect(page.getByTestId('selected')).toBeEmpty();
    }
  });
}

for (const variant of ['starter', 'reference']) {
  test(`canvas ${variant}: zoomed drag and document loading obey the contract`, async ({ page }) => {
    await page.goto('/_questions/canvas?variant=' + variant);
    await page.getByRole('button', { name: 'Add rectangle', exact: true }).click();
    await page.getByLabel('Zoom', { exact: true }).selectOption('2');
    const shape = page.getByTestId('shape-s1');
    const box = await shape.boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2 + 20, box.y + box.height / 2 + 10);
    await page.mouse.up();
    await expect(shape).toHaveAttribute('x', variant === 'reference' ? '20' : '30');
    await expect(shape).toHaveAttribute('y', variant === 'reference' ? '25' : '30');
    await page.getByRole('button', { name: 'Undo', exact: true }).click();
    await expect(shape).toHaveAttribute('x', '10');
    await page.getByRole('button', { name: 'Save document', exact: true }).click();
    const saved = await page.getByLabel('Document JSON', { exact: true }).inputValue();
    await page.getByRole('button', { name: 'Delete selected', exact: true }).click();
    await expect(shape).toHaveCount(0);
    await page.getByRole('button', { name: 'Load document', exact: true }).click();
    if (variant === 'reference') {
      await expect(shape).toHaveCount(1);
      await page.getByLabel('Document JSON', { exact: true }).fill('{bad json');
      await page.getByRole('button', { name: 'Load document', exact: true }).click();
      await expect(page.getByRole('alert')).toHaveText('Invalid document');
      await expect(shape).toHaveAttribute('x', '10');
      await page.getByRole('button', { name: 'Save document', exact: true }).click();
      expect(await page.getByLabel('Document JSON', { exact: true }).inputValue()).toBe(saved);
    } else {
      await expect(page.getByRole('alert')).toHaveText('Invalid document');
      await expect(shape).toHaveCount(0);
    }
  });

  test(`search ${variant}: an old successful response cannot replace newer results`, async ({ page }) => {
    let firstRoute;
    const first = new Promise(resolve => { firstRoute = resolve; });
    await page.route('**/api/movies?**', async route => {
      if (!new URL(route.request().url()).searchParams.get('q')) {
        firstRoute(route);
        return;
      }
      await route.fulfill({ json: { rows: [{ id: 'new', title: 'New result', genre: 'drama', year: 2024 }], total: 1 } });
    });
    await page.goto('/_questions/search?variant=' + variant);
    const held = await first;
    await page.getByLabel('Search', { exact: true }).fill('new');
    await expect(page.getByRole('link', { name: 'New result (new)', exact: true })).toBeVisible();
    const obsolete = page.waitForResponse(response => response.url() === held.request().url());
    await held.fulfill({ json: { rows: [{ id: 'old', title: 'Old result', genre: 'comedy', year: 2019 }], total: 1 } });
    await (await obsolete).finished();
    if (variant === 'starter') {
      await expect(page.getByRole('link', { name: 'Old result (old)', exact: true })).toBeVisible();
    } else {
      // Wait for the obsolete response's body processing, then verify visible state.
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      await expect(page.getByRole('link', { name: 'New result (new)', exact: true })).toBeVisible();
      await expect(page.getByRole('link', { name: 'Old result (old)', exact: true })).toHaveCount(0);
    }
  });
}
