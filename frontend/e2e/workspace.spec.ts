import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.route('**/capabilities', route => route.fulfill({ json: { ingestion: {
    max_files_per_session: 10, max_file_size_bytes: 104857600,
    max_batch_size_bytes: 524288000, supported_extensions: ['.pdf', '.docx', '.txt'], ocr_enabled: true,
  } } }));
  await page.route('**/models/configuration', route => route.fulfill({ json: {
    provider: 'ollama', model_name: 'gemma3:12b', base_url: 'http://127.0.0.1:11434',
    api_key_configured: false, disclosure_acknowledged: false,
  } }));
});

test('opens the workspace and model settings against local API fixtures', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('parsrag_settings_v1', JSON.stringify({ language: 'en', theme: 'light' }));
    localStorage.setItem('parsrag_tour_v1', 'done');
  });
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/sessions/*/files', route => route.fulfill({ json: [] }));
  await page.route('**/models/configuration', route => route.fulfill({
    json: {
      provider: 'ollama', model_name: 'gemma3:12b',
      base_url: 'http://localhost:11434', api_key_configured: false,
    },
  }));

  await page.goto('/');

  await expect(page).toHaveTitle(/ParsRAG/);
  await expect(page.getByRole('textbox', { name: 'Your message' })).toBeVisible();
  await page.getByRole('button', { name: 'Settings' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('tab', { name: 'Model & connection' }).click();
  await expect(page.getByText('OpenAI-compatible API')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Verify connection and apply' })).toBeVisible();
});

test('first visit guide can be skipped and replayed from settings', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('parsrag_settings_v1', JSON.stringify({ language: 'en', theme: 'light' }));
    localStorage.removeItem('parsrag_tour_v1');
  });
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/sessions/*/files', route => route.fulfill({ json: [] }));
  await page.goto('/');
  const tour = page.getByRole('dialog', { name: 'ParsRAG tour' });
  await expect(tour).toBeVisible();
  await expect(tour.getByText('A fresh conversation')).toBeVisible();
  await tour.getByRole('button', { name: 'Next' }).click();
  await expect(tour.getByText('Your documents')).toBeVisible();
  await tour.getByRole('button', { name: 'Skip' }).click();
  await expect(tour).toBeHidden();
  await page.getByRole('button', { name: 'Settings' }).click();
  await page.getByRole('button', { name: 'Show tour' }).click();
  await expect(tour).toBeVisible();
});

test('reuses a previous document and offers document and command suggestions', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('parsrag_tour_v1', 'done');
    localStorage.setItem('parsrag_settings_v1', JSON.stringify({ language: 'en', theme: 'light' }));
    localStorage.setItem('parsrag_sessions_v1', JSON.stringify([
      { id: 'current', title: 'New conversation', createdAt: 2, updatedAt: 2, ragMode: 'hybrid', messages: [], documents: [], draft: '' },
      { id: 'previous', title: 'Research notes', createdAt: 1, updatedAt: 1, ragMode: 'strict', messages: [], documents: [{ name: 'guide.pdf', status: 'indexed' }], draft: '' },
    ]));
    localStorage.setItem('parsrag_active_session_id_v1', 'current');
  });
  let reused = false;
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/sessions/current/files', route => route.fulfill({ json: reused ? ['guide.pdf'] : [] }));
  await page.route('**/sessions/current/files/reuse', route => {
    reused = true;
    return route.fulfill({ json: { filename: 'guide.pdf', chunks: 2 } });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Documents' }).first().click();
  const docs = page.getByRole('dialog', { name: /Conversation documents/ });
  await expect(docs.getByText('guide.pdf')).toBeVisible();
  await docs.getByRole('button', { name: 'Add', exact: true }).click();
  await expect(docs.getByRole('checkbox', { name: /guide.pdf/ })).toBeVisible();
  await docs.getByRole('button', { name: 'Close' }).click();
  const composer = page.getByRole('textbox', { name: 'Your message' });
  await composer.fill('@gui');
  await expect(page.getByRole('listbox', { name: 'Mention a document' })).toBeVisible();
  await composer.press('Enter');
  await expect(composer).toHaveValue(/@\{guide\.pdf\}/);
  await composer.fill('/sum');
  await expect(page.getByRole('listbox', { name: 'Quick commands' })).toBeVisible();
  await composer.press('Enter');
  await expect(composer).toHaveValue(/Summarize the selected documents/);
});

test('selected color palette survives a reload in light and dark mode', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('parsrag_tour_v1', 'done');
    if (!localStorage.getItem('parsrag_settings_v1')) {
      localStorage.setItem('parsrag_settings_v1', JSON.stringify({ language: 'en', theme: 'light' }));
    }
  });
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/sessions/*/files', route => route.fulfill({ json: [] }));
  await page.goto('/');
  await page.getByRole('button', { name: 'Settings' }).click();
  const settings = page.getByRole('dialog', { name: /Settings/ });
  await settings.getByRole('radio', { name: 'Ocean blue' }).check();
  await expect(page.locator('html')).toHaveAttribute('data-palette', 'ocean');
  await settings.getByRole('radio', { name: /Dark/ }).check();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-palette', 'ocean');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
});
