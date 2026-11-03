<template>
  <Teleport to="body">
    <div class="cart-backdrop" role="presentation" @click.self="cart.close()">
      <section ref="panel" class="cart" role="dialog" aria-modal="true" aria-labelledby="cart-title" tabindex="-1">
        <header class="cart__header">
          <h3 id="cart-title" class="cart__title">{{ t('orders.cart') }}</h3>
          <button type="button" class="icon-button cart__close" :aria-label="t('orders.closeCart')" @click="cart.close()">
            <img src="/assets/svg/close.svg" alt="" aria-hidden="true" width="20" height="20" />
          </button>
        </header>

        <LoadingSpinner v-if="cart.loading && !cart.orders.length" :text="t('orders.loadingCart')" />

        <template v-else>
          <section v-if="cart.draftOrders.length" class="orders" aria-labelledby="draft-title">
            <div class="orders__header">
              <h3 id="draft-title" class="orders__title">{{ t('orders.drafts') }}</h3>
              <span class="body">{{ t('orders.draftsHint') }}</span>
            </div>
            <DraftOrderCard
              v-for="order in cart.draftOrders"
              :key="order.orderId"
              :order="order"
              :disabled="cart.busy"
              @submit="cart.submit"
              @remove="(dishId) => cart.removeDish(order.orderId, dishId)"
              @quantity="(dishId, quantity) => cart.updateQuantity(order.orderId, dishId, quantity)"
              @add-dish="goTo('/menu')"
            />
          </section>

          <section v-if="cart.sentOrders.length" class="orders" aria-labelledby="sent-title">
            <div class="orders__header">
              <h3 id="sent-title" class="orders__title">{{ t('orders.sent') }}</h3>
              <span class="body">
                {{ t('orders.editingHint') }}
              </span>
            </div>
            <SentOrderCard
              v-for="order in cart.sentOrders"
              :key="order.orderId"
              :order="order"
              :disabled="cart.busy"
              @cancel="cart.cancelOrderId = order.orderId"
              @edit="cart.edit(order.orderId)"
            />
          </section>

          <div v-if="!cart.orders.length" class="empty-cart">
            <img src="/assets/img/empty-cart.png" alt="" aria-hidden="true" width="135" height="135" />
            <div class="empty-cart__info">
              <h3 class="orders__title">{{ t('orders.emptyCart') }}</h3>
              <span class="body">{{ t('orders.emptyCartHint') }}</span>
            </div>
            <button type="button" class="button button--primary button--large" @click="goTo('/reservations')">
              {{ t('orders.goToReservations') }}
            </button>
          </div>
        </template>
      </section>
    </div>

    <AppModal v-if="cart.submittedOrder" :title="t('orders.submittedTitle')" size="md" @close="cart.submittedOrderId = null">
      <p class="body">
        {{ t('orders.submittedReservation', { address: cart.submittedOrder.reservationAddress, time: orderReservationTime(cart.submittedOrder) }) }}
      </p>
      <p class="body">{{ t('orders.checkingAvailability') }}</p>
      <p v-if="cart.submittedOrder.canEdit" class="body">
        {{ t('orders.canModify') }}
      </p>
      <p v-else class="body">{{ cart.submittedOrder.editDisabledReason ? translateApiMessage(cart.submittedOrder.editDisabledReason) : t('orders.noMoreChanges') }}</p>
      <p class="body">{{ t('orders.thankYou') }}</p>
      <template #footer>
        <button v-if="cart.submittedOrder.canEdit" type="button" class="button button--secondary button--large" @click="askCancelSubmitted">
          {{ t('orders.cancelPreOrder') }}
        </button>
        <button
          v-if="cart.submittedOrder.canEdit"
          type="button"
          class="button button--primary button--large"
          :disabled="cart.busy"
          @click="cart.edit(cart.submittedOrder.orderId)"
        >
          {{ t('orders.editPreOrder') }}
        </button>
      </template>
    </AppModal>

    <AppModal v-if="cart.cancelOrderId" :title="t('orders.cancelOrder')" size="sm" @close="cart.cancelOrderId = null">
      <p class="body">{{ t('orders.confirmCancel', { id: cart.cancelOrderId }) }}</p>
      <template #footer>
        <button type="button" class="button button--secondary button--large" @click="cart.cancelOrderId = null">{{ t('orders.no') }}</button>
        <button
          type="button"
          class="button button--primary button--large"
          :disabled="cart.busy"
          @click="cart.cancel(cart.cancelOrderId)"
        >
          {{ t('orders.yesCancel') }}
        </button>
      </template>
    </AppModal>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { t } from '@/i18n'
import { translateApiMessage } from '@/i18n/errors'
import { orderReservationTime } from './cart-math'
import { useDialogFocus } from '@/composables/useDialogFocus'
import { useRouter } from 'vue-router'
import AppModal from '@/components/shared/AppModal.vue'
import LoadingSpinner from '@/components/shared/LoadingSpinner.vue'
import { useCartStore } from '@/stores/cart'
import DraftOrderCard from './DraftOrderCard.vue'
import SentOrderCard from './SentOrderCard.vue'

const cart = useCartStore()
const router = useRouter()
const panel = ref<HTMLElement | null>(null)

function goTo(path: string): void {
  cart.close()
  void router.push(path)
}

function askCancelSubmitted(): void {
  cart.cancelOrderId = cart.submittedOrderId
  cart.submittedOrderId = null
}

useDialogFocus(panel, () => cart.close())
</script>

<style scoped>
.cart-backdrop {
  position: fixed;
  inset: 0;
  z-index: 400;
  background: rgba(0, 0, 0, 0.6);
}

.cart {
  position: absolute;
  top: 0;
  right: 0;
  display: flex;
  flex-direction: column;
  gap: 40px;
  width: min(560px, 100vw);
  height: 100dvh;
  padding: 40px;
  overflow-y: auto;
  background: var(--neutral-0);
  box-shadow: 0 0 10px 4px rgba(194, 194, 194, 0.5);
  animation: slideIn 0.2s ease;
}

.cart:focus {
  outline: none;
}

@keyframes slideIn {
  from { transform: translateX(40px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

.cart__header {
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
}

.cart__title {
  margin: 0;
}

.cart__close {
  position: absolute;
  right: 0;
}

.orders {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.orders__header {
  display: flex;
  flex-direction: column;
}

.orders__title {
  margin: 0;
  font-size: 26px;
  line-height: 40px;
}

.empty-cart {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 40px;
  text-align: center;
}

.empty-cart__info {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.empty-cart .button {
  width: 100%;
}

.body {
  font-size: 14px;
  font-weight: 300;
  line-height: 24px;
}

@media (max-width: 650px) {
  .cart {
    gap: 24px;
    padding: 24px 16px;
  }
}
</style>
