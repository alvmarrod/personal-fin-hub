<script>
  import { t } from '$lib/i18n/index.svelte';
  import { debtApi } from '$lib/api/debt.js';
  import { formatAmount, formatDate, formatPercent, maskAmount } from '$lib/utils/format.svelte';
  import Modal from '../Modal.svelte';
  import Button from '../Button.svelte';
  import FormActions from '$lib/components/FormActions.svelte';
  import FormError from '$lib/components/FormError.svelte';

  let {
    open = false,
    debtId = null,
    onclose,
    onedit,
    onpayment,
    onrate,
    onsettle,
    oncancel,
    ondelete,
    onplan,
  } = $props();

  let loading = $state(false);
  let error = $state('');
  let debt = $state(null);

  let active = $derived(debt?.status === 'active');

  function money(value) {
    return maskAmount(`${formatAmount(value)} ${debt?.currency ?? ''}`, debt?.currency);
  }

  $effect(() => {
    if (!open || debtId == null) return;
    loading = true;
    error = '';
    debtApi
      .get(debtId)
      .then((data) => {
        debt = data;
      })
      .catch((e) => {
        error = e?.message || t('debt.loadFailed');
      })
      .finally(() => {
        loading = false;
      });
  });
</script>

<Modal {open} {onclose} title={t('debt.detailTitle')} size="lg">
  {#if loading}
    <p class="muted">{t('debt.loading')}</p>
  {:else if error}
    <FormError message={error} />
  {:else if debt}
    <div class="detail">
      <div class="head">
        <div>
          <h3>{debt.counterparty_name}</h3>
          <p class="muted">{debt.description ?? ''}</p>
        </div>
        <span class="badge badge-{debt.direction}">
          {debt.direction === 'payable' ? t('debt.iOwe') : t('debt.owedToMe')}
        </span>
      </div>

      <div class="grid">
        <div><span class="label">{t('debt.principal')}</span><span class="value">{money(debt.principal)}</span></div>
        <div><span class="label">{t('debt.outstanding')}</span><span class="value">{money(debt.outstanding_principal)}</span></div>
        <div><span class="label">{t('debt.accrued')}</span><span class="value">{money(debt.accrued_interest)}</span></div>
        <div><span class="label">{t('debt.totalDue')}</span><span class="value">{money(debt.total_due)}</span></div>
        <div><span class="label">{t('debt.currentRate')}</span><span class="value">{formatPercent(debt.current_rate)}</span></div>
        <div><span class="label">{t('debt.startDate')}</span><span class="value">{formatDate(debt.start_date)}</span></div>
        <div><span class="label">{t('debt.maturityDate')}</span><span class="value">{debt.maturity_date ? formatDate(debt.maturity_date) : '—'}</span></div>
        <div><span class="label">{t('debt.progress')}</span><span class="value">{formatPercent(debt.progress_pct)}</span></div>
      </div>

      <div class="bar"><div class="bar-fill" style="width: {Math.min(debt.progress_pct, 100)}%"></div></div>

      <FormActions>
        {#if active}
          <Button size="sm" onclick={() => onpayment?.(debt)}>{t('debt.addPayment')}</Button>
          <Button size="sm" variant="secondary" onclick={() => onrate?.(debt)}>{t('debt.changeRate')}</Button>
          <Button size="sm" variant="secondary" onclick={() => onsettle?.(debt)}>{t('debt.settle')}</Button>
          <Button size="sm" variant="secondary" onclick={() => onplan?.(debt)}>{t('debt.planTitle')}</Button>
          <Button size="sm" variant="secondary" onclick={() => oncancel?.(debt)}>{t('debt.cancel')}</Button>
        {/if}
        <Button size="sm" variant="secondary" onclick={() => onedit?.(debt)}>{t('common.edit')}</Button>
        <Button size="sm" variant="danger" onclick={() => ondelete?.(debt)}>{t('common.delete')}</Button>
      </FormActions>

      <section>
        <h4>{t('debt.ratesTitle')}</h4>
        <table>
          <thead><tr><th>{t('debt.rateDate')}</th><th class="num">{t('debt.annualRate')}</th></tr></thead>
          <tbody>
            {#each debt.rates as rate (rate.id)}
              <tr><td>{formatDate(rate.effective_from)}</td><td class="num">{formatPercent(rate.annual_rate)}</td></tr>
            {/each}
          </tbody>
        </table>
      </section>

      <section>
        <h4>{t('debt.paymentsTitle')}</h4>
        {#if debt.payments.length === 0}
          <p class="muted">{t('debt.noPayments')}</p>
        {:else}
          <table>
            <thead>
              <tr>
                <th>{t('debt.paymentDate')}</th>
                <th class="num">{t('common.amount')}</th>
                <th class="num">{t('debt.principalPart')}</th>
                <th class="num">{t('debt.interestPart')}</th>
                <th class="num">{t('debt.fees')}</th>
                <th class="num">{t('debt.insurance')}</th>
                <th class="num">{t('debt.other')}</th>
              </tr>
            </thead>
            <tbody>
              {#each debt.payments as payment (payment.id)}
                <tr>
                  <td>{formatDate(payment.paid_at)}</td>
                  <td class="num">{money(payment.amount)}</td>
                  <td class="num">{money(payment.principal_amount)}</td>
                  <td class="num">{money(payment.interest_amount)}</td>
                  <td class="num">{money(payment.fees_amount)}</td>
                  <td class="num">{money(payment.insurance_amount)}</td>
                  <td class="num">{money(payment.other_amount)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </section>

      <section>
        <h4>{t('debt.planSection')}</h4>
        {#if debt.plan.length === 0}
          <p class="muted">{t('debt.noPlan')}</p>
        {:else}
          <table>
            <thead>
              <tr>
                <th>{t('debt.planDue')}</th>
                <th class="num">{t('common.amount')}</th>
                <th class="num">{t('debt.principalPart')}</th>
                <th class="num">{t('debt.interestPart')}</th>
              </tr>
            </thead>
            <tbody>
              {#each debt.plan.slice(0, 24) as entry (entry.id)}
                <tr>
                  <td>{formatDate(entry.due_date)}</td>
                  <td class="num">{money(entry.payment_amount)}</td>
                  <td class="num">{money(entry.principal_amount)}</td>
                  <td class="num">{money(entry.interest_amount)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </section>
    </div>
  {/if}
</Modal>

<style>
  .detail {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }
  .head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3);
  }
  .head h3 {
    margin: 0 0 var(--space-1);
    font-size: var(--font-size-lg);
  }
  .muted {
    margin: 0;
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--space-3);
  }
  .grid > div {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .label {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }
  .value {
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-semibold);
  }
  .bar {
    height: 6px;
    border-radius: var(--radius-full);
    background: var(--color-surface-alt);
    overflow: hidden;
  }
  .bar-fill {
    height: 100%;
    background: var(--color-primary);
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
  section h4 {
    margin: 0 0 var(--space-2);
    font-size: var(--font-size-sm);
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-size-sm);
  }
  th,
  td {
    padding: var(--space-1) var(--space-2);
    border-bottom: 1px solid var(--color-border);
    text-align: left;
  }
  th {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }
  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  @media (max-width: 900px) {
    .grid {
      grid-template-columns: 1fr 1fr;
    }
  }
</style>
