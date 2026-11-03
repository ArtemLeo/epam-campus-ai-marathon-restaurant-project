<template>
  <article class="sent-order">
    <h4 class="sent-order__title body-bold">
      {{ t('orders.orderTitle', { id: order.orderId, address: order.reservationAddress, time: orderReservationTime(order) }) }}
    </h4>

    <ul class="sent-order__items">
      <li v-for="item in order.orderItems" :key="item.dish.id" class="line">
        <span class="body">
          {{ item.quantity }}× {{ localizedDish(item.dish).name }}
          <span :class="`state state--${stateClass(item.state)}`">({{ t(`orders.${stateClass(item.state)}`) }})</span>
        </span>
        <span class="body-bold">{{ formatCurrency(item.dish.price * item.quantity) }}</span>
      </li>
    </ul>

    <p class="line sent-order__total">
      <span class="body">{{ t('orders.totalPrice') }}</span>
      <span class="sent-order__sum">{{ formatCurrency(orderTotal(order, true)) }}</span>
    </p>

    <p v-if="!order.canEdit" class="body" role="status">{{ order.editDisabledReason ? translateApiMessage(order.editDisabledReason) : t('orders.noMoreChanges') }}</p>
    <div v-else class="sent-order__actions">
      <button type="button" class="button button--secondary button--large" :disabled="disabled" @click="emit('cancel')">
        {{ t('orders.cancelPreOrder') }}
      </button>
      <button type="button" class="button button--primary button--large" :disabled="disabled" @click="emit('edit')">
        {{ t('orders.editPreOrder') }}
      </button>
    </div>
  </article>
</template>

<script setup lang="ts">
import type { Order } from '@/services/api'
import { t } from '@/i18n'
import { localizedDish } from '@/i18n/catalog'
import { translateApiMessage } from '@/i18n/errors'
import { formatCurrency } from '@/utils/formatters'
import { ITEM_STATE_LABELS, orderTotal, orderReservationTime } from './cart-math'

defineProps<{ order: Order; disabled?: boolean }>()
const emit = defineEmits<{ cancel: []; edit: [] }>()

function stateClass(state: number): string {
  return ITEM_STATE_LABELS[state]?.toLowerCase() ?? 'unknown'
}
</script>

<style scoped>
.sent-order {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 0;
  border-top: 1px solid var(--neutral-200);
  border-bottom: 1px solid var(--neutral-200);
}

.sent-order__title {
  margin: 0;
  word-break: break-word;
}

.sent-order__items {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin: 0;
}

.sent-order__sum {
  font-size: 26px;
  font-weight: 500;
  line-height: 40px;
}

.sent-order__actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 16px;
}

.state--pending {
  color: var(--orange-600);
}

.state--confirmed {
  color: var(--green-600);
}

.state--rejected {
  color: var(--red-400);
}

.body {
  font-size: 14px;
  font-weight: 300;
  line-height: 24px;
}

.body-bold {
  font-size: 14px;
  font-weight: 500;
  line-height: 24px;
}
</style>
