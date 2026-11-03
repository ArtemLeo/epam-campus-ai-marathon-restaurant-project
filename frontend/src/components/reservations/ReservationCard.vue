<template>
  <div class="reservation-card card">
    <div class="reservation-card__header">
      <div>
        <h5 class="reservation-card__location">{{ reservation.restaurantName || t('customer.restaurant') }}</h5>
        <p class="reservation-card__meta text-muted">
          <template v-if="reservation.tableName">{{ t('customer.tableNumber', { number: reservation.tableName }) }} · </template>
          {{ formatDate(reservation.startTime) }} ({{ RESTAURANT_TIMEZONE }})
        </p>
      </div>
      <span class="badge" :class="statusView.badge">{{ statusView.label }}</span>
    </div>

    <div class="reservation-card__body">
      <div class="reservation-card__row">
        <img src="/assets/svg/pin.svg" alt="" aria-hidden="true" class="icon-sm" />
        <span>{{ reservation.locationAddress }}</span>
      </div>
      <div class="reservation-card__row">
        <img src="/assets/svg/users.svg" alt="" aria-hidden="true" class="icon-sm" />
        <span>{{ t('customer.guestCount', { count: reservation.guestCount }, reservation.guestCount) }}</span>
      </div>
    </div>

    <div class="reservation-card__footer">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { computed } from 'vue'
import { RESTAURANT_TIMEZONE } from '@/utils/date-time'
import { formatDate } from '../../utils/formatters'
import {
  reservationStatusKey,
  type ReservationCustomer,
  type ReservationStatusKey,
} from '../../models/reservations/reservation.model'

const props = defineProps<{
  reservation: ReservationCustomer
}>()

const STATUS_VIEW: Record<ReservationStatusKey, { key: string; badge: string }> = {
  reserved: { key: 'customer.reserved', badge: 'badge--confirmed' },
  'in-progress': { key: 'customer.inProgress', badge: 'badge--pending' },
  finished: { key: 'customer.finished', badge: 'badge--completed' },
  cancelled: { key: 'customer.cancelled', badge: 'badge--cancelled' },
}

const statusView = computed(() => {
  const key = reservationStatusKey(props.reservation.status)
  return key ? { label: t(STATUS_VIEW[key].key), badge: STATUS_VIEW[key].badge } : { label: String(props.reservation.status ?? ''), badge: 'badge--pending' }
})
</script>

<style scoped>
.reservation-card {
  display: flex;
  flex-direction: column;
}

.reservation-card__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 16px;
  border-bottom: 1px solid var(--neutral-100);
  gap: 12px;
}

.reservation-card__location {
  margin: 0 0 4px;
}

.reservation-card__meta {
  margin: 0;
  font-size: 13px;
}

.reservation-card__body {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.reservation-card__row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--neutral-600);
}

.reservation-card__footer {
  padding: 12px 16px;
  border-top: 1px solid var(--neutral-100);
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.icon-sm {
  width: 14px;
  height: 14px;
}
</style>

