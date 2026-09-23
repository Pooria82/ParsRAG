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

test('Persian first-run guide stays usable on a narrow screen', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 667 });
  await page.addInitScript(() => {
    localStorage.setItem('parsrag_settings_v1', JSON.stringify({ language: 'fa', theme: 'light' }));
    localStorage.removeItem('parsrag_tour_v1');
  });
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/sessions/*/files', route => route.fulfill({ json: [] }));
  await page.goto('/');
  const tour = page.getByRole('dialog', { name: 'راهنمای پارس‌رگ' });
  await expect.poll(() => page.locator('main').evaluate(element => element.inert)).toBe(true);
  for (let step = 0; step < 4; step += 1) {
    await expect(tour).toBeVisible();
    const bounds = await tour.locator('.tour-card').boundingBox();
    expect(bounds).not.toBeNull();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.y).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(375);
    expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(667);
    await tour.getByRole('button', { name: step === 3 ? 'شروع کنیم' : 'بعدی' }).click();
  }
  await expect(tour).toBeHidden();
  await expect.poll(() => page.locator('main').evaluate(element => element.inert)).toBe(false);
  await page.reload();
  await expect(tour).toBeHidden();
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

test('two document mentions survive submission with a scoped file filter', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('parsrag_tour_v1', 'done');
    localStorage.setItem('parsrag_settings_v1', JSON.stringify({ language: 'en', theme: 'light' }));
    localStorage.setItem('parsrag_sessions_v1', JSON.stringify([{
      id: 'current', title: 'New conversation', createdAt: 1, updatedAt: 1,
      ragMode: 'strict', messages: [], draft: '', documents: [
        { name: 'costs.pdf', status: 'indexed', enabled: true },
        { name: 'schedule.pdf', status: 'indexed', enabled: true },
      ],
    }]));
    localStorage.setItem('parsrag_active_session_id_v1', 'current');
  });
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/sessions/current/files', route => route.fulfill({ json: ['costs.pdf', 'schedule.pdf'] }));
  await page.route('**/queries/*/progress', route => route.fulfill({ status: 404 }));
  await page.route('**/conversations/title', route => route.fulfill({ json: { title: 'Cost and schedule' } }));
  let submitted: { prompt: string; file_filter: string[] } | undefined;
  await page.route('**/query', async route => {
    submitted = route.request().postDataJSON();
    await route.fulfill({ json: { answer: 'The costs and schedule are documented.', source_nodes: [
      { text: 'cost', score: 0.9, metadata: { filename: 'costs.pdf', page: 2 } },
      { text: 'date', score: 0.9, metadata: { filename: 'schedule.pdf', page: 4 } },
    ] } });
  });
  await page.goto('/');
  const composer = page.getByRole('textbox', { name: 'Your message' });
  await composer.fill('Compare @cost');
  await composer.press('Enter');
  await expect(composer).toHaveValue(/@\{costs\.pdf\}/);
  await composer.pressSequentially(' costs and @sche');
  await composer.press('Enter');
  await expect(composer).toHaveValue(/@\{schedule\.pdf\}/);
  await composer.pressSequentially(' schedule');
  await page.getByRole('button', { name: 'Send message' }).click();
  await expect.poll(() => submitted).toBeDefined();
  expect(submitted!.prompt).toContain('@{costs.pdf}');
  expect(submitted!.prompt).toContain('@{schedule.pdf}');
  expect(submitted!.file_filter).toEqual(['costs.pdf', 'schedule.pdf']);
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

test('all workspace palettes keep readable body and primary-button contrast', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('parsrag_tour_v1', 'done'));
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/sessions/*/files', route => route.fulfill({ json: [] }));
  await page.goto('/');
  const contrast = await page.evaluate(() => {
    const luminance = (raw: string) => {
      const hex = raw.length === 4 ? '#' + [...raw.slice(1)].map(digit => digit + digit).join('') : raw;
      const values = [1, 3, 5].map(offset => Number.parseInt(hex.slice(offset, offset + 2), 16) / 255)
        .map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
      return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722;
    };
    const ratio = (first: string, second: string) => {
      const high = Math.max(luminance(first), luminance(second));
      const low = Math.min(luminance(first), luminance(second));
      return (high + 0.05) / (low + 0.05);
    };
    const output: Array<{ palette: string; theme: string; text: number; button: number }> = [];
    for (const theme of ['light', 'dark']) for (const palette of ['evergreen', 'ocean', 'indigo', 'sienna']) {
      document.documentElement.dataset.theme = theme;
      document.documentElement.dataset.palette = palette;
      const style = getComputedStyle(document.documentElement);
      const color = (name: string) => style.getPropertyValue(name).trim();
      output.push({ palette, theme, text: ratio(color('--ink'), color('--surface')),
        button: ratio(color('--on-accent'), color('--accent')) });
    }
    return output;
  });
  for (const sample of contrast) {
    expect(sample.text, `${sample.theme}/${sample.palette} body text`).toBeGreaterThanOrEqual(4.5);
    expect(sample.button, `${sample.theme}/${sample.palette} primary button`).toBeGreaterThanOrEqual(4.5);
  }
});
