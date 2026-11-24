<script>
  let { children } = $props();
</script>

<div class="form-actions">
  {@render children()}
</div>

<style>
  .form-actions {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: var(--space-3);
    padding-top: var(--space-2);
  }
</style>
