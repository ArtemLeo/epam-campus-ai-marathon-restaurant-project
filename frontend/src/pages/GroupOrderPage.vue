<template>
  <main class="group-order">
    <header class="group-order__header">
      <div class="group-order__title-row">
        <h1 class="group-order__title">{{ t('orders.groupTitle') }}</h1>
        <span v-if="loadState === 'ready'" class="status-badge" :class="`status-badge--${status.toLowerCase()}`">
          {{ t(STATUS_KEYS[status]) }}
        </span>
      </div>

      <ul v-if="invite" class="group-order__meta">
        <li>
          <img src="/assets/svg/location-green.svg" alt="" aria-hidden="true" width="20" height="20" />
          {{ invite.LocationAddress }}
        </li>
        <li>
          <img src="/assets/svg/calendar-green.svg" alt="" aria-hidden="true" width="20" height="20" />
          {{ formatMediumDate(invite.StartTime) }}
        </li>
        <li>
          <img src="/assets/svg/clock-green.svg" alt="" aria-hidden="true" width="20" height="20" />
          {{ formatTime(invite.StartTime) }} – {{ formatTime(invite.EndTime) }} ({{ RESTAURANT_TIMEZONE }})
        </li>
        <li>
          <img src="/assets/svg/people-green.svg" alt="" aria-hidden="true" width="20" height="20" />
          {{ guestsLabel }}
        </li>
      </ul>
    </header>

    <div v-if="loadState === 'loading'" class="group-order__state" role="status">
      <LoadingSpinner :text="t('orders.loadingGroup')" />
    </div>

    <section v-else-if="loadState === 'not-found'" class="group-order__state">
      <h2 class="group-order__state-title">{{ t('orders.groupNotFound') }}</h2>
      <p class="group-order__state-text">{{ t('orders.groupNotFoundHint') }}</p>
      <RouterLink to="/reservations" class="button button--secondary button--large">{{ t('orders.backReservations') }}</RouterLink>
    </section>

    <section v-else-if="loadState === 'error'" class="group-order__state">
      <h2 class="group-order__state-title">{{ t('orders.groupLoadFailed') }}</h2>
      <p class="group-order__state-text">{{ t('orders.checkConnection') }}</p>
      <button type="button" class="button button--primary button--large" @click="load">{{ t('orders.tryAgain') }}</button>
    </section>

    <template v-else>
      <div v-if="isOpen" class="sync-bar">
        <p class="sync-bar__text" :class="{ 'sync-bar__text--failed': syncFailed }" aria-live="polite">
          {{ t(syncFailed ? 'orders.refreshFailed' : 'orders.updatedAt', { time: lastUpdatedLabel }) }}
        </p>
        <button type="button" class="sync-bar__refresh" :disabled="syncing" @click="refresh">{{ t('orders.refresh') }}</button>
      </div>

      <p v-if="isOpen && pendingCount > 0" class="pending-banner" role="note">
        <img src="/assets/svg/bell-regular.svg" alt="" aria-hidden="true" width="20" height="20" />
        {{ pendingMessage }}
      </p>

      <ul class="group-order__participants">
        <li v-for="person in participants" :key="person.id">
          <ParticipantCard
            :participant="person"
            :is-me="person.id === ownerSessionId"
            :can-remove="isOpen && person.type === 'Guest'"
            @remove-click="askRemove"
          />
        </li>
      </ul>

      <section class="consolidated" aria-labelledby="consolidated-title">
        <h2 id="consolidated-title" class="consolidated__title">{{ t('orders.consolidated') }}</h2>
        <p v-if="!hasAnyDishes" class="consolidated__empty">{{ t('orders.noParticipantDishes') }}</p>
        <p v-else-if="!consolidated.items.length" class="consolidated__empty">
          {{ t('orders.noSubmittedCarts') }}
        </p>
        <ul v-else class="consolidated__items">
          <li v-for="item in consolidated.items" :key="item.dish.id" class="consolidated__item">
            <span>{{ localizedDish(item.dish).name }} × {{ item.quantity }}</span>
            <span>{{ formatCurrency(item.dish.price * item.quantity) }}</span>
          </li>
        </ul>
        <p class="grand-total">
          <span>{{ t('orders.grandTotal') }}</span>
          <span class="grand-total__value">{{ formatCurrency(consolidated.total) }}</span>
        </p>
      </section>

      <button
        v-if="isOpen"
        type="button"
        class="button button--primary button--extra-large group-order__submit"
        :disabled="!canSubmit"
        @click="openSubmitDialog"
      >
        {{ t('orders.submitPreOrderTitle') }}
      </button>
      <button v-else type="button" class="button button--extra-large group-order__submit" disabled>
        {{ t(status === 'Submitted' ? 'orders.preOrderSent' : 'orders.preOrderClosed') }}
      </button>
    </template>

    <AppModal v-if="submitDialogOpen" :title="t('orders.submitPreOrderTitle')" size="sm" @close="closeSubmitDialog">
      <p class="dialog-text">
        {{ t('orders.confirmSubmit', { count: dishCount, amount: formatCurrency(consolidated.total) }, dishCount) }}
      </p>
      <template #footer>
        <button type="button" class="button button--tertiary button--large" @click="closeSubmitDialog">{{ t('orders.cancel') }}</button>
        <button type="button" class="button button--primary button--large" :disabled="submitting" @click="confirmSubmit">
          {{ t(submitting ? 'orders.submitting' : 'orders.submit') }}
        </button>
      </template>
    </AppModal>

    <AppModal v-if="guestToRemove" :title="t('orders.removeGuest')" size="sm" @close="closeRemoveDialog">
      <p class="dialog-text">
        {{ t('orders.confirmRemoveGuest', { name: guestToRemove.name }) }}
      </p>
      <template #footer>
        <button type="button" class="button button--tertiary button--large" @click="closeRemoveDialog">{{ t('orders.cancel') }}</button>
        <button type="button" class="button button--large remove-confirm" :disabled="removing" @click="confirmRemove">
          {{ t(removing ? 'orders.removing' : 'orders.removeGuest') }}
        </button>
      </template>
    </AppModal>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { t } from '@/i18n'
import { localizedDish } from '@/i18n/catalog'
import ParticipantCard from '@/components/group-orders/ParticipantCard.vue'
import AppModal from '@/components/shared/AppModal.vue'
import LoadingSpinner from '@/components/shared/LoadingSpinner.vue'
import { useToast } from '@/composables/useToast'
import { useGroupOrdersService } from '@/services/group-orders/group-orders.service'
import { isApiError } from '@/services/http/api-client'
import { consolidatePreOrder } from '@/shared/helpers/consolidate-pre-order'
import { RESTAURANT_TIMEZONE } from '@/utils/date-time'
import { formatClock, formatCurrency, formatMediumDate, formatTime } from '@/utils/formatters'
import type { GroupSessionsResponse } from '@/models/group-orders/group-sessions-response.model'
import type { GroupReservationStatus, GroupStatusResponse } from '@/models/group-orders/group-status.model'
import type { Participant } from '@/models/group-orders/participant.model'
import type { GuestInvite } from '@/models/reservations/guest-invite.model'

const props = defineProps<{
  /** From the route: /reservations/:reservationId/group-order */
  reservationId: string
}>()

/** Background sync period while the group is still collecting pre-orders. */
const SYNC_INTERVAL_MS = 15_000

const STATUS_KEYS: Record<GroupReservationStatus, string> = {
  Open: 'orders.collecting',
  Submitted: 'orders.sentToRestaurant',
  Closed: 'orders.closed',
}

type LoadState = 'loading' | 'ready' | 'not-found' | 'error'

const service = useGroupOrdersService()
const toast = useToast()

const loadState = ref<LoadState>('loading')
const invite = ref<GuestInvite | null>(null)
const sessions = ref<GroupSessionsResponse>({ participants: [], total: 0 })
const ownerSessionId = ref('')
const groupStatus = ref<GroupStatusResponse | null>(null)
const lastUpdatedAt = ref<Date | null>(null)
const syncFailed = ref(false)
const syncing = ref(false)
const submitDialogOpen = ref(false)
const submitting = ref(false)
const guestToRemove = ref<Participant | null>(null)
const removing = ref(false)

const participants = computed(() => sessions.value.participants)
// Only submitted carts go to the restaurant, so this — not `sessions.total` — is the Grand Total.
const consolidated = computed(() => consolidatePreOrder(participants.value))
const dishCount = computed(() => consolidated.value.items.reduce((sum, item) => sum + item.quantity, 0))
const hasAnyDishes = computed(() => participants.value.some((person) => person.items.length > 0))
const pendingCount = computed(() => participants.value.filter((person) => !person.isSubmitted).length)
const status = computed<GroupReservationStatus>(() => groupStatus.value?.status ?? 'Open')
const isOpen = computed(() => status.value === 'Open')
const canSubmit = computed(() => isOpen.value && consolidated.value.items.length > 0 && !submitting.value)
const lastUpdatedLabel = computed(() => formatClock(lastUpdatedAt.value))

const guestsLabel = computed(() => {
  const maxGuests = groupStatus.value?.maxCapacity ?? invite.value?.MaxGuestCount ?? participants.value.length
  return t('orders.guests', { count: participants.value.length, max: maxGuests })
})

const pendingMessage = computed(() => {
  const count = pendingCount.value
  return t('orders.pendingParticipants', { count }, count)
})

// Bumped by every load and every mutation: a response that started before it is stale and ignored,
// so a slow background sync can never resurrect a removed guest or reopen a submitted group.
let generation = 0
let syncTimer: ReturnType<typeof setInterval> | undefined

function stopSync(): void {
  if (syncTimer !== undefined) {
    clearInterval(syncTimer)
    syncTimer = undefined
  }
}

function startSync(): void {
  stopSync() // never two timers: retries and reloads go through here too
  syncTimer = setInterval(() => void refresh(), SYNC_INTERVAL_MS)
}

async function load(): Promise<void> {
  stopSync()
  const current = ++generation
  loadState.value = 'loading'
  syncFailed.value = false
  try {
    const nextInvite = await service.getGroupInvite(props.reservationId)
    const groupId = nextInvite.GroupReservationId
    const [nextSessions, nextOwnerId, nextStatus] = await Promise.all([
      service.getSessions(groupId),
      service.getOwnerSessionId(props.reservationId),
      service.getStatus(groupId),
    ])
    if (current !== generation) return
    invite.value = nextInvite
    sessions.value = nextSessions
    ownerSessionId.value = nextOwnerId
    groupStatus.value = nextStatus
    lastUpdatedAt.value = new Date()
    loadState.value = 'ready'
    if (nextStatus.status === 'Open') startSync()
  } catch (error) {
    if (current !== generation) return
    loadState.value = isApiError(error, 404) ? 'not-found' : 'error'
  }
}

/** Silent sync: no loader, no toasts — the data just changes, or "Couldn't refresh…" appears. */
async function refresh(): Promise<void> {
  const groupId = invite.value?.GroupReservationId
  // exhaustMap semantics: skip the tick while the previous sync (or a mutation) is still running
  if (!groupId || syncing.value || submitting.value || removing.value) return
  const current = generation
  syncing.value = true
  try {
    const [nextSessions, nextStatus] = await Promise.all([
      service.getSessions(groupId, { silent: true }),
      service.getStatus(groupId, { silent: true }),
    ])
    if (current !== generation) return
    sessions.value = nextSessions
    groupStatus.value = nextStatus
    lastUpdatedAt.value = new Date()
    syncFailed.value = false
    if (nextStatus.status !== 'Open') stopSync()
  } catch {
    if (current === generation) syncFailed.value = true
  } finally {
    syncing.value = false
  }
}

function openSubmitDialog(): void {
  if (canSubmit.value) submitDialogOpen.value = true
}

function closeSubmitDialog(): void {
  submitDialogOpen.value = false
}

async function confirmSubmit(): Promise<void> {
  const groupId = invite.value?.GroupReservationId
  if (!groupId || submitting.value || !isOpen.value) return // a double click sends one request
  submitting.value = true
  try {
    await service.submit(groupId, props.reservationId)
    generation++
    stopSync()
    if (groupStatus.value) groupStatus.value = { ...groupStatus.value, status: 'Submitted' }
    toast.success(t('orders.orderSentToast'))
  } catch {
    // The API client already showed the backend's message; the screen stays usable for another try.
  } finally {
    submitting.value = false
    submitDialogOpen.value = false
  }
}

function askRemove(participant: Participant): void {
  if (isOpen.value && participant.type === 'Guest') guestToRemove.value = participant
}

function closeRemoveDialog(): void {
  guestToRemove.value = null
}

async function confirmRemove(): Promise<void> {
  const groupId = invite.value?.GroupReservationId
  const guest = guestToRemove.value
  if (!groupId || !guest || removing.value) return
  removing.value = true
  try {
    // The server answers with the new snapshot; totals and the consolidated order follow via computed().
    sessions.value = await service.removeSession(groupId, guest.id)
    generation++
    lastUpdatedAt.value = new Date()
    toast.success(t('orders.guestRemovedToast', { name: guest.name }))
  } catch {
    // The API client already showed the error toast; the list stays as it was.
  } finally {
    removing.value = false
    guestToRemove.value = null
  }
}

onMounted(load)
watch(() => props.reservationId, load)
onBeforeUnmount(() => {
  stopSync()
  generation++
})
</script>

<style scoped>
.group-order {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
  max-width: 760px;
  margin: 0 auto;
  padding: 32px 24px 56px;
}

.group-order__header {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--bg-green);
}

.group-order__title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
}

.group-order__title {
  margin: 0;
  font-size: 26px;
  font-weight: 500;
  line-height: 40px;
}

.status-badge {
  padding: 2px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  line-height: 20px;
}

.status-badge--open,
.status-badge--closed {
  background: var(--neutral-200);
  color: var(--neutral-700);
}

.status-badge--submitted {
  background: var(--orange-100);
  color: var(--neutral-900);
}

.group-order__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  margin: 0;
  padding: 0;
  list-style: none;
  color: var(--neutral-700);
}

.group-order__meta li {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.group-order__state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 16px;
  text-align: center;
}

.group-order__state-title {
  margin: 0;
  font-size: 20px;
  font-weight: 500;
}

.group-order__state-text {
  margin: 0;
  color: var(--neutral-600);
}

.sync-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.sync-bar__text {
  margin: 0;
  font-size: 13px;
  color: var(--neutral-600);
}

.sync-bar__text--failed {
  color: var(--red-400);
}

.sync-bar__refresh {
  padding: 4px 8px;
  border: none;
  background: none;
  font-family: inherit;
  font-size: 14px;
  font-weight: 500;
  color: var(--green-600);
  text-decoration: underline;
  cursor: pointer;
}

.sync-bar__refresh:disabled {
  color: var(--neutral-400);
  cursor: progress;
}

.pending-banner {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 0;
  padding: 12px 16px;
  border: 1px solid var(--orange-150);
  border-radius: var(--radius-md);
  background: var(--orange-30);
  color: var(--neutral-900);
}

.group-order__participants {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.consolidated {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border-radius: var(--radius-md);
  background: var(--neutral-0);
}

.consolidated__title {
  margin: 0;
  font-size: 18px;
  font-weight: 500;
}

.consolidated__empty {
  margin: 0;
  color: var(--neutral-600);
}

.consolidated__items {
  margin: 0;
  padding: 0;
  list-style: none;
}

.consolidated__item {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 8px 0;
  border-bottom: 1px solid var(--neutral-200);
}

.grand-total {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin: 8px 0 0;
  padding-top: 12px;
  border-top: 2px solid var(--bg-green);
  font-size: 26px;
  font-weight: 500;
  line-height: 40px;
}

.grand-total__value {
  font-weight: 600;
  color: var(--green-600);
}

.group-order__submit {
  width: 100%;
}

.group-order__submit:disabled {
  background: var(--neutral-400);
  color: var(--neutral-0);
  opacity: 1;
}

.dialog-text {
  margin: 0;
}

.remove-confirm {
  border: 2px solid var(--red-400);
  background: var(--neutral-0);
  color: var(--red-400);
}

.remove-confirm:hover:not(:disabled) {
  background: var(--red-30);
}

@media (max-width: 480px) {
  .group-order {
    padding: 24px 16px 40px;
  }

  .grand-total {
    font-size: 22px;
  }
}
</style>
