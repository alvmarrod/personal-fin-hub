<script>
  import { onMount } from 'svelte';
  import Card from '$lib/components/Card.svelte';
  import { analytics } from '$lib/api/analytics.js';
  import { LoadingSpinner, EmptyState } from '$lib/components/index.js';

  let loading = $state(true);
  let error = $state(null);
  let data = $state(null);

  onMount(async () => {
    try {
      data = await analytics.dashboard();
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  });
</script>

<h1 class="page-title">Dashboard</h1>

{#if loading}
  <LoadingSpinner message="Loading dashboard..." />
{:else if error}
  <Card variant="default" padding="lg">
    <p class="error-message">Failed to load dashboard: {error}</p>
  </Card>
{:else if data}
  <div class="metric-grid">
    <Card variant="metric" padding="md">
      <p class="metric-label">Portfolio Value</p>
      <p class="metric-value">{data.total_portfolio_value?.toLocaleString()}</p>
    </Card>
    <Card variant="metric" padding="md">
      <p class="metric-label">Cash Balance</p>
      <p class="metric-value">{data.cash_balance?.toLocaleString()}</p>
    </Card>
    <Card variant="metric" padding="md">
      <p class="metric-label">Total Invested</p>
      <p class="metric-value">{data.total_invested?.toLocaleString()}</p>
    </Card>
    <Card variant="metric" padding="md">
      <p class="metric-label">Total Return</p>
      <p class="metric-value" class:positive={data.total_return > 0} class:negative={data.total_return < 0}>
        {data.total_return_pct?.toFixed(2)}%
      </p>
    </Card>
  </div>
{:else}
  <EmptyState title="No data yet" message="Start by adding your first transaction." />
{/if}

<style>
  .page-title {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-bold);
    margin-bottom: var(--space-6);
  }

  .metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: var(--space-4);
    margin-bottom: var(--space-6);
  }

  .metric-label {
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    color: var(--color-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: var(--space-2);
  }

  .metric-value {
    font-size: var(--font-size-2xl);
    font-weight: var(--font-weight-bold);
    font-family: var(--font-mono);
    color: var(--color-text-primary);
  }

  .positive { color: var(--color-success); }
  .negative { color: var(--color-danger); }

  .error-message {
    color: var(--color-danger);
    font-size: var(--font-size-sm);
  }
</style>
