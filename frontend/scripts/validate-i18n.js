import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');

const en = (await import('../src/lib/i18n/locales/en.ts')).default;
const es = (await import('../src/lib/i18n/locales/es.ts')).default;

function findSvelteFiles(dir) {
  const results = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (entry.startsWith('.') || entry === 'node_modules') continue;
    const stat = statSync(full);
    if (stat.isDirectory()) {
      results.push(...findSvelteFiles(full));
    } else if (entry.endsWith('.svelte') || entry.endsWith('.svelte.ts')) {
      results.push(full);
    }
  }
  return results;
}

function extractKeys(source) {
  const keys = new Set();
  const re = /\bt\(\s*['"]([^'"]+)['"]\s*[),}]/g;
  let m;
  while ((m = re.exec(source)) !== null) {
    if (!m[1].includes('${')) keys.add(m[1]);
  }
  return [...keys];
}

console.log(`en-US keys: ${Object.keys(en).length}`);
console.log(`es-ES keys: ${Object.keys(es).length}\n`);

const files = findSvelteFiles(join(root, 'src'));
const allKeys = new Set();

for (const file of files) {
  const source = readFileSync(file, 'utf-8');
  for (const k of extractKeys(source)) allKeys.add(k);
}

console.log(`Files scanned: ${files.length}`);
console.log(`Unique keys used: ${allKeys.size}\n`);

let errors = 0;

for (const key of [...allKeys].sort()) {
  const missing = [];
  if (!(key in en)) missing.push('en-US');
  if (!(key in es)) missing.push('es-ES');
  if (missing.length > 0) {
    console.error(`  MISSING "${key}" in: ${missing.join(', ')}`);
    errors++;
  }
}

if (errors > 0) {
  console.error(`\n${errors} key(s) missing from dictionaries.`);
  process.exit(1);
}

console.log('All keys present in both dictionaries.\n');

const enSet = new Set(Object.keys(en));
const esSet = new Set(Object.keys(es));
const onlyEn = [...enSet].filter(k => !esSet.has(k));
const onlyEs = [...esSet].filter(k => !enSet.has(k));
const unusedEn = [...enSet].filter(k => !allKeys.has(k));
const unusedEs = [...esSet].filter(k => !allKeys.has(k));

if (onlyEn.length) console.log(`${onlyEn.length} key(s) only in en-US (missing from es-ES)`);
if (onlyEs.length) console.log(`${onlyEs.length} key(s) only in es-ES (missing from en-US)`);
if (unusedEn.length) console.log(`${unusedEn.length} unused key(s) in en-US`);
