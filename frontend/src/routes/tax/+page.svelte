<script>
  import { onMount } from 'svelte';
  import { analytics, currenciesApi } from '$lib/api/analytics.js';
  import { t, locale } from '$lib/i18n/index.svelte';
  import { displayCurrency, setDisplayCurrency, currencySymbol } from '$lib/preferences/currency.svelte';
  import { LoadingSpinner, EmptyState } from '$lib/components/index.js';
  import Select from '$lib/components/Select.svelte';
  import Button from '$lib/components/Button.svelte';

  let loading = $state(true);
  let error = $state(null);
  let taxable = $state(null);
  let currencyCodes = $state([]);

  let _displayCurrency = $derived(displayCurrency());
  let _currencySymbol = $derived(currencySymbol());

  let ruleset = $state('');

  const rulesetOptions = ['spain', 'japan', 'default', 'latest', 'none'].map((key) => ({
    value: key,
    label: t(`fiscalRules.rule.${key}`),
  }));

  async function loadAll() {
    loading = true;
    error = null;
    try {
      taxable = await analytics.taxablePnl(_displayCurrency, locale(), ruleset);
    } catch (e) {
      error = e.message || t('common.errorPrefix', { resource: 'tax data' });
    } finally {
      loading = false;
    }
  }

  function formatMoney(val) {
    if (val == null) return '-';
    return val.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  onMount(async () => {
    try {
      currencyCodes = await currenciesApi.getList();
    } catch (_) {}
    await loadAll();
  });
</script>

<div class="page-header">
  <div class="page-title-row">
    <h1 class="page-title">{t('tax.title')}</h1>
  </div>
  <div class="page-actions">
    <Select
      value={ruleset}
      placeholder={t('tax.ruleset')}
      options={rulesetOptions}
      onchange={(e) => { ruleset = e.target.value; loadAll(); }}
    />
    <Select
      value={_displayCurrency}
      options={currencyCodes.map(c => ({ value: c, label: c }))}
      onchange={(e) => { setDisplayCurrency(e.target.value); loadAll(); }}
    />
  </div>
</div>

{#if loading}
  <LoadingSpinner message={t('tax.loading')} />
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={loadAll}>{t('common.retry')}</Button>
  </div>
{:else if !taxable || taxable.fiscal_years.length === 0}
  <EmptyState title={t('tax.emptyTitle')} message={t('tax.emptyMsg')} />
{:else}
  {#if taxable.rate_fallbacks?.length > 0}
    <div class="rate-warning">
      <div class="rate-warning-icon">⚠</div>
      <div class="rate-warning-content">
        <strong>{t('tax.rateFallbackTitle')}</strong>
        <p>{t('tax.rateFallbackMsg')}</p>
      </div>
    </div>
  {/if}

  <div class="table-wrap">
    <table class="data-table">
      <thead>
        <tr>
          <th>{t('tax.fiscalYear')}</th>
          <th class="num">{t('tax.realizedGains')}</th>
          <th class="num">{t('tax.dividends')}</th>
          <th class="num">{t('tax.total')}</th>
          <th class="num">{t('tax.sells')}</th>
          <th class="num">{t('tax.dividendCount')}</th>
        </tr>
      </thead>
      <tbody>
        {#each taxable.fiscal_years as year (year.fiscal_year)}
          <tr>
            <td class="cell-name">{year.fiscal_year}</td>
            <td class="num {year.realized_gains_taxable >= 0 ? 'positive' : 'negative'}">
              {_currencySymbol}{formatMoney(year.realized_gains_taxable)}
            </td>
            <td class="num {year.dividends_taxable >= 0 ? 'positive' : 'negative'}">
              {_currencySymbol}{formatMoney(year.dividends_taxable)}
            </td>
            <td class="num {year.total_taxable >= 0 ? 'positive' : 'negative'}">
              {_currencySymbol}{formatMoney(year.total_taxable)}
            </td>
            <td class="num">{year.num_sells}</td>
            <td class="num">{year.num_dividends}</td>
          </tr>
        {/each}
      </tbody>
      <tfoot>
        <tr>
          <td class="cell-name">{t('tax.totalTaxable')}</td>
          <td></td>
          <td></td>
          <td class="num">{_currencySymbol}{formatMoney(taxable.total_taxable)}</td>
          <td></td>
          <td></td>
        </tr>
      </tfoot>
    </table>
  </div>
{/if}

<style>
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: var(--space-6);
  }

  .page-title-row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .page-title {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-bold);
    margin: 0;
  }

  .page-actions {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .rate-warning {
    display: flex;
    align-items: flex-start;
    gap: var(--space-3);
    background: var(--color-warning-bg, #fff3cd);
    border: 1px solid var(--color-warning-border, #ffc107);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    margin-bottom: var(--space-6);
  }

  .rate-warning-icon {
    font-size: var(--font-size-xl);
    color: var(--color-warning, #856404);
    flex-shrink: 0;
  }

  .rate-warning-content {
    flex: 1;
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
  }

  .rate-warning-content strong {
    display: block;
    margin-bottom: var(--space-1);
    color: var(--color-warning, #856404);
  }

  .rate-warning-content p {
    margin: 0;
  }

  .table-wrap {
    overflow-x: auto;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
  }

  .data-table th,
  .data-table td {
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--color-border);
    text-align: left;
  }

  .data-table th {
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-secondary);
    background: var(--color-surface-alt);
    white-space: nowrap;
  }

  .data-table th.num,
  .data-table td.num {
    text-align: right;
  }

  .data-table tfoot td {
    font-weight: var(--font-weight-semibold);
    border-top: 2px solid var(--color-border);
  }

  .num {
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
  }

  .positive {
    color: var(--color-success);
  }

  .negative {
    color: var(--color-danger);
  }

  .cell-name {
    font-weight: var(--font-weight-medium);
  }

  .error-card {
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    text-align: center;
  }

  .error-message {
    color: var(--color-danger);
    font-size: var(--font-size-sm);
    margin-bottom: var(--space-3);
  }
</style>
