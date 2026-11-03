<template>
  <div class="empty-state">
    <div class="empty-state__icon">{{ icon }}</div>
    <h4 class="empty-state__title">{{ title || t('core.empty') }}</h4>
    <p v-if="description" class="empty-state__desc">{{ description }}</p>
    <slot />
  </div>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
withDefaults(
  defineProps<{
    icon?: string
    title?: string
    description?: string
  }>(),
  {
    icon: '📭',
    title: '',
    description: '',
  },
)
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 56px 24px;
  text-align: center;
  gap: 12px;
}

.empty-state__icon {
  font-size: 48px;
  line-height: 1;
}

.empty-state__title {
  margin: 0;
  color: var(--neutral-700);
}

.empty-state__desc {
  margin: 0;
  color: var(--neutral-400);
  max-width: 400px;
}
</style>

