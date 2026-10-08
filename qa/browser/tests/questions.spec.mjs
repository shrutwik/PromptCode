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
