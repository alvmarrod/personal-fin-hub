<script>
  import { onMount } from 'svelte';
  import { t } from '$lib/i18n/index.svelte';
  import { debtApi } from '$lib/api/debt.js';
  import { displayCurrency, currencySymbol } from '$lib/preferences/currency.svelte';
  import { privacyHidden } from '$lib/preferences/privacy.svelte';
  import { formatAmount, formatDate, formatPercent, maskAmount } from '$lib/utils/format.svelte';
  import { EmptyState } from '$lib/components/index.js';
  import Button from '$lib/components/Button.svelte';
  import DebtFormModal from '$lib/components/modals/DebtFormModal.svelte';
  import DebtPaymentModal from '$lib/components/modals/DebtPaymentModal.svelte';
  import DebtRateModal from '$lib/components/modals/DebtRateModal.svelte';
  import DebtSettleModal from '$lib/components/modals/DebtSettleModal.svelte';
  import DebtPlanModal from '$lib/components/modals/DebtPlanModal.svelte';
  import DebtDetailModal from '$lib/components/modals/DebtDetailModal.svelte';
  import ConfirmDeleteModal from '$lib/components/modals/ConfirmDeleteModal.svelte';
  import TutorialOverlay from '$lib/tutorial/TutorialOverlay.svelte';
  import ReplayButton from '$lib/tutorial/replay/ReplayButton.svelte';
  import * as tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import { debt as debtTutorial } from '$lib/tutorial/definitions/index';
  import debtMock from '$lib/tutorial/mocks/debt';
  import PageHeader from '$lib/components/PageHeader.svelte';

  tutorialStore.registerMock('debt', debtMock);

  let loading = $state(true);
  let error = $state(null);
  let debts = $state([]);
  let summary = $state(null);

  let direction = $state('all');
  let status = $state('active');

  let detailOpen = $state(false);
  let detailId = $state(null);
  let formOpen = $state(false);
  let editing = $state(null);
  let paymentOpen = $state(false);
  let paying = $state(null);
  let rateOpen = $state(false);
  let rating = $state(null);
  let settleOpen = $state(false);
  let settling = $state(null);
  let planOpen = $state(false);
  let planning = $state(null);
  let confirmOpen = $state(false);
  let confirming = $state(null);
  let confirmKind = $state('delete');

  let symbol = $derived(currencySymbol());

  async function load() {
    loading = true;
    error = null;
    try {
      const [list, totals] = await Promise.all([
        debtApi.list({
          direction: direction === 'all' ? null : direction,
          status: status === 'all' ? null : status,
        }),
        debtApi.summary(displayCurrency()),
      ]);
      debts = list ?? [];
      summary = totals;
    } catch (e) {
      error = e?.message || t('debt.loadFailed');
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    const requested = new URLSearchParams(window.location.search).get('direction');
    if (requested === 'payable' || requested === 'receivable') direction = requested;
    load();
  });

  let _tutWasOn = $state(tutorialStore.isActiveFor('debt'));
  $effect(() => {
    const on = tutorialStore.isActiveFor('debt');
    if (on && !_tutWasOn) load();
    _tutWasOn = on;
  });

  function setDirection(value) {
    direction = value;
    load();
  }

  function setStatus(event) {
    status = event.target.value;
    load();
  }

  function totalMoney(value) {
    return maskAmount(`${symbol}${formatAmount(value)}`, symbol);
  }

  function money(value, code) {
    return maskAmount(`${formatAmount(value)} ${code}`, code);
  }

  function today() {
    return new Date().toISOString().slice(0, 10);
  }

  function statusLabel(value) {
    if (value === 'settled') return t('debt.statusSettled');
    if (value === 'cancelled') return t('debt.statusCancelled');
    return t('debt.statusActive');
  }

  function openDetail(debt) {
    detailId = debt.id;
    detailOpen = true;
  }

  function openForm(debt) {
    detailOpen = false;
    editing = debt;
    formOpen = true;
  }

  function openPayment(debt) {
    detailOpen = false;
    paying = debt;
    paymentOpen = true;
  }

  function openRate(debt) {
    detailOpen = false;
    rating = debt;
    rateOpen = true;
  }

  function openSettle(debt) {
    detailOpen = false;
    settling = debt;
    settleOpen = true;
  }

  function openPlan(debt) {
    detailOpen = false;
    planning = debt;
    planOpen = true;
  }

  function openConfirm(debt, kind) {
    detailOpen = false;
    confirming = debt;
    confirmKind = kind;
    confirmOpen = true;
  }

  async function confirmAction() {
    if (!confirming) return;
    try {
      if (confirmKind === 'delete') {
        await debtApi.remove(confirming.id);
      } else {
        await debtApi.cancel(confirming.id, { cancelled_at: today() });
      }
      confirmOpen = false;
      await load();
    } catch (e) {
      error = e?.message || t('debt.saveFailed');
      confirmOpen = false;
    }
  }

  let confirmTitle = $derived(confirmKind === 'delete' ? t('debt.deleteTitle') : t('debt.cancelTitle'));
  let confirmMessage = $derived(confirmKind === 'delete' ? t('debt.deleteMessage') : t('debt.cancelMessage'));
</script>

<PageHeader title={t('debt.title')}>
  <ReplayButton page="debt" />
  {#snippet actions()}
    <span class="debt-add">
      <Button variant="primary" size="sm" onclick={() => openForm(null)}>{t('debt.add')}</Button>
    </span>
  {/snippet}
</PageHeader>

{#if loading}
  <p class="loading">{t('debt.loading')}</p>
{:else if error}
  <div class="error-card">
    <p class="error-message">{error}</p>
    <Button variant="secondary" size="sm" onclick={load}>{t('common.retry')}</Button>
  </div>
{:else}
  <div class="tiles debt-tiles">
    <div class="tile">
      <span class="tile-label">{t('debt.totalPayable')}</span>
      <strong class="tile-value">{totalMoney(summary?.payable ?? 0)}</strong>
      <span class="tile-note">
        {t('debt.accrued')}: {totalMoney(summary?.payable_accrued_interest ?? 0)} ·
        {summary?.payable_count ?? 0} {t('debt.activeDebts')}
      </span>
    </div>
    <div class="tile">
      <span class="tile-label">{t('debt.totalReceivable')}</span>
      <strong class="tile-value">{totalMoney(summary?.receivable ?? 0)}</strong>
      <span class="tile-note">
        {t('debt.accrued')}: {totalMoney(summary?.receivable_accrued_interest ?? 0)} ·
        {summary?.receivable_count ?? 0} {t('debt.activeDebts')}
      </span>
    </div>
  </div>

  <div class="filters debt-filters">
    <div class="tabs">
      <button class="tab" class:active={direction === 'all'} onclick={() => setDirection('all')}>
        {t('debt.allDirections')}
      </button>
      <button class="tab" class:active={direction === 'payable'} onclick={() => setDirection('payable')}>
        {t('debt.iOwe')}
      </button>
      <button class="tab" class:active={direction === 'receivable'} onclick={() => setDirection('receivable')}>
        {t('debt.owedToMe')}
      </button>
    </div>
    <select class="status-select" value={status} onchange={setStatus}>
      <option value="active">{t('debt.statusActive')}</option>
      <option value="settled">{t('debt.statusSettled')}</option>
      <option value="cancelled">{t('debt.statusCancelled')}</option>
      <option value="all">{t('debt.allStatuses')}</option>
    </select>
  </div>

  {#if debts.length === 0}
    <EmptyState title={t('debt.emptyTitle')} message={t('debt.emptyMsg')} />
  {:else}
    <div class="table-wrap debt-table">
      <table class="data-table">
        <thead>
          <tr>
            <th>{t('debt.colCounterparty')}</th>
            <th>{t('debt.colDirection')}</th>
            <th class="num">{t('debt.colOutstanding')}</th>
            <th class="num">{t('debt.colRate')}</th>
            <th>{t('debt.colNext')}</th>
            <th>{t('debt.colProgress')}</th>
            <th>{t('debt.colStatus')}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each debts as debt (debt.id)}
            <tr class="row" onclick={() => openDetail(debt)}>
              <td>
                <span class="name">{debt.counterparty_name}</span>
                {#if debt.description}<span class="desc">{debt.description}</span>{/if}
              </td>
              <td>
                <span class="badge badge-{debt.direction}">
                  {debt.direction === 'payable' ? t('debt.iOwe') : t('debt.owedToMe')}
                </span>
              </td>
              <td class="num">{money(debt.outstanding_principal, debt.currency)}</td>
              <td class="num">{formatPercent(debt.current_rate)}</td>
              <td>
                {#if debt.next_payment_date}
                  <span class="next-date">{formatDate(debt.next_payment_date)}</span>
                  {#if debt.next_payment_amount}<span class="desc">{money(debt.next_payment_amount, debt.currency)}</span>{/if}
                {:else}
                  —
                {/if}
              </td>
              <td>
                <div class="bar"><div class="bar-fill" style="width: {Math.min(debt.progress_pct, 100)}%"></div></div>
                {#if !privacyHidden()}<span class="desc">{formatPercent(debt.progress_pct)}</span>{/if}
              </td>
              <td><span class="status status-{debt.status}">{statusLabel(debt.status)}</span></td>
              <td class="actions-cell">
                <button class="link-btn" onclick={(event) => { event.stopPropagation(); openForm(debt); }}>
                  {t('common.edit')}
                </button>
                {#if debt.status === 'active'}
                  <button class="link-btn" onclick={(event) => { event.stopPropagation(); openPayment(debt); }}>
                    {t('debt.addPayment')}
                  </button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
{/if}

<DebtFormModal
  open={formOpen}
  debt={editing}
  onclose={() => { formOpen = false; editing = null; }}
  onsaved={load}
/>
<DebtPaymentModal
  open={paymentOpen}
  debt={paying}
  onclose={() => { paymentOpen = false; paying = null; }}
  onsaved={load}
/>
<DebtRateModal
  open={rateOpen}
  debt={rating}
  onclose={() => { rateOpen = false; rating = null; }}
  onsaved={load}
/>
<DebtSettleModal
  open={settleOpen}
  debt={settling}
  onclose={() => { settleOpen = false; settling = null; }}
  onsaved={load}
/>
<DebtPlanModal
  open={planOpen}
  debt={planning}
  onclose={() => { planOpen = false; planning = null; }}
  onsaved={load}
/>
<DebtDetailModal
  open={detailOpen}
  debtId={detailId}
  onclose={() => { detailOpen = false; }}
  onedit={openForm}
  onpayment={openPayment}
  onrate={openRate}
  onsettle={openSettle}
  oncancel={(debt) => openConfirm(debt, 'cancel')}
  ondelete={(debt) => openConfirm(debt, 'delete')}
  onplan={openPlan}
/>
<TutorialOverlay definition={debtTutorial} page="debt" onfinish={load} />
<ConfirmDeleteModal
  open={confirmOpen}
  onclose={() => { confirmOpen = false; confirming = null; }}
  onconfirm={confirmAction}
  title={confirmTitle}
  message={confirmMessage}
  entityName={confirming?.counterparty_name ?? ''}
/>

<style>
  .loading {
    color: var(--color-text-muted);
  }
  .error-card {
    padding: var(--space-4);
    border: 1px solid var(--color-danger);
    border-radius: var(--radius-md);
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
  .error-message {
    margin: 0;
    color: var(--color-danger);
  }
  .tiles {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-4);
    margin-bottom: var(--space-5);
  }
  .tile {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    padding: var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-surface);
  }
  .tile-label {
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
  }
  .tile-value {
    font-size: var(--font-size-2xl);
  }
  .tile-note {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }
  .filters {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
    flex-wrap: wrap;
  }
  .tabs {
    display: flex;
    gap: var(--space-2);
  }
  .tab {
    padding: var(--space-1) var(--space-3);
    border: 1px solid var(--color-border);
    background: var(--color-surface);
    color: var(--color-text-secondary);
    border-radius: var(--radius-md);
    font-size: var(--font-size-sm);
    cursor: pointer;
  }
  .tab.active {
    border-color: var(--color-primary);
    background: var(--color-primary-bg);
    color: var(--color-primary);
  }
  .status-select {
    padding: var(--space-1) var(--space-2);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-surface);
    font-size: var(--font-size-sm);
  }
  .table-wrap {
    overflow-x: auto;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
  }
  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
  }
  .data-table th,
  .data-table td {
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--color-border);
    text-align: left;
    white-space: nowrap;
  }
  .data-table th {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    background: var(--color-surface-alt);
  }
  .data-table tr:last-child td {
    border-bottom: none;
  }
  .row {
    cursor: pointer;
  }
  .row:hover {
    background: var(--color-surface-hover);
  }
  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  .name {
    display: block;
    font-weight: var(--font-weight-medium);
  }
  .desc {
    display: block;
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }
  .badge {
    padding: 2px var(--space-2);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
  }
  .badge-payable {
    background: var(--color-danger-bg);
    color: var(--color-danger);
  }
  .badge-receivable {
    background: var(--color-success-bg);
    color: var(--color-success);
  }
  .status {
    font-size: var(--font-size-xs);
  }
  .status-active {
    color: var(--color-primary);
  }
  .status-settled {
    color: var(--color-success);
  }
  .status-cancelled {
    color: var(--color-text-muted);
  }
  .next-date {
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
  }
  .bar {
    width: 80px;
    height: 5px;
    border-radius: var(--radius-full);
    background: var(--color-surface-alt);
    overflow: hidden;
    margin-bottom: 2px;
  }
  .bar-fill {
    height: 100%;
    background: var(--color-primary);
  }
  .link-btn {
    background: none;
    border: none;
    color: var(--color-primary);
    font-size: var(--font-size-xs);
    cursor: pointer;
    padding: var(--space-1);
  }
  .link-btn:hover {
    text-decoration: underline;
  }
  .actions-cell {
    text-align: right;
  }
  @media (max-width: 900px) {
    .tiles {
      grid-template-columns: 1fr;
    }
  }
</style>
