<script>
  import TextInput from './TextInput.svelte';
  import { dateFormat } from '$lib/preferences/dateFormat.svelte';
  import { formatDate } from '$lib/utils/format.svelte';
  import { t } from '$lib/i18n/index.svelte';

  let { value = $bindable(''), disabled = false, ...rest } = $props();

  let editing = $state(false);
  let text = $state('');
  let nativeEl = $state(null);

  // Keep the visible text in the user's chosen order; the bound value stays ISO.
  $effect(() => {
    const formatted = value ? formatDate(value) : '';
    if (!editing) text = formatted;
  });

  function pad(n) {
    return String(n).padStart(2, '0');
  }

  function parseTyped(raw) {
    const input = raw.trim();
    if (!input) return '';

    const compact = /^(\d{4})(\d{2})(\d{2})$/.exec(input);
    const parts = /^(\d{1,4})[/\-.](\d{1,2})[/\-.](\d{1,4})$/.exec(input);
    let year;
    let month;
    let day;
    if (compact) {
      [, year, month, day] = compact.map(Number);
    } else if (parts) {
      if (parts[1].length === 4) {
        year = Number(parts[1]);
        month = Number(parts[2]);
        day = Number(parts[3]);
      } else if (dateFormat() === 'mdy') {
        month = Number(parts[1]);
        day = Number(parts[2]);
        year = Number(parts[3]);
      } else {
        day = Number(parts[1]);
        month = Number(parts[2]);
        year = Number(parts[3]);
      }
    } else {
      return null;
    }

    const date = new Date(Date.UTC(year, month - 1, day));
    if (
      year < 1000 ||
      year > 9999 ||
      date.getUTCFullYear() !== year ||
      date.getUTCMonth() !== month - 1 ||
      date.getUTCDate() !== day
    ) {
      return null;
    }
    return `${year}-${pad(month)}-${pad(day)}`;
  }

  function commit() {
    const parsed = parseTyped(text);
    editing = false;
    if (parsed === null) {
      text = value ? formatDate(value) : '';
      return;
    }
    value = parsed;
    text = parsed ? formatDate(parsed) : '';
  }

  function handleInput(event) {
    editing = true;
    text = event.target.value;
    const parsed = parseTyped(text);
    if (parsed !== null) value = parsed;
  }

  function handleKeydown(event) {
    if (event.key === 'Enter') {
      event.preventDefault();
      event.currentTarget.blur();
    } else if (event.key === 'Escape') {
      editing = false;
      text = value ? formatDate(value) : '';
      event.currentTarget.blur();
    }
  }

  function openPicker() {
    if (disabled || !nativeEl) return;
    try {
      if (typeof nativeEl.showPicker === 'function') {
        nativeEl.showPicker();
        return;
      }
    } catch {
      // fall through to click
    }
    nativeEl.click();
  }

  function handlePickerChange(event) {
    value = event.target.value;
    editing = false;
    text = value ? formatDate(value) : '';
  }
</script>

<div class="date-input">
  <TextInput
    {...rest}
    type="text"
    {disabled}
    value={text}
    style="padding-right: 2.25rem;"
    oninput={handleInput}
    onfocus={() => (editing = true)}
    onblur={commit}
    onkeydown={handleKeydown}
  />
  <button
    type="button"
    class="picker-btn"
    aria-label={t('common.openCalendar')}
    title={t('common.openCalendar')}
    {disabled}
    onclick={openPicker}
  >
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
      <line x1="16" y1="2" x2="16" y2="6"></line>
      <line x1="8" y1="2" x2="8" y2="6"></line>
      <line x1="3" y1="10" x2="21" y2="10"></line>
    </svg>
  </button>
  <input
    class="native-picker"
    type="date"
    bind:this={nativeEl}
    {value}
    onchange={handlePickerChange}
    tabindex="-1"
    aria-hidden="true"
  />
</div>

<style>
  .date-input {
    position: relative;
  }

  .picker-btn {
    position: absolute;
    top: 50%;
    right: var(--space-2);
    transform: translateY(-50%);
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    padding: 0;
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--color-text-muted);
    cursor: pointer;
  }

  .picker-btn:hover:not(:disabled) {
    background: var(--color-surface-hover);
    color: var(--color-text-primary);
  }

  .picker-btn:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }

  .native-picker {
    position: absolute;
    top: 0;
    left: 0;
    width: 1px;
    height: 1px;
    opacity: 0;
    pointer-events: none;
  }
</style>
