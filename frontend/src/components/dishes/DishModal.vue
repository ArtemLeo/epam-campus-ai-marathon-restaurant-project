<template>
  <AppModal :title="displayDish.name" size="md" @close="emit('close')">
    <img :src="dish.imageUrl || '/assets/svg/dish-placeholder.svg'" :alt="displayDish.name" class="dish-modal__image" />
    <p class="dish-modal__desc">{{ displayDish.description }}</p>
    <dl class="dish-modal__facts">
      <div><dt>{{ t('customer.price') }}</dt><dd>{{ formatCurrency(dish.price) }}</dd></div>
      <div><dt>{{ t('customer.weight') }}</dt><dd>{{ displayDish.weight }}</dd></div>
      <div><dt>{{ t('customer.calories') }}</dt><dd>{{ displayDish.calories }}</dd></div>
      <div><dt>{{ t('customer.proteins') }}</dt><dd>{{ displayDish.proteins }}</dd></div>
      <div><dt>{{ t('customer.fats') }}</dt><dd>{{ displayDish.fats }}</dd></div>
      <div><dt>{{ t('customer.carbohydrates') }}</dt><dd>{{ displayDish.carbohydrates }}</dd></div>
      <div><dt>{{ t('customer.vitamins') }}</dt><dd>{{ displayDish.vitamins }}</dd></div>
      <div><dt>{{ t('customer.state') }}</dt><dd>{{ dishState }}</dd></div>
    </dl>

    <div v-if="auth.isAuthenticated && auth.isCustomer" class="dish-modal__cart">
      <template v-if="reservations.length">
        <label class="dish-modal__label" for="dish-reservation">{{ t('customer.reservation') }}</label>
        <select id="dish-reservation" v-model="reservationId" class="dish-modal__select">
          <option v-for="r in reservations" :key="r.id" :value="r.id">
            {{ r.locationAddress }} - {{ formatDate(r.startTime) }}
          </option>
        </select>
      </template>
      <p v-else-if="!loadingReservations" class="text-muted">{{ t('customer.noEligibleReservation') }}</p>
    </div>

    <template v-if="auth.isAuthenticated && auth.isCustomer" #footer>
      <AppButton :disabled="!reservationId || cart.busy || dish.state !== 'Available'" @click="addToCart">{{ t(dish.state === 'Available' ? 'customer.addToCart' : 'customer.unavailable') }}</AppButton>
    </template>
  </AppModal>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { localizedDish } from '@/i18n/catalog'
import { onMounted, computed, ref } from 'vue'
import { formatDate, formatCurrency } from '@/utils/formatters'
import AppModal from '../shared/AppModal.vue'
import AppButton from '../shared/AppButton.vue'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'
import { reservationsApi, ordersApi, type Dish, type Reservation } from '@/services/api'

const props = defineProps<{ dish: Dish }>()
const displayDish = computed(() => localizedDish(props.dish))
const dishState = computed(() => t(`customer.${({ Available: 'available', 'On stop': 'onStop', OnStop: 'onStop', 'Out of stock': 'outOfStock', OutOfStock: 'outOfStock' } as Record<string, string>)[props.dish.state] ?? 'unavailable'}`))
const emit = defineEmits<{ close: [] }>()

const auth = useAuthStore()
const cart = useCartStore()
const reservations = ref<Reservation[]>([])
const reservationId = ref('')
const loadingReservations = ref(false)

onMounted(async () => {
  if (!auth.isAuthenticated || !auth.isCustomer) return
  loadingReservations.value = true
  try {
    const [bookings, orders] = await Promise.all([reservationsApi.list(), ordersApi.list()])
    reservations.value = bookings.filter((r) => {
      const order = orders.find((item) => item.reservationId === r.id)
      return r.status === 0 && Date.parse(r.startTime) > Date.now() + 30 * 60_000
        && props.dish.locationIds?.includes(r.locationId)
        && (!order || order.canEdit)
    })
    reservationId.value = reservations.value[0]?.id ?? ''
  } catch {
    reservations.value = []
  } finally {
    loadingReservations.value = false
  }
})

async function addToCart(): Promise<void> {
  if (await cart.addDish(reservationId.value, props.dish)) {
    await cart.load()
    emit('close')
  }
}
</script>

<style scoped>
.dish-modal__image {
  width: 100%;
  max-height: 260px;
  object-fit: cover;
  border-radius: 8px;
}
.dish-modal__desc {
  margin: 12px 0;
}
.dish-modal__facts {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px 16px;
  margin: 0;
}
.dish-modal__facts div {
  display: flex;
  flex-direction: column;
}
.dish-modal__facts dt {
  font-size: 12px;
  color: var(--gray-500, #6b7280);
}
.dish-modal__facts dd {
  margin: 0;
  font-weight: 500;
}
.dish-modal__cart {
  margin-top: 16px;
}
.dish-modal__label {
  display: block;
  font-size: 13px;
  margin-bottom: 4px;
}
.dish-modal__select {
  width: 100%;
  padding: 8px;
  border-radius: 6px;
  border: 1px solid #d1d5db;
}
</style>
