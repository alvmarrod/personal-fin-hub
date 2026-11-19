import { describe, it, expect, beforeEach, vi } from 'vitest';
import { initLocale, locale, localeOptions, setLocale, t } from './index.svelte';

describe('i18n locale', () => {
  beforeEach(() => {
    localStorage.clear();
    setLocale('en-US');
  });

  it('registers Japanese', () => {
    setLocale('ja-JP');
    expect(locale()).toBe('ja-JP');
    expect(localeOptions.map((o) => o.code)).toContain('ja-JP');
  });

  it('translates Japanese labels', () => {
    setLocale('ja-JP');
    expect(t('common.save')).toBe('保存');
  });

  it('persists the selected locale', () => {
    setLocale('ja-JP');
    expect(localStorage.getItem('locale')).toBe('ja-JP');
  });

  it('detects a Japanese browser on first visit', () => {
    localStorage.removeItem('locale');
    vi.stubGlobal('navigator', { language: 'ja-JP' });
    initLocale();
    expect(locale()).toBe('ja-JP');
    vi.unstubAllGlobals();
  });
});
