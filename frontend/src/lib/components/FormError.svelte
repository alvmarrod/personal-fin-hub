<script>
  let { message = '' } = $props();
</script>

{#if message}
  <p class="form-error">{message}</p>
{/if}

<style>
  .form-error {
    margin: 0;
    font-size: var(--font-size-sm);
    color: var(--color-danger);
  }
</style>
