<script>
  import DateInput from '$lib/components/DateInput.svelte';

  let { initial = '' } = $props();
  let value = $state(initial);
</script>

<DateInput bind:value />
<span data-testid="value">{value}</span>
