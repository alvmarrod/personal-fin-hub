<script>
  import Modal from '../Modal.svelte';
  import FormField from '../FormField.svelte';
  import Select from '../Select.svelte';
  import TextInput from '../TextInput.svelte';
  import NumberInput from '../NumberInput.svelte';
  import Button from '../Button.svelte';
  import { t } from '$lib/i18n/index.svelte';
  import { crud, currenciesApi } from '../../api/analytics.js';
  import { api } from '../../api/client.js';

  let { open = false, transaction = null, onclose, onsuccess } = $props();

  let submitting = $state(false);
  let error = $state('');

  // Form state
  let txType = $state('INCOME');
  let timestamp = $state('');
  let entityId = $state('');
  let currency = $state('EUR');
  let totalValue = $state('');
  let notes = $state('');
  let incomeCategory = $state('');
  let cashHandling = $state('');
  let autoCashHandling = $state(null);

  // Investment fields
  let portfolioAssetId = $state('');
  let quantity = $state('');
  let unitPrice = $state('');
  let investmentTransactionCategory = $state('NORMAL');
  let paymentCurrency = $state('');
  let fxRate = $state('');
  let settlementDate = $state('');
  let fiscalExemptionId = $state('');

  // Dividend fields
  let dividendType = $state('regular');
  let recordDate = $state('');
  let paymentDate = $state('');
  let grossAmount = $state('');
  let netAmount = $state('');
  let dividendCurrency = $state('');
  let dividendPaymentCurrency = $state('');
  let dividendFxRate = $state('');

  // Fees & Taxes (for investments)
  let fees = $state([]);
  let taxes = $state([]);

  // Options
  let entities = $state([]);
  let currencies = $state([]);
  let portfolioAssets = $state([]);
  let fiscalExemptions = $state([]);
  let loadingOptions = $state(true);
  let loadingTransaction = $state(true);

  let TYPE_OPTIONS = $derived([
    { value: 'INCOME', label: t('transactions.typeIncome') },
    { value: 'MONEY_OUT', label: t('transactions.typeExpense') },
    { value: 'INVESTMENT_BUY', label: t('transactions.typeBuy') },
    { value: 'INVESTMENT_SELL', label: t('transactions.typeSell') },
    { value: 'TRANSFER_IN', label: t('transactions.typeTransferIn') },
    { value: 'TRANSFER_OUT', label: t('transactions.typeTransferOut') },
  ]);

  const CATEGORY_OPTIONS = [
    { value: 'NORMAL', label: 'Normal' },
    { value: 'DCA', label: 'DCA' },
    { value: 'REBALANCE', label: 'Rebalance' },
  ];

  let incomeCategoryOptions = $derived([
    { value: '', label: 'None' },
    { value: 'salary', label: t('income.category.salary') },
    { value: 'other', label: t('income.category.other') },
    { value: 'dividends', label: t('income.category.dividends') },
    { value: 'interest', label: t('income.category.interest') },
    { value: 'cashback', label: t('income.category.cashback') },
  ]);

  const DIVIDEND_TYPE_OPTIONS = [
    { value: 'regular', label: 'Regular' },
    { value: 'special', label: 'Special' },
    { value: 'qualified', label: 'Qualified' },
  ];

  const FEE_TYPE_OPTIONS = [
    { value: 'BROKER', label: 'Broker' },
    { value: 'FX', label: 'FX' },
    { value: 'PLATFORM', label: 'Platform' },
    { value: 'OTHER', label: 'Other' },
  ];

  const FEE_NATURE_OPTIONS = [
    { value: 'FIXED', label: 'Fixed' },
    { value: 'PERCENTAGE', label: 'Percentage' },
    { value: 'BOTH', label: 'Both' },
    { value: 'MIN', label: 'Min' },
  ];

  // Computed properties
  let isInvestmentType = $derived(['INVESTMENT_BUY', 'INVESTMENT_SELL'].includes(txType));
  let isDividendType = $derived(txType === 'INCOME' && incomeCategory === 'dividends');
  let isTransferType = $derived(['TRANSFER', 'TRANSFER_IN', 'TRANSFER_OUT'].includes(txType));
  let isIncomeType = $derived(txType === 'INCOME');
  let isSpendType = $derived(['MONEY_OUT', 'INVESTMENT_BUY', 'TRANSFER_OUT'].includes(txType));

  let cashHandlingOptions = $derived([
    {
      value: '',
      label:
        autoCashHandling === 'inject'
          ? t('transactions.cashHandlingAutoInject')
          : autoCashHandling === 'debit'
            ? t('transactions.cashHandlingAutoDebit')
            : t('transactions.cashHandlingAuto'),
    },
    { value: 'inject', label: t('transactions.cashHandlingInject') },
    { value: 'debit', label: t('transactions.cashHandlingDebit') },
  ]);

  // Entity options
  let entityOptions = $derived([
    { value: '', label: 'Select entity...' },
    ...entities.map(e => ({ value: String(e.id), label: e.name }))
  ]);

  // Currency options
  let currencyOptions = $derived([
    { value: '', label: 'Select currency...' },
    ...currencies.map(c => ({ value: c, label: c }))
  ]);

  // Portfolio asset options
  let assetOptions = $derived([
    { value: '', label: 'Select asset...' },
    ...portfolioAssets.map(a => ({
      value: String(a.id),
      label: `${a.market_code} (${a.name || a.market_code})`
    }))
  ]);

  // Fiscal exemption options
  let exemptionOptions = $derived([
    { value: '', label: 'None' },
    ...fiscalExemptions.map(e => ({ value: String(e.id), label: `${e.exemption_type} - ${e.description || 'No description'}` }))
  ]);

  // Load options and transaction data when modal opens
  $effect(() => {
    if (open && transaction) {
      loadOptions();
      loadTransaction();
    }
  });

  async function loadOptions() {
    loadingOptions = true;
    try {
      const [entityList, currencyList, assetList, exemptionList] = await Promise.all([
        crud.entities.getList(),
        currenciesApi.getList(),
        crud.portfolioAssets.getList(),
        crud.fiscalExemptions.getList(),
      ]);
      entities = entityList;
      currencies = currencyList;
      portfolioAssets = assetList;
      fiscalExemptions = exemptionList;
    } catch (e) {
      error = t('common.errorPrefix', { resource: 'options' });
    } finally {
      loadingOptions = false;
    }
  }

  async function loadTransaction() {
    if (!transaction) return;
    loadingTransaction = true;
    try {
      // Load full transaction details if needed
      const tx = transaction;

      txType = tx.type;
      timestamp = tx.timestamp ? tx.timestamp.split('T')[0] : '';
      entityId = String(tx.entity_id ?? '');
      currency = tx.currency || '';
      totalValue = tx.total_value?.toString() || '';
      notes = tx.notes || '';
      incomeCategory = tx.income_category || '';
      cashHandling = tx.cash_handling || '';
      autoCashHandling = tx.cash_handling_effective || null;

      // Normalize legacy income types (DIVIDEND/INTEREST) into INCOME + category
      if (tx.type === 'DIVIDEND') {
        txType = 'INCOME';
        incomeCategory = tx.income_category || 'dividends';
      } else if (tx.type === 'INTEREST') {
        txType = 'INCOME';
        incomeCategory = tx.income_category || 'interest';
      }

      // Investment fields
      portfolioAssetId = tx.portfolio_asset_id?.toString() || '';
      quantity = tx.quantity?.toString() || '';
      unitPrice = tx.unit_price?.toString() || '';
      investmentTransactionCategory = tx.investment_transaction_category || 'NORMAL';
      paymentCurrency = tx.payment_currency || '';
      fxRate = tx.fx_rate?.toString() || '';
      settlementDate = tx.settlement_date ? tx.settlement_date.split('T')[0] : '';
      fiscalExemptionId = tx.fiscal_exemption_id?.toString() || '';

      // Dividend fields
      dividendType = tx.dividend_type || 'regular';
      recordDate = tx.record_date ? tx.record_date.split('T')[0] : '';
      paymentDate = tx.payment_date ? tx.payment_date.split('T')[0] : '';
      grossAmount = tx.gross_amount?.toString() || '';
      netAmount = tx.net_amount?.toString() || '';
      dividendCurrency = tx.dividend_currency || '';
      dividendPaymentCurrency = tx.dividend_payment_currency || '';
      dividendFxRate = tx.dividend_fx_rate?.toString() || '';

      try {
        const full = await api.get(`/transactions/${tx.id}/full`);
        fees = (full.fees || []).map(f => ({
          fee_type: f.fee_type,
          nature: f.nature,
          fixed_amount: String(f.fixed_amount ?? ''),
          percentage: String(f.percentage ?? ''),
          currency: f.currency || currency,
        }));
        taxes = (full.taxes || []).map(t => ({
          tax_type: t.tax_type,
          tax_rate: t.tax_rate != null ? String(t.tax_rate) : '',
          tax_amount: String(t.tax_amount ?? ''),
          currency: t.currency || currency,
        }));
      } catch {
        fees = [];
        taxes = [];
      }

    } catch (e) {
      error = t('common.errorPrefix', { resource: 'transaction details' });
    } finally {
      loadingTransaction = false;
    }
  }

  // Fee management
  function addFee() {
    fees = [...fees, {
      fee_type: 'BROKER',
      nature: 'FIXED',
      fixed_amount: '',
      percentage: '',
      currency: currency,
    }];
  }

  function removeFee(index) {
    fees = fees.filter((_, i) => i !== index);
  }

  function updateFee(index, field, value) {
    const newFees = [...fees];
    newFees[index] = { ...newFees[index], [field]: value };
    fees = newFees;
  }

  // Tax management
  function addTax() {
    taxes = [...taxes, {
      tax_type: '',
      tax_rate: '',
      tax_amount: '',
      currency: currency,
    }];
  }

  function removeTax(index) {
    taxes = taxes.filter((_, i) => i !== index);
  }

  function updateTax(index, field, value) {
    const newTaxes = [...taxes];
    newTaxes[index] = { ...newTaxes[index], [field]: value };
    taxes = newTaxes;
  }

  // Form validation
  function validate() {
    if (!timestamp) return 'Date is required';
    if (!entityId) return 'Entity is required';
    if (!currency) return 'Currency is required';
    if (!totalValue && txType !== 'INVESTMENT_BUY' && txType !== 'INVESTMENT_SELL') {
      return 'Amount is required';
    }
    if (isInvestmentType && !portfolioAssetId) return 'Portfolio asset is required';
    if (isDividendType && !portfolioAssetId) return 'Portfolio asset is required for dividends';
    if (isInvestmentType) {
      const filled = [!!totalValue, !!quantity, !!unitPrice].filter(Boolean).length;
      if (filled < 2) return 'Fill at least 2 of: Amount, Quantity, Unit Price';
    }
    return null;
  }

  async function handleSubmit() {
    const validationError = validate();
    if (validationError) {
      error = validationError;
      return;
    }

    submitting = true;
    error = '';

    try {
      const txData = {
        timestamp: new Date(timestamp).toISOString(),
        type: txType,
        entity_id: parseInt(entityId),
        currency: currency,
        total_value: totalValue ? parseFloat(totalValue) : null,
        notes: notes || null,
      };

      // Add income category for income types
      if (isIncomeType) {
        txData.income_category = incomeCategory || null;
      }

      // Cash handling: always sent for spends (null = back to Auto)
      if (isSpendType) {
        txData.cash_handling = cashHandling || null;
      }

      // Add investment fields
      if (isInvestmentType) {
        txData.portfolio_asset_id = parseInt(portfolioAssetId);
        txData.quantity = parseFloat(quantity);
        txData.unit_price = parseFloat(unitPrice);
        txData.investment_transaction_category = investmentTransactionCategory;
        if (paymentCurrency) txData.payment_currency = paymentCurrency;
        if (fxRate) txData.fx_rate = parseFloat(fxRate);
        if (settlementDate) txData.settlement_date = settlementDate;
        if (fiscalExemptionId) txData.fiscal_exemption_id = parseInt(fiscalExemptionId);
      }

      // Add dividend fields
      if (isDividendType) {
        txData.portfolio_asset_id = parseInt(portfolioAssetId);
        txData.dividend_type = dividendType;
        if (recordDate) txData.record_date = recordDate;
        if (paymentDate) txData.payment_date = paymentDate;
        if (grossAmount) txData.gross_amount = parseFloat(grossAmount);
        if (netAmount) txData.net_amount = parseFloat(netAmount);
        if (dividendCurrency) txData.dividend_currency = dividendCurrency;
        if (dividendPaymentCurrency) txData.dividend_payment_currency = dividendPaymentCurrency;
        if (dividendFxRate) txData.dividend_fx_rate = parseFloat(dividendFxRate);
      }

      if (isInvestmentType) {
        const fullTxData = {
          transaction: txData,
          fees: fees.map(f => ({
            fee_type: f.fee_type,
            nature: f.nature,
            fixed_amount: parseFloat(f.fixed_amount) || 0,
            percentage: parseFloat(f.percentage) || 0,
            currency: f.currency,
          })),
          taxes: taxes.map(t => ({
            tax_type: t.tax_type,
            tax_rate: t.tax_rate ? parseFloat(t.tax_rate) : null,
            tax_amount: parseFloat(t.tax_amount),
            currency: t.currency,
          })),
        };
        await api.put(`/transactions/${transaction.id}/full`, fullTxData);
      } else {
        await crud.transactions.update(transaction.id, txData);
      }

      onsuccess?.();
      onclose?.();
    } catch (e) {
      error = e.message || t('modals.updateFailed');
    } finally {
      submitting = false;
    }
  }

  function resetForm() {
    txType = 'INCOME';
    timestamp = '';
    entityId = '';
    currency = 'EUR';
    totalValue = '';
    notes = '';
    incomeCategory = '';
    cashHandling = '';
    autoCashHandling = null;
    portfolioAssetId = '';
    quantity = '';
    unitPrice = '';
    investmentTransactionCategory = 'NORMAL';
    paymentCurrency = '';
    fxRate = '';
    settlementDate = '';
    fiscalExemptionId = '';
    dividendType = 'regular';
    recordDate = '';
    paymentDate = '';
    grossAmount = '';
    netAmount = '';
    dividendCurrency = '';
    dividendPaymentCurrency = '';
    dividendFxRate = '';
    fees = [];
    taxes = [];
    error = '';
  }
</script>

<Modal {open} {onclose} title={t('modals.editTransaction')} size="lg">
  {#if loadingOptions || loadingTransaction}
    <p class="loading-text">{t('common.loading')}</p>
  {:else}
    <div class="form">
      <!-- Type Selector -->
      <FormField label={t('common.type')} required>
        <Select bind:value={txType} options={TYPE_OPTIONS} disabled={isTransferType} />
        {#if isTransferType}
          <p class="field-hint">{t('transactions.transferLegHint')}</p>
        {/if}
      </FormField>

      <!-- Common Fields -->
      <div class="form-row">
        <FormField label={t('modals.date')} required>
          <TextInput type="date" bind:value={timestamp} />
        </FormField>
        <FormField label={t('modals.entity')} required>
          <Select bind:value={entityId} options={entityOptions} />
        </FormField>
      </div>

      <div class="form-row">
        <FormField label={t('common.currency')} required>
          <Select bind:value={currency} options={currencyOptions} />
        </FormField>
        <FormField label={t('common.amount')} required={txType !== 'INVESTMENT_BUY' && txType !== 'INVESTMENT_SELL'}>
          <NumberInput bind:value={totalValue} step="0.01" placeholder={isInvestmentType ? 'Auto if quantity & price set' : 'Enter amount'} />
        </FormField>
      </div>

      <!-- Cash Handling -->
      {#if isSpendType}
        <FormField label={t('transactions.cashHandling')}>
          <Select bind:value={cashHandling} options={cashHandlingOptions} />
          {#if cashHandling}
            <p class="field-hint field-hint-warning">{t('transactions.cashHandlingWarning')}</p>
          {/if}
        </FormField>
      {/if}

      <!-- Income Category -->
      {#if isIncomeType}
        <FormField label={t('income.category')}>
          <Select bind:value={incomeCategory} options={incomeCategoryOptions} />
        </FormField>
      {/if}

      <!-- Investment Fields -->
      {#if isInvestmentType}
        <div class="section-divider">Investment Details</div>

        <div class="form-row">
          <FormField label={t('modals.asset')} required>
            <Select bind:value={portfolioAssetId} options={assetOptions} />
          </FormField>
          <FormField label={t('modals.category')}>
            <Select bind:value={investmentTransactionCategory} options={CATEGORY_OPTIONS} />
          </FormField>
        </div>

        <div class="form-row">
          <FormField label={t('modals.quantity')}>
            <NumberInput bind:value={quantity} step="0.0001" placeholder="Auto if amount & price set" />
          </FormField>
          <FormField label={t('modals.unitPrice')}>
            <NumberInput bind:value={unitPrice} step="0.01" placeholder="Auto if amount & qty set" />
          </FormField>
        </div>

        <div class="form-row">
          <FormField label="Payment Currency">
            <Select bind:value={paymentCurrency} options={currencyOptions} placeholder="Same as currency" />
          </FormField>
          <FormField label="FX Rate">
            <NumberInput bind:value={fxRate} step="0.0001" placeholder="Auto" />
          </FormField>
        </div>

        <div class="form-row">
          <FormField label="Settlement Date">
            <TextInput type="date" bind:value={settlementDate} />
          </FormField>
          <FormField label="Fiscal Exemption">
            <Select bind:value={fiscalExemptionId} options={exemptionOptions} />
          </FormField>
        </div>

        <!-- Fees Section -->
        <div class="fees-section">
          <div class="section-header">
            <h4>Fees</h4>
            <Button variant="ghost" size="sm" onclick={addFee}>+ Add Fee</Button>
          </div>

          {#each fees as fee, i (i)}
            <div class="fee-row">
              <FormField label={t('common.type')}>
                <Select value={fee.fee_type} options={FEE_TYPE_OPTIONS} onchange={(e) => updateFee(i, 'fee_type', e.target.value)} />
              </FormField>
              <FormField label="Nature">
                <Select value={fee.nature} options={FEE_NATURE_OPTIONS} onchange={(e) => updateFee(i, 'nature', e.target.value)} />
              </FormField>
              <FormField label="Fixed Amount">
                <NumberInput value={fee.fixed_amount} step="0.01" placeholder="0.00" oninput={(e) => updateFee(i, 'fixed_amount', e.target.value)} />
              </FormField>
              <FormField label="Percentage">
                <NumberInput value={fee.percentage} step="0.01" placeholder="0.00" oninput={(e) => updateFee(i, 'percentage', e.target.value)} />
              </FormField>
              <FormField label={t('common.currency')}>
                <Select value={fee.currency} options={currencyOptions} onchange={(e) => updateFee(i, 'currency', e.target.value)} />
              </FormField>
              <button class="icon-btn icon-btn-danger" onclick={() => removeFee(i)} title={t('modals.removeFee')} aria-label={t('modals.removeFee')}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
              </button>
            </div>
          {/each}
        </div>

        <!-- Taxes Section -->
        <div class="taxes-section">
          <div class="section-header">
            <h4>Taxes</h4>
            <Button variant="ghost" size="sm" onclick={addTax}>+ Add Tax</Button>
          </div>

          {#each taxes as tax, i (i)}
            <div class="tax-row">
              <FormField label={t('common.type')}>
                <TextInput value={tax.tax_type} placeholder="WITHHOLDING, STAMP_DUTY, etc." oninput={(e) => updateTax(i, 'tax_type', e.target.value)} />
              </FormField>
              <FormField label="Tax Rate (%)">
                <NumberInput value={tax.tax_rate} step="0.01" placeholder="0.00" oninput={(e) => updateTax(i, 'tax_rate', e.target.value)} />
              </FormField>
              <FormField label="Tax Amount">
                <NumberInput value={tax.tax_amount} step="0.01" placeholder="0.00" oninput={(e) => updateTax(i, 'tax_amount', e.target.value)} />
              </FormField>
              <FormField label={t('common.currency')}>
                <Select value={tax.currency} options={currencyOptions} onchange={(e) => updateTax(i, 'currency', e.target.value)} />
              </FormField>
              <button class="icon-btn icon-btn-danger" onclick={() => removeTax(i)} title={t('modals.removeTax')} aria-label={t('modals.removeTax')}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
              </button>
            </div>
          {/each}
        </div>
      {/if}

      <!-- Dividend Fields -->
      {#if isDividendType}
        <div class="section-divider">Dividend Details</div>

        <div class="form-row">
          <FormField label={t('modals.asset')} required>
            <Select bind:value={portfolioAssetId} options={assetOptions} />
          </FormField>
          <FormField label="Dividend Type">
            <Select bind:value={dividendType} options={DIVIDEND_TYPE_OPTIONS} />
          </FormField>
        </div>

        <div class="form-row">
          <FormField label="Record Date">
            <TextInput type="date" bind:value={recordDate} />
          </FormField>
          <FormField label="Payment Date">
            <TextInput type="date" bind:value={paymentDate} />
          </FormField>
        </div>

        <div class="form-row">
          <FormField label="Gross Amount">
            <NumberInput bind:value={grossAmount} step="0.01" />
          </FormField>
          <FormField label="Net Amount">
            <NumberInput bind:value={netAmount} step="0.01" />
          </FormField>
        </div>

        <div class="form-row">
          <FormField label="Dividend Currency">
            <Select bind:value={dividendCurrency} options={currencyOptions} placeholder="Same as currency" />
          </FormField>
          <FormField label="Payment Currency">
            <Select bind:value={dividendPaymentCurrency} options={currencyOptions} placeholder="Same as currency" />
          </FormField>
        </div>

        <div class="form-row">
          <FormField label="Dividend FX Rate">
            <NumberInput bind:value={dividendFxRate} step="0.0001" placeholder="Auto" />
          </FormField>
        </div>
      {/if}

      <!-- Notes -->
      <FormField label={t('common.notes')}>
        <TextInput bind:value={notes} placeholder={t('modals.notesPlaceholder')} />
      </FormField>

      <!-- Error Display -->
      {#if error}
        <p class="form-error">{error}</p>
      {/if}

      <!-- Actions -->
      <div class="form-actions">
        <Button variant="secondary" onclick={onclose} disabled={submitting}>{t('common.cancel')}</Button>
        <Button variant="primary" onclick={handleSubmit} disabled={submitting}>
          {submitting ? t('common.saving') : t('common.save')}
        </Button>
      </div>
    </div>
  {/if}
</Modal>

<style>
  .loading-text {
    text-align: center;
    padding: var(--space-8);
    color: var(--color-text-secondary);
  }

  .form {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-4);
  }

  .section-divider {
    border-top: 1px solid var(--color-border);
    padding-top: var(--space-4);
    margin-top: var(--space-2);
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-3);
  }

  .section-header h4 {
    margin: 0;
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-semibold);
    color: var(--color-text-primary);
  }

  .fees-section, .taxes-section {
    margin-top: var(--space-4);
    padding: var(--space-3);
    background: var(--color-surface-alt);
    border-radius: var(--radius-md);
  }

  .fee-row, .tax-row {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr 1fr 1fr auto;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
    align-items: end;
  }

  .fee-row:last-child, .tax-row:last-child {
    margin-bottom: 0;
  }

  .icon-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: var(--space-1);
    border-radius: var(--radius-md);
    color: var(--color-text-muted);
    transition: background var(--transition-fast), color var(--transition-fast);
    margin-bottom: var(--space-2);
  }

  .icon-btn:hover {
    background: var(--color-surface-hover);
    color: var(--color-text-primary);
  }

  .icon-btn-danger:hover {
    background: rgba(224, 49, 49, 0.1);
    color: var(--color-danger);
  }

  .form-error {
    font-size: var(--font-size-sm);
    color: var(--color-danger);
    margin: 0;
  }

  .field-hint {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    margin: var(--space-1) 0 0;
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-3);
    padding-top: var(--space-2);
  }
</style>
