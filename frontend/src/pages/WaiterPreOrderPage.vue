<template>
  <div class="waiter-preorder container">
    <div class="page-header"><h1>{{ t('staff.preorderTitle') }}</h1><p>{{ t('staff.preorderSubtitle') }}</p></div>
    <label class="selector">{{ t('staff.reservation') }}
      <select v-model="selectedReservationId" :aria-label="t('staff.reservation')" @change="selectReservation">
        <option value="">{{ t('staff.chooseReservation') }}</option>
        <option v-for="reservation in reservations" :key="reservation.id" :value="reservation.id">
          {{ reservation.locationAddress }} · {{ formatDate(reservation.startTime) }} ({{ RESTAURANT_TIMEZONE }})
        </option>
      </select>
    </label>
    <LoadingSpinner v-if="loading" :text="t('staff.loadingOrder')" />
    <p v-else-if="error" role="alert">{{ error }}</p>
    <EmptyState v-else-if="selectedReservationId && !order" :title="t('staff.noPreorder')" :description="t('staff.noPreorderDescription')" />
    <section v-else-if="order" class="card order-card">
      <h2>{{ statusLabel }}</h2>
      <p v-if="order.status === 0">{{ t('staff.stillChoosing') }}</p>
      <ul class="order-lines">
        <li v-for="item in order.orderItems" :key="item.dish.id">
          <div><strong>{{ item.quantity }} × {{ localizedDish(item.dish).name }}</strong><p>{{ formatCurrency(item.dish.price * item.quantity) }} · {{ itemStateLabel(item.state) }}</p></div>
          <div v-if="canReview" class="actions">
            <AppButton :disabled="busy || item.state === 1" :aria-label="t('staff.confirmDish', { name: localizedDish(item.dish).name })" @click="reviewDish(item.dish.id, true)">{{ t('staff.confirm') }}</AppButton>
            <AppButton variant="secondary" :disabled="busy || item.state === 2" :aria-label="t('staff.cancelNamedDish', { name: localizedDish(item.dish).name })" @click="reviewDish(item.dish.id, false)">{{ t('staff.cancelDish') }}</AppButton>
          </div>
        </li>
      </ul>
      <p>{{ t('staff.totalWithoutCancelled') }} <strong>{{ formatCurrency(orderTotal(order, true)) }}</strong></p>
      <AppButton variant="secondary" :disabled="busy" @click="loadOrder">{{ t('staff.refresh') }}</AppButton>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { t } from '@/i18n'
import { localizedDish } from '@/i18n/catalog'
import { useRoute, useRouter } from 'vue-router'
import { ordersApi, reservationsApi, type Order, type Reservation } from '@/services/api'
import { isApiError } from '@/services/http/api-client'
import { formatCurrency, formatDate } from '@/utils/formatters'
import { RESTAURANT_TIMEZONE } from '@/utils/date-time'
import { orderTotal } from '@/components/cart/cart-math'
import AppButton from '@/components/shared/AppButton.vue'
import LoadingSpinner from '@/components/shared/LoadingSpinner.vue'
import EmptyState from '@/components/shared/EmptyState.vue'

const route = useRoute()
const router = useRouter()
const reservations = ref<Reservation[]>([])
const selectedReservationId = ref(String(route.query.reservationId ?? ''))
const order = ref<Order | null>(null)
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const statusLabel = computed(() => t(`staff.${['draft', 'confirmed', 'cancelled', 'awaitingReview'][order.value?.status ?? 0] ?? 'draft'}`))
const itemStateLabel = (state: number) => t(`staff.${['pending', 'confirmed', 'cancelled'][state] ?? 'pending'}`)
const canReview = computed(() => !!order.value && [1, 3].includes(order.value.status) && ![1, 3].includes(reservations.value.find(r => r.id === selectedReservationId.value)?.status ?? 3))

async function loadOrder(): Promise<void> {
  order.value = null
  error.value = ''
  if (!selectedReservationId.value) return
  loading.value = true
  try { order.value = await ordersApi.get(selectedReservationId.value, { skipErrorToast: true }) }
  catch (err) { if (!isApiError(err, 404)) error.value = err instanceof Error ? err.message : t('staff.orderLoadFailed') }
  finally { loading.value = false }
}
async function selectReservation(): Promise<void> {
  await router.replace({ query: { reservationId: selectedReservationId.value || undefined } })
  await loadOrder()
}
async function reviewDish(dishId: string, confirm: boolean): Promise<void> {
  busy.value = true
  try {
    if (confirm) await ordersApi.confirmDish(selectedReservationId.value, dishId)
    else await ordersApi.cancelDish(selectedReservationId.value, dishId)
    await loadOrder()
  } catch { /* API client displays failure. */ }
  finally { busy.value = false }
}
onMounted(async () => {
  loading.value = true
  try { reservations.value = await reservationsApi.list(); await loadOrder() }
  catch (err) { error.value = err instanceof Error ? err.message : t('staff.reservationsLoadFailed') }
  finally { loading.value = false }
})
</script>

<style scoped>
.waiter-preorder { padding-bottom: 48px; }
.selector { display: grid; gap: 8px; max-width: 650px; margin-bottom: 24px; }
.selector select { padding: 12px; border: 1px solid var(--neutral-300); border-radius: 8px; font: inherit; max-width: 100%; }
.order-card { padding: 24px; }
.order-lines { list-style: none; padding: 0; }
.order-lines li { display: flex; justify-content: space-between; align-items: center; gap: 16px; border-bottom: 1px solid var(--neutral-200); padding: 16px 0; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; }
@media (max-width: 600px) { .order-lines li { flex-direction: column; align-items: stretch; } }
</style>
