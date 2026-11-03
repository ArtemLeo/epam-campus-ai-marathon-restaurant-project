<template>
  <div class="table-card card" :class="{ 'table-card--available': table.available }">
    <div class="table-card__header">
      <h5 class="table-card__number">{{ t('customer.tableNumber', { number: table.tableNumber || table.id }) }}</h5>
      <span class="badge" :class="table.available ? 'badge--confirmed' : 'badge--cancelled'">
        {{ t(table.available ? 'customer.available' : 'customer.occupied') }}
      </span>
    </div>
    <div class="table-card__body">
      <div class="table-card__row">
        <img src="/assets/svg/users.svg" :alt="t('customer.capacity')" class="icon-sm" />
        <span>{{ t('customer.capacityGuests', { count: table.capacity }, table.capacity) }}</span>
      </div>
      <div v-if="table.locationName" class="table-card__row">
        <img src="/assets/svg/pin.svg" :alt="t('customer.location')" class="icon-sm" />
        <span>{{ table.locationName }}</span>
      </div>
    </div>
    <div v-if="$slots.action" class="table-card__footer">
      <slot name="action" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import type { Table } from '@/services/api'

defineProps<{
  table: Table & { available?: boolean; locationName?: string }
}>()
</script>

<style scoped>
.table-card {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.table-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--neutral-100);
}

.table-card__number {
  margin: 0;
}

.table-card__body {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.table-card__row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--neutral-600);
}

.table-card__footer {
  padding: 12px 16px;
  border-top: 1px solid var(--neutral-100);
}

.icon-sm {
  width: 14px;
  height: 14px;
}
</style>

