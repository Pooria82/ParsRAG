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

test('document drawer animates both opening and closing without losing modal focus', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('parsrag_settings_v1', JSON.stringify({ language: 'fa', theme: 'light' }));
    localStorage.setItem('parsrag_tour_v1', 'done');
  });
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.goto('/');
  await page.getByRole('button', { name: 'اسناد' }).first().click();
  const drawer = page.locator('dialog.documents-dialog');
  await expect(drawer).toBeVisible();
  await expect.poll(() => drawer.evaluate(element => getComputedStyle(element).getPropertyValue('--drawer-offset').trim())).toBe('-105%');
  await expect.poll(() => drawer.evaluate(element => getComputedStyle(element).animationName)).toBe('documents-enter');
  await drawer.getByRole('button', { name: 'بستن' }).click();
  await expect(drawer).toHaveAttribute('data-closing', 'true');
  await expect.poll(() => drawer.evaluate(element => getComputedStyle(element).animationName)).toBe('documents-exit');
  await expect(drawer).not.toBeVisible();
});

test('keyboard navigation keeps the active slash command visible in its scroll panel', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('parsrag_settings_v1', JSON.stringify({ language: 'en', theme: 'light' }));
    localStorage.setItem('parsrag_tour_v1', 'done');
  });
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.goto('/');
  const composer = page.getByRole('textbox', { name: 'Your message' });
  await composer.fill('/');
  const list = page.getByRole('listbox', { name: 'Quick commands' });
  await expect(list).toBeVisible();
  await composer.press('ArrowUp');
  await expect.poll(() => list.evaluate(element => {
    const selected = element.querySelector('[aria-selected="true"]');
    if (!selected) return false;
    const viewport = element.getBoundingClientRect();
    const item = selected.getBoundingClientRect();
    return element.scrollTop > 0 && item.top >= viewport.top && item.bottom <= viewport.bottom;
  })).toBe(true);
  await composer.press('ArrowDown');
  await expect(list.locator('[aria-selected="true"]')).toHaveAttribute('id', 'composer-option-0');
  await expect.poll(() => list.evaluate(element => {
    const viewport = element.getBoundingClientRect();
    const item = element.querySelector('[aria-selected="true"]')!.getBoundingClientRect();
    return item.top >= viewport.top && item.bottom <= viewport.bottom;
  })).toBe(true);
});

test('Windows and Linux shortcuts work and the settings guide reflects Control keys', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
    localStorage.setItem('parsrag_settings_v1', JSON.stringify({ language: 'en', theme: 'light' }));
    localStorage.setItem('parsrag_tour_v1', 'done');
  });
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.goto('/');
  await expect(page.getByRole('textbox', { name: 'Your message' })).toBeVisible();
  await page.keyboard.press('Control+Shift+k');
  await expect(page.getByRole('textbox', { name: 'Search conversations' })).toBeFocused();
  await page.getByRole('button', { name: 'Toggle conversations' }).click();
  await page.keyboard.press('/');
  const composer = page.getByRole('textbox', { name: 'Your message' });
  await expect(composer).toBeFocused();
  await composer.fill('A draft to keep in the previous conversation');
  await page.keyboard.press('Control+Shift+o');
  await expect(composer).toHaveValue('');
  await page.keyboard.press('Control+Shift+d');
  const documents = page.getByRole('dialog', { name: /Conversation documents/ });
  await expect(documents).toBeVisible();
  await documents.getByRole('button', { name: 'Close' }).click();
  await expect(documents).toBeHidden();
  await page.keyboard.press('Control+,');
  const settings = page.getByRole('dialog', { name: /Settings/ });
  await expect(settings).toBeVisible();
  await expect(settings.getByRole('region', { name: 'Keyboard shortcuts' }).getByText('Ctrl+Shift+O')).toBeVisible();
  await settings.getByRole('button', { name: 'Close' }).click();
  await expect(settings).toBeHidden();
  await page.keyboard.press('Control+Shift+y');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.keyboard.press('Control+Shift+h');
  await expect(page.getByRole('dialog', { name: 'ParsRAG tour' })).toBeVisible();
});

test('macOS shortcuts use Command and do not respond to Control', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' });
    localStorage.setItem('parsrag_settings_v1', JSON.stringify({ language: 'en', theme: 'light' }));
    localStorage.setItem('parsrag_tour_v1', 'done');
  });
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.goto('/');
  const search = page.getByRole('textbox', { name: 'Search conversations' });
  await page.keyboard.press('Control+Shift+k');
  await expect(search).not.toBeFocused();
  await page.keyboard.press('Meta+Shift+k');
  await expect(search).toBeFocused();
  await page.getByRole('button', { name: 'Settings' }).click();
  await expect(page.getByRole('region', { name: 'Keyboard shortcuts' }).getByText('⌘⇧O')).toBeVisible();
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
  await expect(tour.getByText('Conversation space')).toBeVisible();
  await tour.getByRole('button', { name: 'Skip' }).click();
  await expect(tour).toBeHidden();
  await page.getByRole('button', { name: 'Settings' }).click();
  await page.getByRole('button', { name: 'Show tour' }).click();
  await expect(tour).toBeVisible();
});

test('tour opens real document, composer, and settings controls without changing saved settings', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('parsrag_settings_v1', JSON.stringify({ language: 'en', theme: 'light', palette: 'evergreen' }));
    localStorage.removeItem('parsrag_tour_v1');
  });
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/sessions/*/files', route => route.fulfill({ json: [] }));
  await page.route('**/models/configuration', route => route.fulfill({ json: {
    provider: 'ollama', model_name: 'qwen2.5:7b', base_url: 'http://ollama:11434',
    api_key_configured: false, disclosure_acknowledged: false,
  } }));
  await page.goto('/');
  const tour = page.getByRole('dialog', { name: 'ParsRAG tour' });
  const advanceTo = async (title: string) => {
    for (let attempt = 0; attempt < 34; attempt += 1) {
      if (await tour.getByRole('heading', { name: title }).isVisible()) return;
      await tour.getByRole('button', { name: 'Next' }).click();
    }
    throw new Error(`Tour step not found: ${title}`);
  };
  const expectHighlightOn = async (selector: string) => {
    await expect.poll(async () => {
      const target = await page.locator(selector).first().boundingBox();
      const highlight = await tour.locator('.tour-highlight').boundingBox();
      return Boolean(target && highlight && Math.abs(highlight.x - target.x) < 10 && Math.abs(highlight.y - target.y) < 10);
    }).toBe(true);
  };
  await advanceTo('Upload a document');
  await expect(page.locator('.documents-dialog')).toBeVisible();
  await expect(page.locator('[data-tour="document-upload"]')).toBeVisible();
  await expectHighlightOn('[data-tour="document-upload"]');
  await advanceTo('Reuse a document');
  await expect(page.locator('[data-tour="document-reuse"]')).toBeVisible();
  await advanceTo('Select or remove documents');
  await expect(page.locator('[data-tour="document-selection"]')).toBeVisible();
  await advanceTo('Mention a document with @');
  await expect(page.locator('.documents-dialog')).toBeHidden();
  await expect(page.locator('[data-tour="mention-menu"]')).toBeVisible();
  await expectHighlightOn('[data-tour="mention-menu"]');
  await advanceTo('Quick commands with /');
  await expect(page.locator('[data-tour="command-menu"]')).toBeVisible();
  await expectHighlightOn('[data-tour="command-menu"]');
  await advanceTo('Three answer modes');
  await expect(page.locator('[data-tour="mode-menu"] [role="menuitemradio"]')).toHaveCount(3);
  await expectHighlightOn('[data-tour="mode-menu"]');
  await advanceTo('Install the app (PWA)');
  await expect(page.locator('.settings-dialog')).toBeVisible();
  await expect(page.locator('[data-tour="settings-pwa"]')).toBeVisible();
  await expectHighlightOn('[data-tour="settings-pwa"]');
  await advanceTo('Default answer mode');
  await expect(page.locator('#tab-rag')).toHaveAttribute('aria-selected', 'true');
  await advanceTo('Model provider');
  await expect(page.locator('input[name="provider"]:checked')).toHaveCount(1);
  await expect(page.locator('input[name="provider"]:checked').locator('..')).toContainText('Ollama');
  await advanceTo('API key');
  await expect(page.locator('input[name="provider"]:checked').locator('..')).toContainText('API');
  await expect(page.locator('[data-tour="settings-api-key"]')).toBeVisible();
  await tour.getByRole('button', { name: 'Skip' }).click();
  await expect(page.locator('.settings-dialog')).toBeHidden();
  await expect(page.locator('[data-tour="mention-menu"]')).toHaveCount(0);
  await expect(page.locator('[data-tour="command-menu"]')).toHaveCount(0);
  await expect(page.locator('[data-tour="mode-menu"]')).toHaveCount(0);
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('parsrag_settings_v1') || '{}').palette)).toBe('evergreen');
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
  const total = Number((await tour.locator('.tour-card-heading span').innerText()).split('/')[1].trim());
  for (let step = 0; step < total; step += 1) {
    await expect(tour).toBeVisible();
    await expect(tour.locator('.tour-highlight')).toHaveCount(1);
    const bounds = await tour.locator('.tour-card').boundingBox();
    expect(bounds).not.toBeNull();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.y).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(375);
    expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(667);
    await tour.getByRole('button', { name: step === total - 1 ? 'شروع کنیم' : 'بعدی' }).click();
  }
  await expect(tour).toBeHidden();
  await expect.poll(() => page.locator('main').evaluate(element => element.inert)).toBe(false);
  await page.reload();
  await expect(tour).toBeHidden();
});

test('tour highlights prompt controls, citations, and answer actions when a conversation exists', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.addInitScript(() => {
    localStorage.setItem('parsrag_settings_v1', JSON.stringify({ language: 'en', theme: 'light' }));
    localStorage.removeItem('parsrag_tour_v1');
    localStorage.setItem('parsrag_sessions_v1', JSON.stringify([{
      id: 'guided', title: 'Research', createdAt: 1, updatedAt: 1, ragMode: 'strict', draft: '',
      documents: [{ name: 'guide.pdf', status: 'indexed' }],
      messages: [
        { id: 'user-1', role: 'user', content: 'What does the guide say?', timestamp: 1 },
        { id: 'answer-1', role: 'assistant', content: 'It describes the workflow.', timestamp: 2,
          citations: [{ filename: 'guide.pdf', locations: [{ kind: 'page', start: 2 }] }] },
      ],
    }]));
    localStorage.setItem('parsrag_active_session_id_v1', 'guided');
  });
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/sessions/guided/files', route => route.fulfill({ json: ['guide.pdf'] }));
  await page.goto('/');
  const tour = page.getByRole('dialog', { name: 'ParsRAG tour' });
  await expect(tour).toBeVisible();
  for (const [index, selector, title] of [
    [13, '[data-tour="prompt-actions"]', 'Edit your question'],
    [14, '[data-tour="sources"]', 'Answer sources'],
    [15, '[data-tour="response-actions"]', 'Control an answer'],
  ] as const) {
    while (Number((await tour.locator('.tour-card-heading span').innerText()).split('/')[0].trim()) <= index) {
      await tour.getByRole('button', { name: 'Next' }).click();
    }
    await expect(tour.getByRole('heading', { name: title })).toBeVisible();
    await expect.poll(async () => {
      const target = await page.locator(selector).first().boundingBox();
      const highlight = await tour.locator('.tour-highlight').boundingBox();
      return Boolean(target && highlight && Math.abs(highlight.x - target.x) < 10 && Math.abs(highlight.y - target.y) < 10);
    }).toBe(true);
  }
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
  await expect(docs).toBeHidden();
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
  await settings.locator('.theme-choice.preview-dark').click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-palette', 'ocean');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
});

test('workspace, document, and settings scroll areas stay usable in both themes', async ({ page }) => {
  await page.setViewportSize({ width: 920, height: 600 });
  await page.addInitScript(() => {
    localStorage.setItem('parsrag_tour_v1', 'done');
    localStorage.setItem('parsrag_settings_v1', JSON.stringify({ language: 'en', theme: 'light' }));
    const sessions = Array.from({ length: 24 }, (_, index) => ({
      id: `scroll-${index}`, title: `Conversation ${index}`, createdAt: index + 1,
      updatedAt: index + 1, ragMode: 'strict', draft: '',
      documents: index === 23 ? Array.from({ length: 8 }, (_, file) => ({ name: `document-${file}.pdf`, status: 'indexed' })) : [],
      messages: index === 23 ? Array.from({ length: 20 }, (_, message) => ({
        id: `message-${message}`, role: message % 2 ? 'assistant' : 'user',
        content: `Long response ${message}: ${'document evidence '.repeat(18)}`, timestamp: message + 1,
      })) : [{ id: `history-${index}`, role: 'user', content: `Question ${index}`, timestamp: index + 1 }],
    }));
    localStorage.setItem('parsrag_sessions_v1', JSON.stringify(sessions));
    localStorage.setItem('parsrag_active_session_id_v1', 'scroll-23');
  });
  await page.route('**/health/ready', route => route.fulfill({ json: { status: 'ready' } }));
  await page.route('**/sessions/scroll-23/files', route => route.fulfill({ json: Array.from({ length: 8 }, (_, index) => `document-${index}.pdf`) }));
  await page.goto('/');
  const checkScroll = async (selector: string) => {
    const scroll = page.locator(selector).first();
    await expect(scroll).toBeVisible();
    const state = await scroll.evaluate(element => {
      element.scrollTop = element.scrollHeight;
      return { max: element.scrollHeight - element.clientHeight, position: element.scrollTop,
        color: getComputedStyle(element).scrollbarColor };
    });
    expect(state.max).toBeGreaterThan(0);
    expect(state.position).toBeGreaterThan(0);
    expect(state.color).not.toBe('auto');
  };
  await checkScroll('.history-list');
  await checkScroll('.chat-feed');
  await page.getByRole('button', { name: 'Documents' }).first().click();
  await checkScroll('.documents-dialog');
  await page.locator('.documents-dialog .dialog-header button').click();
  await page.getByRole('button', { name: 'Settings' }).click();
  await page.getByRole('tab', { name: /Model/ }).click();
  await checkScroll('.settings-dialog');
  await page.locator('.settings-dialog .dialog-header button').click();
  await page.getByRole('button', { name: /dark/i }).first().click();
  await checkScroll('.history-list');
  await checkScroll('.chat-feed');
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
