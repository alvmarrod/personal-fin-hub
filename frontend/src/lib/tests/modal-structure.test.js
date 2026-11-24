import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const MODALS = join(process.cwd(), 'src', 'lib', 'components', 'modals');
const files = readdirSync(MODALS).filter((name) => name.endsWith('.svelte'));

describe('modal structure', () => {
  it('finds the modal directory', () => {
    expect(files.length).toBeGreaterThan(20);
  });

  it('uses ModalForm, FormActions and FormError instead of local copies', () => {
    const legacy = [
      /<div class="form">/,
      /<div class="form-actions">/,
      /<div class="actions">/,
      /<p class="(?:form-error|error)">/,
      /\.(?:form|form-actions|actions|form-error|error)\s*\{/,
    ];
    const offenders = [];
    for (const name of files) {
      const source = readFileSync(join(MODALS, name), 'utf8');
      for (const pattern of legacy) {
        if (pattern.test(source)) offenders.push(`${name}: ${pattern}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it('imports every shared form component it uses', () => {
    const offenders = [];
    for (const name of files) {
      const source = readFileSync(join(MODALS, name), 'utf8');
      for (const component of ['ModalForm', 'FormActions', 'FormError']) {
        if (source.includes(`<${component}`) && !source.includes(`import ${component}`)) {
          offenders.push(`${name}: ${component}`);
        }
      }
    }
    expect(offenders).toEqual([]);
  });
});
