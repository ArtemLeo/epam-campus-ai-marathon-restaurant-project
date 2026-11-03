<template>
  <article class="draft-order">
    <h4 class="draft-order__title body-bold">
      {{ t('orders.orderTitle', { id: order.orderId, address: order.reservationAddress, time: orderReservationTime(order) }) }}
    </h4>

    <ul class="draft-order__items">
      <li v-for="item in order.orderItems" :key="item.dish.id" class="dish-row">
        <img
          v-if="item.dish.imageUrl"
          class="dish-row__image"
          :src="item.dish.imageUrl"
          :alt="localizedDish(item.dish).name"
          width="96"
          height="96"
          loading="lazy"
        />
        <span v-else class="dish-row__image dish-row__image--initial" aria-hidden="true">{{ localizedDish(item.dish).name.charAt(0) }}</span>

        <div class="dish-row__body">
          <div class="dish-row__details">
            <div class="dish-row__name">
              <span class="body-bold">{{ localizedDish(item.dish).name }}</span>
              <span class="caption">{{ t('orders.prepared') }}</span>
            </div>
            <button
              type="button"
              class="icon-button"
              :aria-label="t('orders.removeDish', { name: localizedDish(item.dish).name })"
              :disabled="disabled || !order.canEdit"
              @click="emit('remove', item.dish.id)"
            >
              <img src="/assets/svg/trash.svg" alt="" aria-hidden="true" width="24" height="24" />
            </button>
          </div>

          <div class="dish-row__quantity">
            <div class="stepper">
              <button
                type="button"
                class="icon-button"
                :aria-label="t('orders.decrease')"
                :disabled="disabled || !order.canEdit || item.quantity <= 1"
                @click="emit('quantity', item.dish.id, item.quantity - 1)"
              >
                <img src="/assets/svg/minus-green.svg" alt="" aria-hidden="true" width="24" height="24" />
              </button>
              <span class="stepper__value" aria-live="polite">{{ item.quantity }}</span>
              <button
                type="button"
                class="icon-button"
                :aria-label="t('orders.increase')"
                :disabled="disabled || !order.canEdit"
                @click="emit('quantity', item.dish.id, item.quantity + 1)"
              >
                <img src="/assets/svg/plus-green.svg" alt="" aria-hidden="true" width="24" height="24" />
              </button>
            </div>
            <span class="body-bold">{{ formatCurrency(item.dish.price * item.quantity) }}</span>
          </div>
        </div>
      </li>
    </ul>

    <button type="button" class="button button--tertiary button--large add-dish" :disabled="disabled || !order.canEdit" @click="emit('add-dish')">
      <img src="/assets/svg/plus-green.svg" alt="" aria-hidden="true" width="24" height="24" />
      {{ t('orders.addDish') }}
    </button>

    <p class="draft-order__total">
      <span class="body-bold">{{ t('orders.total') }}</span>
      <span class="draft-order__sum">{{ formatCurrency(orderTotal(order)) }}</span>
    </p>

    <button
      type="button"
      class="button button--primary button--large draft-order__submit"
      :disabled="disabled || !order.canEdit"
      @click="emit('submit', order.orderId)"
    >
      {{ t('orders.submitPreOrder') }}
    </button>
    <p v-if="!order.canEdit" class="caption" role="status">{{ order.editDisabledReason ? translateApiMessage(order.editDisabledReason) : t('orders.noMoreChanges') }}</p>
  </article>
</template>

<script setup lang="ts">
import type { Order } from '@/services/api'
import { t } from '@/i18n'
import { localizedDish } from '@/i18n/catalog'
import { translateApiMessage } from '@/i18n/errors'
import { formatCurrency } from '@/utils/formatters'
import { orderTotal, orderReservationTime } from './cart-math'

defineProps<{ order: Order; disabled?: boolean }>()

const emit = defineEmits<{
  submit: [orderId: string]
  remove: [dishId: string]
  quantity: [dishId: string, quantity: number]
  'add-dish': []
}>()
</script>

<style scoped>
.draft-order {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.draft-order__title {
  margin: 0;
  word-break: break-word;
}

.draft-order__items {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.dish-row {
  display: flex;
  gap: 16px;
  padding: 24px;
  border-radius: var(--radius-md);
  box-shadow: 0 0 10px 4px rgba(194, 194, 194, 0.5);
}

.dish-row__image {
  flex: 0 0 96px;
  width: 96px;
  height: 96px;
  border-radius: 50%;
  object-fit: cover;
  box-shadow: 0 0 10px 4px rgba(194, 194, 194, 0.5);
}

.dish-row__image--initial {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--green-300);
  color: var(--neutral-0);
  font-size: 32px;
  font-weight: 500;
}

.dish-row__body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
  min-width: 0;
}

.dish-row__details,
.dish-row__quantity {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.dish-row__details {
  align-items: flex-start;
}

.dish-row__name {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stepper {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-md);
}

.stepper__value {
  min-width: 24px;
  text-align: center;
}

.add-dish {
  align-self: flex-start;
  text-decoration: none;
}

.draft-order__total {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 16px;
  margin: 0;
}

.draft-order__sum {
  font-size: 32px;
  font-weight: 500;
  line-height: 40px;
}

.draft-order__submit {
  width: 100%;
}

.body-bold {
  font-size: 14px;
  font-weight: 500;
  line-height: 24px;
}

.caption {
  font-size: 12px;
  font-weight: 300;
  line-height: 16px;
}

@media (max-width: 480px) {
  .dish-row {
    padding: 16px;
  }

  .dish-row__image {
    flex-basis: 64px;
    width: 64px;
    height: 64px;
  }
}
</style>
