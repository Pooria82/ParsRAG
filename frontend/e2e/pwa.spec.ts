import { expect, test } from '@playwright/test';

test('production workspace installs an offline shell without caching API data', async ({ page, request }) => {
  const healthRoute = (route: import('@playwright/test').Route) => route.fulfill({ status: 503, json: { status: 'preparing' } });
  await page.route('**/health/ready', healthRoute);
  await page.addInitScript(() => {
    localStorage.setItem('parsrag_tour_v1', 'done');
    localStorage.setItem('parsrag_settings_v1', JSON.stringify({ language: 'en', theme: 'light' }));
  });
  await page.goto('/');
  const manifestResponse = await request.get('/manifest.webmanifest');
  expect(manifestResponse.ok()).toBe(true);
  const manifest = await manifestResponse.json();
  expect(manifest).toMatchObject({ id: '/', start_url: '/', scope: '/', display: 'standalone' });
  for (const icon of manifest.icons) expect((await request.get(icon.src)).ok()).toBe(true);

  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload();
  await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
  const cachedUrls = await page.evaluate(async () => {
    const names = await caches.keys();
    const urls = await Promise.all(names.map(async name => (await caches.open(name)).keys()));
    return urls.flat().map(request => new URL(request.url).pathname);
  });
  expect(cachedUrls).toContain('/index.html');
  expect(cachedUrls).toContain('/manifest.webmanifest');
  expect(cachedUrls.some(url => /^\/(?:health|query|queries|sessions|models|ingest)/.test(url))).toBe(false);

  await page.unroute('**/health/ready', healthRoute);
  await page.context().setOffline(true);
  await page.reload();
  await expect(page.getByRole('textbox', { name: 'Your message' })).toBeVisible();
  const apiUnavailable = await page.evaluate(() => fetch('/health/ready').then(() => false, () => true));
  expect(apiUnavailable).toBe(true);
});

test('install action appears when the browser offers installation', async ({ page }) => {
  await page.route('**/health/ready', route => route.fulfill({ status: 503, json: { status: 'preparing' } }));
  await page.addInitScript(() => {
    localStorage.setItem('parsrag_tour_v1', 'done');
    localStorage.setItem('parsrag_settings_v1', JSON.stringify({ language: 'en', theme: 'light' }));
  });
  await page.goto('/');
  await page.evaluate(() => {
    const event = new Event('beforeinstallprompt', { cancelable: true });
    Object.assign(event, {
      prompt: async () => { (window as Window & { __prompted?: boolean }).__prompted = true; },
      userChoice: Promise.resolve({ outcome: 'accepted' }),
    });
    window.dispatchEvent(event);
  });
  await page.getByRole('button', { name: 'Settings' }).click();
  await page.getByRole('button', { name: 'Install app' }).click();
  await expect.poll(() => page.evaluate(() => (window as Window & { __prompted?: boolean }).__prompted)).toBe(true);
});
