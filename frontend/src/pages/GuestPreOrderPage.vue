<template>
  <div class="guest-page container">
    <LoadingSpinner v-if="loading" :text="t('orders.openingInvite')" />
    <EmptyState v-else-if="error" icon="⏰" :title="t('orders.inviteUnavailable')" :description="message(error)" />
    <template v-else-if="invite">
      <div class="page-header">
        <h1>{{ t('orders.joinMeal', { name: invite.InviterName }) }}</h1>
        <p>{{ invite.LocationAddress }} · {{ formatDate(invite.StartTime) }} ({{ RESTAURANT_TIMEZONE }})</p>
      </div>
      <form v-if="!credentials" class="card join-form" @submit.prevent="join">
        <AppInput v-model="guestName" :label="t('orders.yourName')" maxlength="50" required autocomplete="name" />
        <p v-if="actionError" class="form-error" role="alert">{{ message(actionError) }}</p>
        <AppButton type="submit" :loading="busy" :disabled="!guestName.trim()">{{ t('orders.joinGroup') }}</AppButton>
      </form>
      <template v-else-if="session">
        <div v-if="session.isSubmitted" class="card submitted" role="status">
          <h2>{{ t('orders.guestSubmitted') }}</h2>
          <p>{{ t('orders.guestSubmittedHint', { name: session.name }) }}</p>
        </div>
        <div class="guest-layout">
          <section v-if="!session.isSubmitted" :aria-label="t('orders.menu')">
            <AppInput v-model="search" :label="t('orders.searchDishes')" />
            <p v-if="!filteredDishes.length">{{ t('orders.noMatchingDishes') }}</p>
            <div class="dishes-grid">
              <article v-for="dish in filteredDishes" :key="dish.id" class="card dish-card">
                <img :src="dish.imageUrl || '/assets/svg/dish-placeholder.svg'" :alt="dish.name" loading="lazy" />
                <div class="dish-card__body">
                  <h3>{{ dish.name }}</h3><p>{{ dish.description }}</p>
                  <strong>{{ formatCurrency(dish.price) }}</strong>
                  <AppButton :disabled="busy || !dish.selectable" :aria-label="t('orders.addNamedDish', { name: dish.name })" @click="addDish(dish.id)">
                    {{ t(dish.selectable ? 'orders.add' : 'orders.unavailable') }}
                  </AppButton>
                </div>
              </article>
            </div>
          </section>
          <section class="card guest-summary" aria-labelledby="guest-order-title">
            <h2 id="guest-order-title">{{ t('orders.guestOrder', { name: session.name }) }}</h2>
            <p v-if="!session.items.length">{{ t('orders.chooseDish') }}</p>
            <ul v-else class="order-list">
              <li v-for="item in session.items" :key="item.dish.id">
                <span>{{ item.quantity }} × {{ localizedDish(item.dish).name }}</span>
                <strong>{{ formatCurrency(item.quantity * item.dish.price) }}</strong>
                <button
                  v-if="!session.isSubmitted" type="button" class="button button--secondary button--small" :disabled="busy"
                  :aria-label="t('orders.removeOneNamedDish', { name: localizedDish(item.dish).name })" @click="removeDish(item.dish.id)"
                >
                  {{ t('orders.removeOne') }}
                </button>
              </li>
            </ul>
            <p>{{ t('orders.totalAmount', { amount: formatCurrency(session.total) }) }}</p>
            <p v-if="actionError" class="form-error" role="alert">{{ message(actionError) }}</p>
            <AppButton v-if="!session.isSubmitted" :loading="busy" :disabled="!session.items.length" @click="submitOrder">{{ t('orders.submitPreOrderTitle') }}</AppButton>
          </section>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { t } from '@/i18n'
import { localizedDish } from '@/i18n/catalog'
import { translateApiMessage } from '@/i18n/errors'
import { isApiError } from '@/services/http/api-client'
import { getServerErrorMessage } from '@/shared/helpers/http-error-helpers'
import { useRoute } from 'vue-router'
import { guestApi, type GuestMenuDish, type GuestSessionCreated, type GuestSessionInfo } from '@/services/api'
import type { GuestInvite } from '@/models/reservations/guest-invite.model'
import AppButton from '@/components/shared/AppButton.vue'
import AppInput from '@/components/shared/AppInput.vue'
import EmptyState from '@/components/shared/EmptyState.vue'
import LoadingSpinner from '@/components/shared/LoadingSpinner.vue'
import { formatCurrency, formatDate } from '@/utils/formatters'
import { RESTAURANT_TIMEZONE } from '@/utils/date-time'

const route = useRoute()
const invite = ref<GuestInvite | null>(null)
const credentials = ref<GuestSessionCreated | null>(null)
const session = ref<GuestSessionInfo | null>(null)
const dishes = ref<GuestMenuDish[]>([])
const guestName = ref('')
const search = ref('')
const loading = ref(true)
const busy = ref(false)
const error = ref<unknown>(null)
const actionError = ref<unknown>(null)
const storageKey = computed(() => `guest-session:${String(route.params.token)}`)
const filteredDishes = computed(() => dishes.value.map(dish => localizedDish(dish)).filter(d => `${d.name} ${d.description}`.toLocaleLowerCase().includes(search.value.toLocaleLowerCase())))

function message(err: unknown): string {
  if (isApiError(err)) return translateApiMessage(getServerErrorMessage(err.body) || err.message, err.status)
  return err instanceof Error ? translateApiMessage(err.message) : t('orders.tryAgainMessage')
}

async function loadSession(): Promise<void> {
  if (!credentials.value) return
  const { SessionId, SessionToken } = credentials.value
  session.value = await guestApi.session(SessionId, SessionToken)
  if (!session.value.isSubmitted) {
    const menu = await guestApi.menu(SessionId, SessionToken)
    dishes.value = Object.values(menu.dishes).flatMap(category => category ?? [])
  }
}

async function join(): Promise<void> {
  if (!invite.value || busy.value || !guestName.value.trim()) return
  busy.value = true
  actionError.value = null
  try {
    credentials.value = await guestApi.createSession(invite.value.GroupReservationId, guestName.value.trim())
    localStorage.setItem(storageKey.value, JSON.stringify(credentials.value))
    await loadSession()
  } catch (err) { actionError.value = err }
  finally { busy.value = false }
}

async function mutate(action: (id: string, token: string) => Promise<unknown>): Promise<void> {
  if (!credentials.value || busy.value) return
  busy.value = true
  actionError.value = null
  try {
    await action(credentials.value.SessionId, credentials.value.SessionToken)
    await loadSession()
  } catch (err) { actionError.value = err }
  finally { busy.value = false }
}
const addDish = (id: string) => mutate((sessionId, token) => guestApi.addDish(sessionId, token, id))
const removeDish = (id: string) => mutate((sessionId, token) => guestApi.removeDish(sessionId, token, id))
const submitOrder = () => mutate((sessionId, token) => guestApi.submit(sessionId, token))

watch(() => route.params.token, async () => {
  loading.value = true
  error.value = null
  credentials.value = null
  session.value = null
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey.value) ?? 'null') as Partial<GuestSessionCreated> | null
    if (typeof stored?.SessionId === 'string' && typeof stored.SessionToken === 'string') {
      credentials.value = { SessionId: stored.SessionId, SessionToken: stored.SessionToken }
    }
  } catch { localStorage.removeItem(storageKey.value) }
  try {
    invite.value = await guestApi.invite(String(route.params.token), credentials.value?.SessionToken, { skipErrorToast: true })
    await loadSession()
  } catch (err) { error.value = err }
  finally { loading.value = false }
}, { immediate: true })
</script>

<style scoped>
.guest-page { padding: 24px 16px 48px; }
.join-form { max-width: 480px; padding: 24px; display: grid; gap: 20px; }
.guest-layout { display: grid; grid-template-columns: minmax(0, 1fr) 330px; gap: 28px; align-items: start; }
.dishes-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 20px; margin-top: 20px; }
.dish-card { overflow: hidden; }
.dish-card img { width: 100%; height: 170px; object-fit: cover; }
.dish-card__body { padding: 16px; display: grid; gap: 12px; }
.dish-card h3, .dish-card p { margin: 0; }
.guest-summary { padding: 24px; display: grid; gap: 16px; }
.order-list { padding: 0; margin: 0; list-style: none; }
.order-list li { display: grid; gap: 8px; padding: 12px 0; border-bottom: 1px solid var(--neutral-200); }
.submitted { padding: 24px; margin-bottom: 24px; background: var(--green-50); }
.form-error { color: var(--red-600); }
@media (max-width: 900px) { .guest-layout { grid-template-columns: 1fr; } }
</style>
