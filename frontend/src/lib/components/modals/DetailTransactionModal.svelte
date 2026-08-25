<script>
  import Modal from '../Modal.svelte';
  import Badge from '../Badge.svelte';
  import Button from '../Button.svelte';
  import { t } from '$lib/i18n/index.svelte';
  import { api } from '../../api/client.js';

  let { open = false, transaction = null, onclose, onedit, ondelete, assetNameMap = {} } = $props();

  let loading = $state(false);
  let error = $state('');
  let tx = $state(null);
  let fees = $state([]);
  let taxes = $state([]);
  let linkedSpends = $state([]);

  let TYPE_LABELS = $derived({
    'INCOME': t('transactions.typeIncome'),
    'MONEY_OUT': t('transactions.typeExpense'),
    'INVESTMENT_BUY': t('transactions.typeBuy'),
    'INVESTMENT_SELL': t('transactions.typeSell'),
    'TRANSFER': t('transactions.typeTransfer'),
    'TRANSFER_IN': t('transactions.typeTransferIn'),
    'TRANSFER_OUT': t('transactions.typeTransferOut'),
    'BALANCE_ADJUSTMENT': t('transactions.typeAdjustment'),
  });

  const TYPE_VARIANTS = {
    'INCOME': 'success',
    'MONEY_OUT': 'danger',
    'INVESTMENT_BUY': 'primary',
    'INVESTMENT_SELL': 'info',
    'TRANSFER': 'default',
    'TRANSFER_IN': 'default',
    'TRANSFER_OUT': 'default',
    'BALANCE_ADJUSTMENT': 'warning',
  };

  const SPEND_TYPES = ['MONEY_OUT', 'INVESTMENT_BUY', 'TRANSFER_OUT'];

  function cashHandlingLabel(txx) {
    if (!SPEND_TYPES.includes(txx.type)) return null;
    if (txx.cash_handling === 'inject') return t('transactions.cashHandlingInject');
    if (txx.cash_handling === 'debit') return t('transactions.cashHandlingDebit');
    if (txx.cash_handling_effective === 'inject') return t('transactions.cashHandlingAutoInject');
    if (txx.cash_handling_effective === 'debit') return t('transactions.cashHandlingAutoDebit');
    return t('transactions.cashHandlingAuto');
  }

  function isLastLinked(s) {
    return tx?.attached_transaction_ids?.[tx.attached_transaction_ids.length - 1] === s.id;
  }

  function formatType(type) {
    return TYPE_LABELS[type] || type;
  }

  function getTypeVariant(type) {
    return TYPE_VARIANTS[type] || 'default';
  }

  function formatDate(dateStr) {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString();
  }

  function formatNumber(num) {
    if (num === null || num === undefined) return '-';
    return Number(num).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  async function loadTransaction() {
    if (!transaction) return;
    loading = true;
    error = '';
    try {
      const data = await api.get(`/transactions/${transaction.id}/full`);
      tx = data.transaction;
      fees = data.fees || [];
      taxes = data.taxes || [];
      linkedSpends = [];
      if (tx.type === 'BALANCE_ADJUSTMENT' && tx.attached_transaction_ids?.length) {
        try {
          const results = await Promise.all(
            tx.attached_transaction_ids.map(id => api.get(`/transactions/${id}`))
          );
          linkedSpends = results;
        } catch {
          linkedSpends = [];
        }
      }
    } catch (e) {
      error = e.message || t('common.errorPrefix', { resource: 'transaction details' });
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if (open && transaction) {
      loadTransaction();
    }
  });

  function handleEdit() {
    onedit?.(tx);
  }

  function handleDelete() {
    ondelete?.(tx);
  }

  function handleEditFee(fee) {
    // TODO: Implement fee editing modal
    console.log('Edit fee:', fee);
  }

  function handleDeleteFee(fee) {
    // TODO: Implement fee deletion
    console.log('Delete fee:', fee);
  }

  function handleEditTax(tax) {
    // TODO: Implement tax editing modal
    console.log('Edit tax:', tax);
  }

  function handleDeleteTax(tax) {
    // TODO: Implement tax deletion
    console.log('Delete tax:', tax);
  }
</script>

<Modal {open} {onclose} title={t('modals.viewTransaction')} size="lg">
  {#if loading}
    <div class="loading-container">
      <p>{t('common.loading')}</p>
    </div>
  {:else if error}
    <div class="error-container">
      <p class="error-message">{error}</p>
      <Button variant="secondary" size="sm" onclick={loadTransaction}>{t('common.retry')}</Button>
    </div>
  {:else if tx}
    <div class="detail-content">
      <!-- Header -->
      <div class="detail-header">
        <Badge variant={getTypeVariant(tx.type)}>{formatType(tx.type)}</Badge>
        <span class="detail-date">{formatDate(tx.timestamp)}</span>
        <span class="detail-amount">{formatNumber(tx.total_value)} {tx.currency}</span>
      </div>

      <!-- General Information -->
      <div class="detail-section">
        <h4>General Information</h4>
        <div class="detail-grid">
          <div class="detail-field">
            <span class="detail-label">{t('modals.entity')}</span>
            <span>{tx.entity_id}</span>
          </div>
          <div class="detail-field">
            <span class="detail-label">{t('common.currency')}</span>
            <span>{tx.currency}</span>
          </div>
          {#if tx.type === 'INCOME' && tx.income_category}
            <div class="detail-field">
              <span class="detail-label">{t('income.category')}</span>
              <span>{tx.income_category}</span>
            </div>
          {/if}
          {#if cashHandlingLabel(tx)}
            <div class="detail-field">
              <span class="detail-label">{t('transactions.cashHandling')}</span>
              <span>{cashHandlingLabel(tx)}</span>
            </div>
          {/if}
          {#if tx.type === 'BALANCE_ADJUSTMENT' && tx.attached_transaction_ids?.length}
            <div class="detail-field full-width">
              <span class="detail-label">{t('transactions.fundsTransactions', { n: tx.attached_transaction_ids.length })}</span>
              <span>
                {#if linkedSpends.length}
                  {#each linkedSpends as s (s.id)}
                    {formatDate(s.timestamp)} · {formatType(s.type)} · {formatNumber(s.total_value)} {s.currency}{#if !isLastLinked(s)}<br />{/if}
                  {/each}
                {:else}
                  {tx.attached_transaction_ids.join(', ')}
                {/if}
              </span>
            </div>
          {/if}
          {#if tx.notes}
            <div class="detail-field full-width">
              <span class="detail-label">{t('common.notes')}</span>
              <span>{tx.notes}</span>
            </div>
          {/if}
        </div>
      </div>

      <!-- Investment Details -->
      {#if tx.type === 'INVESTMENT_BUY' || tx.type === 'INVESTMENT_SELL'}
        <div class="detail-section">
          <h4>Investment Details</h4>
          <div class="detail-grid">
            {#if tx.portfolio_asset_id}
              <div class="detail-field">
                <span class="detail-label">{t('modals.asset')}</span>
                <span>{assetNameMap[tx.portfolio_asset_id] || tx.portfolio_asset_id}</span>
              </div>
            {/if}
            {#if tx.investment_transaction_category}
              <div class="detail-field">
                <span class="detail-label">{t('modals.category')}</span>
                <Badge variant="warning">{tx.investment_transaction_category}</Badge>
              </div>
            {/if}
            {#if tx.quantity !== null && tx.quantity !== undefined}
              <div class="detail-field">
                <span class="detail-label">{t('modals.quantity')}</span>
                <span>{formatNumber(tx.quantity)}</span>
              </div>
            {/if}
            {#if tx.unit_price !== null && tx.unit_price !== undefined}
              <div class="detail-field">
                <span class="detail-label">{t('modals.unitPrice')}</span>
                <span>{formatNumber(tx.unit_price)}</span>
              </div>
            {/if}
            {#if tx.payment_currency}
              <div class="detail-field">
                <span class="detail-label">{t('modals.paymentCurrency')}</span>
                <span>{tx.payment_currency}</span>
              </div>
            {/if}
            {#if tx.fx_rate !== null && tx.fx_rate !== undefined}
              <div class="detail-field">
                <span class="detail-label">{t('modals.fxRate')}</span>
                <span>{formatNumber(tx.fx_rate)}</span>
              </div>
            {/if}
            {#if tx.settlement_date}
              <div class="detail-field">
                <span class="detail-label">{t('modals.settlementDate')}</span>
                <span>{formatDate(tx.settlement_date)}</span>
              </div>
            {/if}
            {#if tx.fiscal_exemption_id}
              <div class="detail-field">
                <span class="detail-label">{t('modals.fiscalExemption')}</span>
                <span>{tx.fiscal_exemption_id}</span>
              </div>
            {/if}
          </div>
        </div>
      {/if}

      <!-- Dividend Details -->
      {#if tx.income_category === 'dividends'}
        <div class="detail-section">
          <h4>Dividend Details</h4>
          <div class="detail-grid">
            {#if tx.portfolio_asset_id}
              <div class="detail-field">
                <span class="detail-label">{t('modals.asset')}</span>
                <span>{assetNameMap[tx.portfolio_asset_id] || tx.portfolio_asset_id}</span>
              </div>
            {/if}
            {#if tx.dividend_type}
              <div class="detail-field">
                <span class="detail-label">{t('modals.dividendType')}</span>
                <span>{tx.dividend_type}</span>
              </div>
            {/if}
            {#if tx.record_date}
              <div class="detail-field">
                <span class="detail-label">{t('modals.recordDate')}</span>
                <span>{formatDate(tx.record_date)}</span>
              </div>
            {/if}
            {#if tx.payment_date}
              <div class="detail-field">
                <span class="detail-label">{t('modals.paymentDate')}</span>
                <span>{formatDate(tx.payment_date)}</span>
              </div>
            {/if}
            {#if tx.gross_amount !== null && tx.gross_amount !== undefined}
              <div class="detail-field">
                <span class="detail-label">{t('modals.grossAmount')}</span>
                <span>{formatNumber(tx.gross_amount)}</span>
              </div>
            {/if}
            {#if tx.net_amount !== null && tx.net_amount !== undefined}
              <div class="detail-field">
                <span class="detail-label">{t('modals.netAmount')}</span>
                <span>{formatNumber(tx.net_amount)}</span>
              </div>
            {/if}
            {#if tx.dividend_currency}
              <div class="detail-field">
                <span class="detail-label">{t('modals.dividendCurrency')}</span>
                <span>{tx.dividend_currency}</span>
              </div>
            {/if}
            {#if tx.dividend_payment_currency}
              <div class="detail-field">
                <span class="detail-label">{t('modals.paymentCurrency')}</span>
                <span>{tx.dividend_payment_currency}</span>
              </div>
            {/if}
            {#if tx.dividend_fx_rate !== null && tx.dividend_fx_rate !== undefined}
              <div class="detail-field">
                <span class="detail-label">{t('modals.dividendFxRate')}</span>
                <span>{formatNumber(tx.dividend_fx_rate)}</span>
              </div>
            {/if}
          </div>
        </div>
      {/if}

      <!-- Fees -->
      {#if fees.length > 0}
        <div class="detail-section">
          <h4>Fees</h4>
          <table class="detail-table">
            <thead>
              <tr>
                <th>{t('common.type')}</th>
                <th>Nature</th>
                <th>Fixed</th>
                <th>%</th>
                <th>{t('common.currency')}</th>
                <th>{t('common.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {#each fees as fee (fee.id)}
                <tr>
                  <td>{fee.fee_type}</td>
                  <td>{fee.nature}</td>
                  <td class="num">{fee.fixed_amount !== null && fee.fixed_amount !== undefined ? formatNumber(fee.fixed_amount) : '-'}</td>
                  <td class="num">{fee.percentage !== null && fee.percentage !== undefined ? formatNumber(fee.percentage) : '-'}</td>
                  <td>{fee.currency}</td>
                  <td class="actions-cell">
                    <button class="icon-btn" aria-label="Edit fee" onclick={() => handleEditFee(fee)}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                      </svg>
                    </button>
                    <button class="icon-btn icon-btn-danger" aria-label="Delete fee" onclick={() => handleDeleteFee(fee)}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                      </svg>
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}

      <!-- Taxes -->
      {#if taxes.length > 0}
        <div class="detail-section">
          <h4>Taxes</h4>
          <table class="detail-table">
            <thead>
              <tr>
                <th>{t('common.type')}</th>
                <th>Rate</th>
                <th>{t('common.amount')}</th>
                <th>{t('common.currency')}</th>
                <th>{t('common.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {#each taxes as tax (tax.id)}
                <tr>
                  <td>{tax.tax_type}</td>
                  <td class="num">{tax.tax_rate !== null && tax.tax_rate !== undefined ? formatNumber(tax.tax_rate) : '-'}</td>
                  <td class="num">{formatNumber(tax.tax_amount)}</td>
                  <td>{tax.currency}</td>
                  <td class="actions-cell">
                    <button class="icon-btn" aria-label="Edit tax" onclick={() => handleEditTax(tax)}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                      </svg>
                    </button>
                    <button class="icon-btn icon-btn-danger" aria-label="Delete tax" onclick={() => handleDeleteTax(tax)}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                      </svg>
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}

      <!-- Action Buttons -->
      <div class="detail-actions">
        <Button variant="secondary" onclick={onclose}>{t('common.close')}</Button>
        <Button variant="primary" onclick={handleEdit}>{t('common.edit')}</Button>
        <Button variant="danger" onclick={handleDelete}>{t('common.delete')}</Button>
      </div>
    </div>
  {/if}
</Modal>

<style>
  .loading-container,
  .error-container {
    text-align: center;
    padding: var(--space-8);
  }

  .error-message {
    color: var(--color-danger);
    margin-bottom: var(--space-4);
  }

  .detail-content {
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
  }

  .detail-header {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding-bottom: var(--space-4);
    border-bottom: 1px solid var(--color-border);
  }

  .detail-date {
    font-size: var(--font-size-sm);
    color: var(--color-text-secondary);
  }

  .detail-amount {
    font-size: var(--font-size-lg);
    font-weight: var(--font-weight-semibold);
    margin-left: auto;
  }

  .detail-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .detail-section h4 {
    margin: 0;
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-primary);
  }

  .detail-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--space-4);
  }

  .detail-field {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .detail-field.full-width {
    grid-column: 1 / -1;
  }

  .detail-field .detail-label {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    font-weight: var(--font-weight-medium);
  }

  .detail-field span {
    font-size: var(--font-size-sm);
    color: var(--color-text-primary);
  }

  .detail-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
  }

  .detail-table th {
    padding: var(--space-2) var(--space-3);
    text-align: left;
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-secondary);
    background: var(--color-surface-alt);
    border-bottom: 1px solid var(--color-border);
  }

  .detail-table td {
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--color-border);
  }

  .detail-table td.num {
    text-align: right;
    font-family: var(--font-mono);
  }

  .detail-table .actions-cell {
    text-align: center;
    width: 80px;
  }

  .icon-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: var(--space-1);
    border-radius: var(--radius-md);
    color: var(--color-text-muted);
    transition: background var(--transition-fast), color var(--transition-fast);
  }

  .icon-btn:hover {
    background: var(--color-surface-hover);
    color: var(--color-text-primary);
  }

  .icon-btn-danger:hover {
    background: rgba(224, 49, 49, 0.1);
    color: var(--color-danger);
  }

  .detail-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-3);
    padding-top: var(--space-4);
    border-top: 1px solid var(--color-border);
  }

  @media (max-width: 768px) {
    .detail-grid {
      grid-template-columns: 1fr;
    }

    .detail-header {
      flex-wrap: wrap;
    }

    .detail-amount {
      margin-left: 0;
      width: 100%;
    }

    .detail-actions {
      flex-direction: column;
    }

    .detail-actions :global(button) {
      width: 100%;
    }
  }
</style>
