// Offline release guard for Cloudflare Workers Builds; no Python/Chromium required.
import { createHash } from 'node:crypto';
import { readdir, readFile, lstat } from 'node:fs/promises';
import { resolve, relative, sep } from 'node:path';

const root = resolve(process.argv[2] || 'public');
const manifestPath = process.argv[3] || `${root}.release.json`;
const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
if (!manifest.issues?.length || manifest.issues.some(issue => !['approved', 'published'].includes(issue.status))) {
  throw new Error('Release must contain only approved/published issues');
}
if (!manifest.site_url?.startsWith('https://')) throw new Error('Release needs an HTTPS canonical origin');
const expected = manifest.files;
if (!expected || Object.keys(expected).length > 20000) throw new Error('Invalid release manifest');
const actual = {};
async function walk(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name);
    const name = relative(root, path).split(sep).join('/');
    const info = await lstat(path);
    if (info.isSymbolicLink()) throw new Error(`Symlink in release: ${name}`);
    if (info.isDirectory()) { await walk(path); continue; }
    if (!info.isFile() || info.size > 25 * 1024 * 1024) throw new Error(`Invalid asset: ${name}`);
    if (name.endsWith('.json') || name.split('/').some(part => part.startsWith('.'))) {
      throw new Error(`Internal file in public release: ${name}`);
    }
    const bytes = await readFile(path);
    actual[name] = createHash('sha256').update(bytes).digest('hex');
    if (expected[name] !== actual[name]) throw new Error(`Unreviewed or changed release file: ${name}`);
    if (name.endsWith('.html') && name !== '404.html') {
      const html = bytes.toString('utf8');
      if (/<meta[^>]*name=["']robots["'][^>]*noindex|<small>[^<]*(?:Локальный просмотр|Local preview|ローカルプレビュー)/i.test(html)) {
        throw new Error(`Preview page in release: ${name}`);
      }
    }
  }
}
await walk(root);
if (Object.keys(actual).length !== Object.keys(expected).length) throw new Error('Release files are missing');
for (const name of ['index.html', '404.html', 'style.css', 'robots.txt', 'sitemap.xml']) {
  if (!actual[name]) throw new Error(`Release lacks ${name}`);
}
for (const lang of ['ru', 'en', 'ja']) {
  if (!actual[`${lang}/rss.xml`]) throw new Error(`Missing ${lang} RSS`);
  for (const issue of manifest.issues) {
    if (!actual[`${lang}/issues/${issue.issue_id}/edition.pdf`]) throw new Error(`Missing ${lang} issue PDF`);
  }
}
const robots = await readFile(resolve(root, 'robots.txt'), 'utf8');
if (/Disallow:\s*\/\s*(?:\n|$)/.test(robots)) throw new Error('Release blocks indexing');
console.log(`Verified ${Object.keys(actual).length} public files; ${manifest.issues.length} issues; ${manifest.site_url}`);
