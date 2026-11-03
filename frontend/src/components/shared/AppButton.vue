<template>
  <button
    :type="type"
    class="button"
    :class="[`button--${variant}`, `button--${size}`, { 'button--full-width': fullWidth }]"
    :disabled="disabled || loading"
    v-bind="$attrs"
  >
    <span v-if="loading" class="btn-spinner" />
    <slot />
  </button>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    type?: 'button' | 'submit' | 'reset'
    variant?: 'primary' | 'secondary' | 'tertiary' | 'danger'
    size?: 'extra-large' | 'large' | 'small'
    disabled?: boolean
    loading?: boolean
    fullWidth?: boolean
  }>(),
  {
    type: 'button',
    variant: 'primary',
    size: 'large',
    disabled: false,
    loading: false,
    fullWidth: false,
  },
)
</script>

<style scoped>
.btn-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>

