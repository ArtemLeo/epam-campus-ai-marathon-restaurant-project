<template>
  <template v-if="visible">
    <button
      type="button"
      class="cart-button"
      :aria-expanded="cart.isOpen"
      :aria-label="cart.draftItemCount ? t('orders.cartCount', { count: cart.draftItemCount }, cart.draftItemCount) : t('orders.cart')"
      @click="cart.toggle()"
    >
      <img src="/assets/svg/cart-empty.svg" alt="" aria-hidden="true" width="24" height="24" />
      <span class="cart-button__label">{{ t('orders.cart') }}</span>
      <span v-if="cart.draftItemCount" class="cart-button__badge" aria-hidden="true">{{ cart.draftItemCount }}</span>
    </button>
    <CartDrawer v-if="cart.isOpen" />
  </template>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { t } from '@/i18n'
import CartDrawer from '@/components/cart/CartDrawer.vue'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'

/** Header entry point of the pre-order cart; customers only. */
const auth = useAuthStore()
const cart = useCartStore()

const visible = computed(() => auth.isAuthenticated && auth.isCustomer)

watch(
  visible,
  (isVisible) => {
    if (isVisible) void cart.load()
    else cart.close()
  },
  { immediate: true },
)
</script>

<style scoped>
.cart-button {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--neutral-900);
  font: inherit;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
}

.cart-button:hover {
  background: var(--neutral-100);
}

.cart-button:focus-visible {
  outline: 2px solid var(--green-600);
  outline-offset: 2px;
}

.cart-button__badge {
  position: absolute;
  top: 2px;
  left: 26px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: var(--radius-full);
  background: var(--green-600);
  color: var(--neutral-0);
  font-size: 11px;
  line-height: 18px;
  text-align: center;
}

@media (max-width: 600px) {
  .cart-button__label {
    display: none;
  }
}
</style>
