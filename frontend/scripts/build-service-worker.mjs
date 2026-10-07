import { createHash } from 'node:crypto';
import { readFile, readdir, writeFile } from 'node:fs/promises';
import { dirname, join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
const dist = join(frontendRoot, 'dist');
const allowed = /\.(?:html|js|css|woff2?|ttf|svg|png|webmanifest)$/i;

async function collect(directory) {
  const paths = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) paths.push(...await collect(path));
    else if (entry.isFile() && allowed.test(entry.name)) paths.push(path);
  }
  return paths;
}

const files = (await collect(dist)).sort();
const urls = files.map(path => '/' + relative(dist, path).split(sep).join('/'));
if (!urls.includes('/index.html') || !urls.includes('/manifest.webmanifest')) {
  throw new Error('The production shell or app manifest is missing.');
}
const hash = createHash('sha256');
for (const file of files) {
  hash.update(relative(dist, file));
  hash.update(await readFile(file));
}
const name = `parsrag-shell-${hash.digest('hex').slice(0, 16)}`;
const template = await readFile(join(frontendRoot, 'pwa', 'sw.template.js'), 'utf8');
const worker = template
  .replace('__CACHE_NAME__', JSON.stringify(name))
  .replace('__PRECACHE_URLS__', JSON.stringify(urls));
await writeFile(join(dist, 'sw.js'), worker);
process.stdout.write(`Built ${name} with ${urls.length} public files.\n`);
