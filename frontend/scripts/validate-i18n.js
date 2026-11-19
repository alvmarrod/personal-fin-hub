import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');

const dictionaries = {
  'en-US': (await import('../src/lib/i18n/locales/en.ts')).default,
  'es-ES': (await import('../src/lib/i18n/locales/es.ts')).default,
  'ja-JP': (await import('../src/lib/i18n/locales/ja.ts')).default,
};
const en = dictionaries['en-US'];
const locales = Object.keys(dictionaries);

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

for (const [code, dict] of Object.entries(dictionaries)) {
  console.log(`${code} keys: ${Object.keys(dict).length}`);
}
console.log('');

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
  const missing = locales.filter((code) => !(key in dictionaries[code]));
  if (missing.length > 0) {
    console.error(`  MISSING "${key}" in: ${missing.join(', ')}`);
    errors++;
  }
}

if (errors > 0) {
  console.error(`\n${errors} key(s) missing from dictionaries.`);
  process.exit(1);
}

console.log(`All keys present in all dictionaries (${locales.join(', ')}).\n`);

const enSet = new Set(Object.keys(en));
for (const code of locales.filter((c) => c !== 'en-US')) {
  const other = new Set(Object.keys(dictionaries[code]));
  const onlyEn = [...enSet].filter((k) => !other.has(k));
  const onlyOther = [...other].filter((k) => !enSet.has(k));
  if (onlyEn.length) console.log(`${onlyEn.length} key(s) only in en-US (missing from ${code})`);
  if (onlyOther.length) console.log(`${onlyOther.length} key(s) only in ${code} (missing from en-US)`);
}
for (const code of locales) {
  const unused = Object.keys(dictionaries[code]).filter((k) => !allKeys.has(k));
  if (unused.length) console.log(`${unused.length} unused key(s) in ${code}`);
}
