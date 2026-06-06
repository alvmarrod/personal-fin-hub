<script>
  import Modal from '../Modal.svelte';
  import Badge from '../Badge.svelte';
  import Button from '../Button.svelte';
  import { api } from '../../api/client.js';

  let { open = false, transaction = null, onclose, onedit, ondelete } = $props();

  let loading = $state(false);
  let error = $state('');
  let tx = $state(null);
  let fees = $state([]);
  let taxes = $state([]);

  const TYPE_LABELS = {
    'MONEY_IN': 'Income',
    'MONEY_OUT': 'Expense',
    'INVESTMENT_BUY': 'Investment Buy',
    'INVESTMENT_SELL': 'Investment Sell',
    'DIVIDEND': 'Dividend',
    'INTEREST': 'Interest',
  };

  const TYPE_VARIANTS = {
    'MONEY_IN': 'success',
    'MONEY_OUT': 'danger',
    'INVESTMENT_BUY': 'primary',
    'INVESTMENT_SELL': 'info',
    'DIVIDEND': 'warning',
    'INTEREST': 'success',
  };

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
    } catch (e) {
      error = e.message || 'Failed to load transaction details';
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

<Modal {open} {onclose} title="Transaction Details" size="lg">
  {#if loading}
    <div class="loading-container">
      <p>Loading transaction details...</p>
    </div>
  {:else if error}
    <div class="error-container">
      <p class="error-message">{error}</p>
      <Button variant="secondary" size="sm" onclick={loadTransaction}>Retry</Button>
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
            <label>Entity</label>
            <span>{tx.entity_id}</span>
          </div>
          <div class="detail-field">
            <label>Currency</label>
            <span>{tx.currency}</span>
          </div>
          {#if tx.notes}
            <div class="detail-field full-width">
              <label>Notes</label>
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
                <label>Portfolio Asset</label>
                <span>{tx.portfolio_asset_id}</span>
              </div>
            {/if}
            {#if tx.transaction_category}
              <div class="detail-field">
                <label>Category</label>
                <Badge variant="warning">{tx.transaction_category}</Badge>
              </div>
            {/if}
            {#if tx.quantity !== null && tx.quantity !== undefined}
              <div class="detail-field">
                <label>Quantity</label>
                <span>{formatNumber(tx.quantity)}</span>
              </div>
            {/if}
            {#if tx.unit_price !== null && tx.unit_price !== undefined}
              <div class="detail-field">
                <label>Unit Price</label>
                <span>{formatNumber(tx.unit_price)}</span>
              </div>
            {/if}
            {#if tx.payment_currency}
              <div class="detail-field">
                <label>Payment Currency</label>
                <span>{tx.payment_currency}</span>
              </div>
            {/if}
            {#if tx.fx_rate !== null && tx.fx_rate !== undefined}
              <div class="detail-field">
                <label>FX Rate</label>
                <span>{formatNumber(tx.fx_rate)}</span>
              </div>
            {/if}
            {#if tx.settlement_date}
              <div class="detail-field">
                <label>Settlement Date</label>
                <span>{formatDate(tx.settlement_date)}</span>
              </div>
            {/if}
            {#if tx.fiscal_exemption_id}
              <div class="detail-field">
                <label>Fiscal Exemption</label>
                <span>{tx.fiscal_exemption_id}</span>
              </div>
            {/if}
          </div>
        </div>
      {/if}

      <!-- Dividend Details -->
      {#if tx.type === 'DIVIDEND'}
        <div class="detail-section">
          <h4>Dividend Details</h4>
          <div class="detail-grid">
            {#if tx.portfolio_asset_id}
              <div class="detail-field">
                <label>Portfolio Asset</label>
                <span>{tx.portfolio_asset_id}</span>
              </div>
            {/if}
            {#if tx.dividend_type}
              <div class="detail-field">
                <label>Dividend Type</label>
                <span>{tx.dividend_type}</span>
              </div>
            {/if}
            {#if tx.record_date}
              <div class="detail-field">
                <label>Record Date</label>
                <span>{formatDate(tx.record_date)}</span>
              </div>
            {/if}
            {#if tx.payment_date}
              <div class="detail-field">
                <label>Payment Date</label>
                <span>{formatDate(tx.payment_date)}</span>
              </div>
            {/if}
            {#if tx.gross_amount !== null && tx.gross_amount !== undefined}
              <div class="detail-field">
                <label>Gross Amount</label>
                <span>{formatNumber(tx.gross_amount)}</span>
              </div>
            {/if}
            {#if tx.net_amount !== null && tx.net_amount !== undefined}
              <div class="detail-field">
                <label>Net Amount</label>
                <span>{formatNumber(tx.net_amount)}</span>
              </div>
            {/if}
            {#if tx.dividend_currency}
              <div class="detail-field">
                <label>Dividend Currency</label>
                <span>{tx.dividend_currency}</span>
              </div>
            {/if}
            {#if tx.dividend_payment_currency}
              <div class="detail-field">
                <label>Payment Currency</label>
                <span>{tx.dividend_payment_currency}</span>
              </div>
            {/if}
            {#if tx.dividend_fx_rate !== null && tx.dividend_fx_rate !== undefined}
              <div class="detail-field">
                <label>Dividend FX Rate</label>
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
                <th>Type</th>
                <th>Nature</th>
                <th>Fixed</th>
                <th>%</th>
                <th>Currency</th>
                <th>Actions</th>
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
                <th>Type</th>
                <th>Rate</th>
                <th>Amount</th>
                <th>Currency</th>
                <th>Actions</th>
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
        <Button variant="secondary" onclick={onclose}>Close</Button>
        <Button variant="primary" onclick={handleEdit}>Edit Transaction</Button>
        <Button variant="danger" onclick={handleDelete}>Delete Transaction</Button>
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

  .detail-field label {
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

  .detail-table th.num {
    text-align: right;
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

    .detail-actions button {
      width: 100%;
    }
  }
</style>
