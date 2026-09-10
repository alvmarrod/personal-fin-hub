<script>
  import { onMount } from 'svelte';
  import { analytics, currenciesApi, crud } from '$lib/api/analytics.js';
  import { t, locale } from '$lib/i18n/index.svelte';
  import { displayCurrency, setDisplayCurrency, currencySymbol, getSymbolFor } from '$lib/preferences/currency.svelte';
  import { formatAmount } from '$lib/utils/format.svelte';
  import { LoadingSpinner, EmptyState } from '$lib/components/index.js';
  import Select from '$lib/components/Select.svelte';
  import Button from '$lib/components/Button.svelte';
  import EditTransactionModal from '$lib/components/modals/EditTransactionModal.svelte';
  import TutorialOverlay from '$lib/tutorial/TutorialOverlay.svelte';
  import ReplayButton from '$lib/tutorial/replay/ReplayButton.svelte';
  import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import { tax as taxTutorial } from '$lib/tutorial/definitions/index';
  import taxMock from '$lib/tutorial/mocks/tax';

  tutorialStore.registerMock('tax', taxMock);

  let loading = $state(true);
  let error = $state(null);
  let taxable = $state(null);
  let currencyCodes = $state([]);

  let _displayCurrency = $derived(displayCurrency());
  let _currencySymbol = $derived(currencySymbol());

  let ruleset = $state('');
  let expandedYear = $state(null);

  let editModalOpen = $state(false);
  let editingTransaction = $state(null);

  const rulesetOptions = ['spain', 'japan', 'default', 'latest', 'none'].map((key) => ({
    value: key,
    label: t(`fiscalRules.rule.${key}`),
  }));

  async function loadAll() {
    loading = true;
    error = null;
    try {
      taxable = await analytics.taxablePnlExtended(_displayCurrency, locale(), ruleset);
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

  function toggleYear(year) {
    expandedYear = expandedYear === year ? null : year;
  }

  function sourceLabel(source) {
    return source === 'confirmed' ? t('tax.source.confirmed') : t('tax.source.computed');
  }

  function taxCategoryKey(cat) {
    return cat === 'capital_gains' ? 'capitalGains' : cat;
  }

  async function handleEditItem(item) {
    try {
      editingTransaction = await crud.transactions.getOne(item.transaction_id);
      editModalOpen = true;
    } catch (e) {
      error = e.message || t('common.errorPrefix', { resource: t('tax.title') });
    }
  }

  onMount(async () => {
    try {
      currencyCodes = await currenciesApi.getList();
    } catch (_) {}
    await loadAll();
  });

  let _tutWasOn = $state(tutorialStore.isActiveFor('tax'));
  $effect(() => {
    const on = tutorialStore.isActiveFor('tax');
    if (on && !_tutWasOn) loadAll();
    _tutWasOn = on;
  });
</script>

<div class="page-header">
  <div class="page-title-row">
    <h1 class="page-title">{t('tax.title')}</h1>
    <ReplayButton page="tax" />
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
          <th class="num">{t('tax.taxOwed')}</th>
          <th class="num">{t('tax.sells')}</th>
          <th class="num">{t('tax.dividendCount')}</th>
        </tr>
      </thead>
      <tbody>
        {#each taxable.fiscal_years as year (year.fiscal_year)}
          <tr class="year-row" class:expanded={expandedYear === year.fiscal_year}>
            <td class="cell-name">
              <button class="expand-btn" onclick={() => toggleYear(year.fiscal_year)}>
                <span class="expand-icon">{expandedYear === year.fiscal_year ? '▼' : '▶'}</span>
                {year.fiscal_year}
              </button>
            </td>
            <td class="num {year.realized_gains_taxable >= 0 ? 'positive' : 'negative'}">
              {_currencySymbol}{formatMoney(year.realized_gains_taxable)}
            </td>
            <td class="num {year.dividends_taxable >= 0 ? 'positive' : 'negative'}">
              {_currencySymbol}{formatMoney(year.dividends_taxable)}
            </td>
            <td class="num {year.total_taxable >= 0 ? 'positive' : 'negative'}">
              {_currencySymbol}{formatMoney(year.total_taxable)}
            </td>
            <td class="num">
              {#if year.tax_owed && typeof year.tax_owed === 'object'}
                {#each Object.entries(year.tax_owed) as [cat, amt]}
                  <div class="tax-cat-row">
                    <span class="tax-cat-label">{t(`tax.items.category.${taxCategoryKey(cat)}`)}</span>
                    <span>{_currencySymbol}{formatMoney(amt)}</span>
                  </div>
                {/each}
              {:else}
                {_currencySymbol}{formatMoney(year.tax_owed)}
              {/if}
            </td>
            <td class="num">{year.num_sells}</td>
            <td class="num">{year.num_dividends}</td>
          </tr>
          {#if expandedYear === year.fiscal_year && year.items?.length > 0}
            <tr class="items-row">
              <td colspan="7">
                <div class="items-table-wrap">
                  <table class="items-table">
                    <thead>
                      <tr>
                        <th>{t('tax.items.date')}</th>
                        <th>{t('tax.items.taxRuleset')}</th>
                        <th>{t('tax.items.asset')}</th>
                        <th>{t('tax.items.category')}</th>
                        <th class="num">{t('tax.items.nativeAmount')}</th>
                        <th class="num">{t('tax.items.displayAmount', { currency: _currencySymbol })}</th>
                        <th>{t('tax.items.taxExemption')}</th>
                        <th class="num">{t('tax.items.taxableAmount')}</th>
                        <th class="num">{t('tax.items.taxOwed')}</th>
                        <th>{t('tax.items.source')}</th>
                        <th>{t('common.actions')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {#each year.items as item (item.transaction_id)}
                        <tr>
                          <td>{item.date?.slice(0, 10) || '-'}</td>
                          <td>{item.fiscal_rule ? t(`fiscalRules.rule.${item.fiscal_rule}`) : '—'}</td>
                          <td>{item.ticker || item.market_code || item.name || `#${item.transaction_id}`}</td>
                          <td>{t(`tax.items.category.${taxCategoryKey(item.category)}`)}</td>
                          <td class="num">{getSymbolFor(item.currency)}{formatAmount(item.native_amount, item.currency)}</td>
                          <td class="num">{_currencySymbol}{formatAmount(item.display_amount, _displayCurrency)}</td>
                          <td>{item.tax_policy || '—'}</td>
                          <td class="num">{_currencySymbol}{formatAmount(item.taxable_amount, _displayCurrency)}</td>
                          <td class="num">
                            {#if item.source === 'confirmed'}
                              {getSymbolFor(item.currency)}{formatAmount(item.tax_owed, item.currency)}
                            {:else}
                              {_currencySymbol}{formatAmount(item.tax_owed, _displayCurrency)}
                            {/if}
                          </td>
                          <td>
                            <span class="source-badge" class:confirmed={item.source === 'confirmed'}>
                              {sourceLabel(item.source)}
                            </span>
                          </td>
                          <td>
                            <button
                              class="icon-btn"
                              title={t('common.edit')}
                              aria-label={t('transactions.editAria')}
                              onclick={() => handleEditItem(item)}
                            >
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                              </svg>
                            </button>
                          </td>
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                </div>
              </td>
            </tr>
          {/if}
        {/each}
      </tbody>
      <tfoot>
        <tr>
          <td class="cell-name">{t('tax.totalTaxable')}</td>
          <td></td>
          <td></td>
          <td class="num">{_currencySymbol}{formatMoney(taxable.total_taxable)}</td>
          <td class="num">{_currencySymbol}{formatMoney(taxable.total_tax_owed)}</td>
          <td></td>
          <td></td>
        </tr>
      </tfoot>
    </table>
  </div>
{/if}

<TutorialOverlay definition={taxTutorial} page="tax" onfinish={loadAll} />

<EditTransactionModal
  open={editModalOpen}
  transaction={editingTransaction}
  onclose={() => { editModalOpen = false; editingTransaction = null; }}
  onsuccess={() => { editModalOpen = false; editingTransaction = null; loadAll(); }}
/>

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

  .expand-btn {
    background: none;
    border: none;
    cursor: pointer;
    font: inherit;
    color: inherit;
    padding: 0;
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
  }

  .expand-icon {
    font-size: 10px;
    color: var(--color-text-muted);
    width: 12px;
    text-align: center;
  }

  .items-row td {
    padding: 0 !important;
    border-bottom: 1px solid var(--color-border);
  }

  .items-table-wrap {
    padding: 0 var(--space-4) var(--space-4);
    background: var(--color-surface-alt);
  }

  .items-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: var(--space-4) 0;
    font-size: var(--font-size-xs);
  }

  .items-table th,
  .items-table td {
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--color-border);
    text-align: left;
  }

  .items-table th {
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-secondary);
    background: var(--color-surface-alt);
  }

  .items-table th.num,
  .items-table td.num {
    text-align: right;
  }

  .source-badge {
    display: inline-block;
    font-size: var(--font-size-2xs);
    font-weight: var(--font-weight-medium);
    padding: 1px 6px;
    border-radius: var(--radius-sm);
    background: var(--color-border);
    color: var(--color-text-secondary);
  }

  .source-badge.confirmed {
    background: var(--color-success-light, #d4edda);
    color: var(--color-success, #155724);
  }

  .icon-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: var(--space-1);
    color: var(--color-text-secondary);
    border-radius: var(--radius-sm);
    transition: background 0.2s ease, color 0.2s ease;
  }

  .icon-btn:hover {
    background: var(--color-surface);
    color: var(--color-text-primary);
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

  .tax-cat-row {
    display: flex;
    justify-content: space-between;
    gap: var(--space-2);
    font-size: var(--font-size-xs);
    line-height: 1.4;
  }

  .tax-cat-label {
    color: var(--color-text-muted);
    font-size: var(--font-size-2xs);
  }
</style>
