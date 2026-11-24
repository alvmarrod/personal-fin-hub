<script>
  let { children } = $props();
</script>

<div class="modal-form">
  {@render children()}
</div>

<style>
  .modal-form {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }
</style>
