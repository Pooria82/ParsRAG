import { readFileSync } from 'node:fs';
import { expect, test, type Page } from '@playwright/test';

const VERSION = readFileSync(new URL('../../VERSION', import.meta.url), 'utf8').trim();
const [major, minor] = VERSION.split('.').map(Number);
const NEXT = `${major}.${minor + 1}.0`;
const LATER = `${major}.${minor + 2}.0`;

async function open(page: Page, options: { seen?: string; history?: boolean; updates: unknown; notes?: unknown }) {
  await page.addInitScript(({ seen, history }) => {
    localStorage.setItem('parsrag_settings_v1', JSON.stringify({ language: 'en', theme: 'light' }));
    localStorage.setItem('parsrag_tour_v1', 'done');
    if (seen) localStorage.setItem('parsrag_seen_version_v1', seen);
    if (history && !localStorage.getItem('parsrag_sessions_v1')) {
      localStorage.setItem('parsrag_sessions_v1', JSON.stringify([{ id: 'talk', title: 'Old talk', createdAt: 1, updatedAt: 1,
        ragMode: 'hybrid', draft: '', documents: [], messages: [{ id: 'u', role: 'user', content: 'Hi', timestamp: 1 }] }]));
    }
  }, { seen: options.seen, history: options.history });
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/capabilities', route => route.fulfill({ json: { ingestion: {
    max_files_per_session: 10, max_file_size_bytes: 104857600, max_batch_size_bytes: 524288000, supported_extensions: ['.pdf'], ocr_enabled: true,
  } } }));
  await page.route('**/models/configuration', route => route.fulfill({ json: { provider: 'ollama', model_name: 'gemma3:4b', base_url: 'http://localhost:11434', api_key_configured: false, disclosure_acknowledged: false } }));
  await page.route('**/models/status', route => route.fulfill({ json: { provider: 'ollama', model_name: 'gemma3:4b', status: 'ready' } }));
  await page.route('**/sessions/*/files', route => route.fulfill({ json: [] }));
  await page.route(/\/updates(\?.*)?$/, route => route.fulfill({ json: options.updates }));
  await page.route(/\/release-notes(\?.*)?$/, route => route.fulfill({ json: options.notes ?? { current_version: VERSION, notes: [] } }));
}

const available = {
  enabled: true, current_version: VERSION, latest_version: LATER, update_available: true, checked_at: null,
  releases: [
    { version: LATER, url: 'https://github.com/Pooria82/ParsRAG/releases/tag/v' + LATER, notes_fa: '- پاسخ سریع‌تر', notes_en: '- Faster answers' },
    { version: NEXT, url: '', notes_fa: '', notes_en: '- Better OCR' },
  ],
};

test('a newer release offers its notes, a backup first, then the one update command', async ({ page }) => {
  await open(page, { seen: VERSION, updates: available });
  await page.goto('/');
  const badge = page.getByRole('button', { name: `Version ${LATER} is available` });
  await badge.click();
  const dialog = page.getByRole('dialog', { name: `Version ${LATER} is available` });
  await expect(dialog).toContainText(`You have ${VERSION}. The update goes straight to ${LATER}.`);
  // Every release in between is listed; the update installs only the latest.
  await expect(dialog).toContainText('Faster answers');
  await expect(dialog).toContainText('Better OCR');
  await expect(dialog.locator('.update-command code')).toHaveText(/scripts\/update\.(ps1|sh)/);
  const copy = dialog.locator('.update-command button');
  await expect(copy).toBeDisabled();

  const download = page.waitForEvent('download');
  await dialog.getByRole('button', { name: 'Download backup' }).click();
  expect((await download).suggestedFilename()).toMatch(/^parsrag-backup-.*\.json$/);
  await expect(copy).toBeEnabled();

  await dialog.getByRole('button', { name: 'Skip this version' }).click();
  await expect(badge).toHaveCount(0);
});

test('after an update the changes of every skipped version are shown once', async ({ page }) => {
  let since: string | null = null;
  await open(page, { seen: '0.9.0', updates: { ...available, update_available: false, latest_version: VERSION, releases: [] } });
  await page.route(/\/release-notes(\?.*)?$/, route => {
    since = new URL(route.request().url()).searchParams.get('since');
    return route.fulfill({ json: { current_version: VERSION, notes: [
      { version: VERSION, notes: '- Answers follow your language' }, { version: '0.9.5', notes: '- Older fix' },
    ] } });
  });
  await page.goto('/');
  const dialog = page.getByRole('dialog', { name: `What’s new in ${VERSION}` });
  await expect(dialog).toContainText('Answers follow your language');
  await expect(dialog).toContainText('Older fix');
  expect(since).toBe('0.9.0');
  await dialog.getByRole('button', { name: 'Got it' }).click();
  await expect(dialog).toBeHidden();
  expect(await page.evaluate(() => localStorage.getItem('parsrag_seen_version_v1'))).toBe(VERSION);

  await page.reload();
  await expect(page.getByRole('textbox', { name: 'Your message' })).toBeVisible();
  await expect(page.getByRole('dialog', { name: /What’s new/ })).toHaveCount(0);
});

test('a page left open during an update loads the new interface once', async ({ page }) => {
  await open(page, { seen: VERSION, updates: { ...available, current_version: NEXT, update_available: false, releases: [] } });
  let loads = 0;
  page.on('load', () => { loads += 1; });
  await page.goto('/');
  await expect.poll(() => loads, { timeout: 10000 }).toBe(2);
  expect(await page.evaluate(() => sessionStorage.getItem('parsrag_reloaded_for_v1'))).toBe(NEXT);
  // It does not reload again although the versions still differ.
  await page.waitForTimeout(2000);
  expect(loads).toBe(2);
});

test('Settings shows the version and turns the check off', async ({ page }) => {
  await open(page, { seen: VERSION, updates: { ...available, update_available: false, latest_version: VERSION, releases: [] } });
  await page.route('**/settings/runtime', route => route.fulfill({ json: { upload_ceiling_bytes: 524288000, settings: [
    { key: 'UPDATE_CHECK_ENABLED', group: 'updates', kind: 'bool', value: '1', env_value: '1', overridden: false, minimum: null, maximum: null, automatic: false, automatic_value: null },
  ] } }));
  await page.goto('/');
  await page.getByRole('button', { name: 'Settings' }).click();
  const section = page.getByRole('region', { name: 'Version and updates' });
  await expect(section).toContainText(`Installed version: ${VERSION}`);
  await expect(section.getByRole('switch', { name: /Check for new versions/ })).toBeChecked();
  await section.getByRole('button', { name: 'Check for updates' }).click();
  await expect(section).toContainText('You have the latest version.');
});
