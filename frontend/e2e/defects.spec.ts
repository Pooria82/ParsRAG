import { expect, test, type Page } from '@playwright/test';

type StoredSession = { id: string; title: string; documents?: { name: string; status: string; enabled: boolean }[]; messages?: unknown[] };

/** Open the workspace in English with the given conversations and a ready service. */
async function open(page: Page, sessions: StoredSession[] = []) {
  await page.addInitScript(stored => {
    localStorage.setItem('parsrag_settings_v1', JSON.stringify({ language: 'en', theme: 'light' }));
    localStorage.setItem('parsrag_tour_v1', 'done');
    if (stored.length && !localStorage.getItem('parsrag_seeded')) {
      localStorage.setItem('parsrag_seeded', '1');
      localStorage.setItem('parsrag_sessions_v1', JSON.stringify(stored.map(session => ({
        createdAt: 1, updatedAt: 1, ragMode: 'hybrid', draft: '', documents: [], messages: [], ...session,
      }))));
      localStorage.setItem('parsrag_active_session_id_v1', stored[0].id);
    }
  }, sessions);
  await page.route('**/capabilities', route => route.fulfill({ json: { ingestion: {
    max_files_per_session: 10, max_file_size_bytes: 104857600,
    max_batch_size_bytes: 524288000, supported_extensions: ['.pdf', '.txt'], ocr_enabled: true,
  } } }));
  await page.route('**/models/configuration', route => route.fulfill({ json: {
    provider: 'ollama', model_name: 'gemma3:4b', base_url: 'http://127.0.0.1:11434',
    api_key_configured: false, disclosure_acknowledged: false,
  } }));
  await page.route('**/sessions/*/suggestions', route => route.fulfill({ json: { questions: [] } }));
}

test('server setting edits survive other changes, and an emptied number is not "Automatic"', async ({ page }) => {
  await open(page);
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/settings/runtime', route => route.fulfill({ json: { upload_ceiling_bytes: 524288000, settings: [
    { key: 'STRICT_RAG_TOP_K', group: 'retrieval', kind: 'int', value: '12', env_value: '', overridden: true, minimum: 1, maximum: 50, automatic: true, automatic_value: '8-30' },
  ] } }));
  await page.goto('/');
  await page.getByRole('button', { name: 'Settings' }).click();
  await page.getByRole('tab', { name: 'Answers' }).click();
  const depth = page.locator('#runtime-STRICT_RAG_TOP_K');
  await depth.fill('20');
  // A browser preference re-renders the whole app; the unsaved edit stays.
  await page.getByRole('switch', { name: /Automatic retrieval depth/ }).click();
  await expect(depth).toHaveValue('20');

  await depth.fill('');
  await expect(depth).toBeEnabled();
  await expect(depth).toHaveValue('');
  await expect(page.locator('.server-setting', { has: depth }).getByRole('checkbox', { name: 'Automatic' })).not.toBeChecked();
  await expect(page.getByRole('button', { name: 'Save', exact: true })).toBeDisabled();
});

test('the rename field takes focus, and dragging out of a dialog keeps it open', async ({ page }) => {
  await open(page, [{ id: 'talk', title: 'Budget review', messages: [{ id: 'u', role: 'user', content: 'Hi', timestamp: 1 }] }]);
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/sessions/*/files', route => route.fulfill({ json: [] }));
  await page.goto('/');
  await page.getByLabel('Conversation options: Budget review').click();
  await page.getByRole('button', { name: 'Rename' }).click();
  const title = page.getByRole('textbox', { name: 'Conversation name' });
  await expect(title).toBeFocused();

  const box = (await title.boundingBox())!;
  await page.mouse.move(box.x + 10, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(5, 5);
  await page.mouse.up();
  await expect(page.getByRole('dialog', { name: 'Rename' })).toBeVisible();
});

test('a dropped connection keeps the text that already arrived', async ({ page }) => {
  await open(page);
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/conversations/title', route => route.fulfill({ json: { title: 'Plan' } }));
  await page.route('**/query/stream', route => route.fulfill({ contentType: 'text/event-stream',
    body: 'event: stage\ndata: {"stage":"generating"}\n\nevent: token\ndata: {"text":"The first half of the answer"}\n\n' }));
  await page.goto('/');
  const composer = page.getByRole('textbox', { name: 'Your message' });
  await composer.fill('Explain the plan');
  await composer.press('Enter');
  await expect(page.locator('.message-assistant')).toContainText('The first half of the answer');
  await expect(page.locator('.system-message')).toContainText('The connection dropped');
});

test('a conversation deleted while the service is offline is deleted there once it is back', async ({ page }) => {
  await open(page, [
    { id: 'keep', title: 'Keep me', messages: [{ id: 'k', role: 'user', content: 'Hi', timestamp: 1 }] },
    { id: 'old', title: 'Old report', documents: [{ name: 'report.pdf', status: 'indexed', enabled: true }] },
  ]);
  let online = false;
  const deleted: string[] = [];
  await page.route('**/health/ready', route => online ? route.fulfill({ json: { status: 'ready' } }) : route.abort());
  await page.route('**/sessions/*/files', route => route.fulfill({ json: [] }));
  await page.route('**/sessions/old', route => {
    if (!online) return route.abort();
    deleted.push(route.request().method());
    return route.fulfill({ status: 204 });
  });
  await page.goto('/');
  await page.getByLabel('Conversation options: Old report').click();
  await page.locator('.history-menu-popover').getByRole('button', { name: 'Delete conversation' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Delete conversation' }).click();
  await expect(page.getByLabel('Conversation options: Old report')).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem('parsrag_pending_deletions_v1'))).toBe('["old"]');

  online = true;
  await page.getByRole('button', { name: 'Check again' }).click();
  await expect.poll(() => deleted).toEqual(['DELETE']);
  await expect.poll(() => page.evaluate(() => localStorage.getItem('parsrag_pending_deletions_v1'))).toBeNull();
});

test('shortcuts work with the Persian keyboard layout', async ({ page }) => {
  await open(page);
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.goto('/');
  await expect(page.getByRole('textbox', { name: 'Your message' })).toBeVisible();
  // Ctrl+Shift+D on a Persian layout types "ی" on the D key.
  await page.evaluate(() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ی', code: 'KeyD', ctrlKey: true, shiftKey: true, bubbles: true })));
  await expect(page.getByRole('dialog', { name: /Conversation documents/ })).toBeVisible();
});

test('two open tabs share changes instead of overwriting each other', async ({ page, context }) => {
  await open(page, [{ id: 'talk', title: 'Budget review', messages: [{ id: 'u', role: 'user', content: 'Hi', timestamp: 1 }] }]);
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/sessions/*/files', route => route.fulfill({ json: [] }));
  await page.goto('/');
  await expect(page.getByLabel('Conversation options: Budget review')).toBeVisible();
  const other = await context.newPage();
  await other.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await other.route('**/sessions/*/files', route => route.fulfill({ json: [] }));
  await other.goto('/');
  await expect(other.getByLabel('Conversation options: Budget review')).toBeVisible();

  await page.getByLabel('Conversation options: Budget review').click();
  await page.getByRole('button', { name: 'Rename' }).click();
  await page.getByRole('textbox', { name: 'Conversation name' }).fill('Budget 2026');
  await page.getByRole('button', { name: 'Save' }).click();

  await expect(other.getByLabel('Conversation options: Budget 2026')).toBeVisible();
  await other.reload();
  await expect(other.getByLabel('Conversation options: Budget 2026')).toBeVisible();
});

for (const [language, prompt, side] of [
  ['fa', 'این گزارش دربارهٔ چیست؟', 'right'],
  ['en', 'What is this report about?', 'left'],
  ['fa', 'What is this report about?', 'left'],
  ['en', 'این گزارش دربارهٔ چیست؟', 'right'],
] as const) {
  test(`a ${language} interface puts "${prompt}" on the ${side}`, async ({ page }) => {
    await open(page, [{ id: 'talk', title: 'Report', messages: [{ id: 'u', role: 'user', content: prompt, timestamp: 1 },
      { id: 'a', role: 'assistant', parentUserId: 'u', content: language === 'fa' ? 'این گزارش دربارهٔ امنیت توکن‌هاست.' : 'The report is about token security.', timestamp: 2 }] }]);
    await page.addInitScript(lang => localStorage.setItem('parsrag_settings_v1', JSON.stringify({ language: lang, theme: 'light' })), language);
    await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
    await page.route('**/sessions/*/files', route => route.fulfill({ json: [] }));
    await page.goto('/');
    const bubble = (await page.locator('.user-bubble').boundingBox())!;
    const list = (await page.locator('.message-list').boundingBox())!;
    const gap = side === 'right' ? list.x + list.width - (bubble.x + bubble.width) : bubble.x - list.x;
    expect(gap).toBeLessThan(4);
    await expect(page.locator('.boot-sequence')).toHaveCount(0, { timeout: 10000 });
    await page.screenshot({ path: `test-results/bubble-${language}-${side}.png` });
  });
}

test('"Service ready" needs the model service too', async ({ page }) => {
  await open(page);
  let model = 'unreachable';
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/models/status', route => route.fulfill({ json: { provider: 'ollama', model_name: 'gemma3:4b', status: model } }));
  await page.goto('/');
  const status = page.locator('.connection-status');
  await expect(status).toContainText('Ollama is not reachable; start it');
  await expect(status).toHaveAttribute('data-status', 'degraded');

  model = 'ready';
  const retry = status.getByRole('button', { name: 'Check again' });
  await retry.click();
  // The icon spins while the check runs, so the click visibly does something.
  await expect(retry.locator('svg')).toHaveClass(/spin/);
  await expect(retry).toBeDisabled();
  await expect(status).toContainText('Service ready');
  await expect(status).toHaveAttribute('data-status', 'online');
});

test('an API address without a key cannot be connected, and the sidebar says why', async ({ page }) => {
  await open(page);
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/models/status', route => route.fulfill({ json: { provider: 'api', model_name: 'google/gemma-4-26b-a4b-it', status: 'key_missing' } }));
  await page.route('**/models/configuration', route => route.request().method() === 'PUT'
    ? route.fulfill({ status: 400, json: { detail: 'No API key for openrouter.ai; enter one.', code: 'api_key_missing' } })
    : route.fulfill({ json: { provider: 'api', model_name: 'google/gemma-4-26b-a4b-it', base_url: 'https://openrouter.ai/api/v1',
      api_key_configured: true, disclosure_acknowledged: true, api_key_hosts: ['generativelanguage.googleapis.com'] } }));
  await page.goto('/');
  await expect(page.locator('.connection-status')).toContainText('No API key is set; enter one in Settings');

  await page.getByRole('button', { name: 'Settings' }).click();
  await page.getByRole('tab', { name: 'Model & connection' }).click();
  // The service has a key, but for another host: this address has none.
  const keyState = page.locator('.credential-state');
  await expect(keyState).toHaveAttribute('data-state', 'missing');
  await expect(keyState).toContainText('The service holds a key for generativelanguage.googleapis.com');
  await page.getByRole('button', { name: 'Verify connection and apply' }).click();
  await expect(page.getByText('There is no API key for this address, and it cannot be used without one.')).toBeVisible();
});

test('closing Settings with the mouse leaves no focus ring on the Settings button', async ({ page }) => {
  await open(page);
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.goto('/');
  const settings = page.getByRole('button', { name: 'Settings' });
  await settings.click();
  await page.getByRole('dialog', { name: /Settings/ }).getByRole('button', { name: 'Close' }).click();
  await expect(page.getByRole('dialog', { name: /Settings/ })).toBeHidden();
  await expect(settings).toBeFocused();
  expect(await settings.evaluate(element => element.matches(':focus-visible'))).toBe(false);
});
