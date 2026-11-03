<template>
  <div class="page">
    <div class="card">
      <h1>{{ t('orders.sessionExpired') }}</h1>
      <p>{{ t('orders.askNewLink') }}</p>
      <div style="margin-top: 24px;">
        <router-link to="/main" class="button button--primary button--large">
          {{ t('orders.backHome') }}
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
</script>

<style scoped>
.page {
  min-height: calc(100vh - 80px);
  display: grid;
  place-items: center;
  padding: 24px;
}

.card {
  width: min(640px, 100%);
  background: var(--neutral-0, #fff);
  border-radius: 16px;
  padding: 32px;
  text-align: center;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

h1 {
  font-size: 24px;
  font-weight: 600;
  color: var(--neutral-900, #232323);
  margin-bottom: 12px;
}

p {
  color: var(--neutral-600, #575757);
}
</style>

