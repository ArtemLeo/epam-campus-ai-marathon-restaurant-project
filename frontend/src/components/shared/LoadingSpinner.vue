<template>
  <div class="loading-spinner" :class="`loading-spinner--${size}`">
    <div class="spinner" />
    <p v-if="text" class="loading-spinner__text">{{ text }}</p>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    size?: 'sm' | 'md' | 'lg'
    text?: string
  }>(),
  {
    size: 'md',
    text: '',
  },
)
</script>

<style scoped>
.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 24px;
}

.spinner {
  border: 3px solid var(--neutral-200);
  border-top-color: var(--green-400);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

.loading-spinner--sm .spinner { width: 24px; height: 24px; }
.loading-spinner--md .spinner { width: 40px; height: 40px; }
.loading-spinner--lg .spinner { width: 56px; height: 56px; }

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-spinner__text {
  margin: 0;
  color: var(--neutral-400);
  font-size: 14px;
}
</style>

