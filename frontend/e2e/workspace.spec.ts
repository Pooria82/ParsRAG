import { expect, test } from '@playwright/test';

test('opens the workspace and model settings against local API fixtures', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('parsrag_settings_v1', JSON.stringify({ language: 'en', theme: 'light' }));
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
