<template>
  <div class="reservations-page container">
    <div class="page-header flex justify-between items-center">
      <div>
        <h2>{{ t('customer.myReservations') }}</h2>
        <p class="text-muted">{{ t('customer.bookingsIntro') }}</p>
      </div>
      <RouterLink to="/tables" class="button button--primary button--large">
        {{ t('customer.newReservation') }}
      </RouterLink>
    </div>

    <!-- Status tabs -->
    <div class="status-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.value"
        class="status-tab"
        :class="{ 'status-tab--active': activeTab === tab.value }"
        @click="activeTab = tab.value"
      >
        {{ tab.label }}
      </button>
    </div>

    <LoadingSpinner v-if="loading" :text="t('customer.loadingReservations')" />

    <EmptyState
      v-else-if="filteredReservations.length === 0"
      icon="📅"
      :title="t('customer.noReservations')"
      :description="t('customer.noReservationsCategory')"
    />

    <div v-else class="reservations-grid">
      <ReservationCard
        v-for="res in filteredReservations"
        :key="res.id"
        :reservation="res"
      >
        <template #actions>
          <button
            v-if="canChange(res)"
            type="button"
            class="button button--secondary button--small"
            @click="editing = res"
          >
            {{ t('customer.edit') }}
          </button>
          <button
            v-if="canChange(res)"
            type="button"
            class="button button--danger button--small"
            @click="cancelTarget = res"
          >
            {{ t('customer.cancelBookingAction') }}
          </button>
          <p v-if="isUpcoming(res) && !canChange(res)" class="text-muted">{{ t('customer.bookingCutoff') }}</p>
          <button
            v-if="canInvite(res)"
            type="button"
            class="button button--secondary button--small"
            @click="inviteId = res.id"
          >
            {{ t('customer.invite') }}
          </button>
          <button
            v-if="isFinished(res)"
            type="button"
            class="button button--secondary button--small"
            @click="feedbackId = res.id"
          >
            {{ t('customer.feedback') }}
          </button>
          <RouterLink
            v-if="canOpenGroupOrder(res)"
            :to="`/reservations/${res.id}/group-order`"
            class="button button--secondary button--small"
          >
            {{ t('customer.groupPreorder') }}
          </RouterLink>
        </template>
      </ReservationCard>
    </div>

    <EditReservationModal
      v-if="editing"
      :reservation="editing"
      @close="editing = null"
      @saved="editing = null; fetchReservations()"
    />
    <FeedbackWindow v-if="feedbackId" :reservation-id="feedbackId" @close="feedbackId = ''" />
    <ReservationInviteModal v-if="inviteId" :reservation-id="inviteId" @close="inviteId = ''" />

    <AppModal v-if="cancelTarget" :title="t('customer.cancelReservation')" size="sm" @close="cancelTarget = null">
      <p>{{ t('customer.cancelReservationQuestion') }}</p>
      <template #footer>
        <button type="button" class="button button--secondary" @click="cancelTarget = null">{{ t('customer.keep') }}</button>
        <button type="button" class="button button--danger" :disabled="cancelling" @click="confirmCancel">
          {{ t('customer.yesCancel') }}
        </button>
      </template>
    </AppModal>
  </div>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { ref, computed, onMounted } from 'vue'
import ReservationCard from '../components/reservations/ReservationCard.vue'
import LoadingSpinner from '../components/shared/LoadingSpinner.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import AppModal from '../components/shared/AppModal.vue'
import EditReservationModal from '../components/reservations/EditReservationModal.vue'
import FeedbackWindow from '../components/reservations/FeedbackWindow.vue'
import ReservationInviteModal from '../components/reservations/ReservationInviteModal.vue'
import { reservationsApi } from '../services/api'
import { useToast } from '../composables/useToast'
import {
  reservationStatusKey,
  type ReservationCustomer,
  type ReservationStatusKey,
} from '../models/reservations/reservation.model'

type Tab = 'all' | ReservationStatusKey

const toast = useToast()
const reservations = ref<ReservationCustomer[]>([])
const loading = ref(false)
const activeTab = ref<Tab>('all')
const editing = ref<ReservationCustomer | null>(null)
const cancelTarget = ref<ReservationCustomer | null>(null)
const cancelling = ref(false)
const feedbackId = ref('')
const inviteId = ref('')

const tabs = computed<{ label: string; value: Tab }[]>(() => [
  { label: t('customer.all'), value: 'all' },
  { label: t('customer.upcoming'), value: 'reserved' },
  { label: t('customer.inProgress'), value: 'in-progress' },
  { label: t('customer.finished'), value: 'finished' },
  { label: t('customer.cancelled'), value: 'cancelled' },
])

const filteredReservations = computed(() => {
  if (activeTab.value === 'all') return reservations.value
  return reservations.value.filter((reservation) => reservationStatusKey(reservation.status) === activeTab.value)
})

function isUpcoming(reservation: ReservationCustomer): boolean {
  return reservationStatusKey(reservation.status) === 'reserved'
}

function canChange(reservation: ReservationCustomer): boolean {
  return isUpcoming(reservation) && Date.parse(reservation.startTime) > Date.now() + 30 * 60_000
}

function isFinished(reservation: ReservationCustomer): boolean {
  return reservationStatusKey(reservation.status) === 'finished'
}

function canInvite(reservation: ReservationCustomer): boolean {
  return canOpenGroupOrder(reservation) && reservation.guestInviteLinkAvailable === true
}

/** The Owner can open the group pre-order while the reservation is not finished or cancelled. */
function canOpenGroupOrder(reservation: ReservationCustomer): boolean {
  const key = reservationStatusKey(reservation.status)
  return reservation.guestCount > 1 && (key === 'reserved' || key === 'in-progress')
}

async function fetchReservations(): Promise<void> {
  loading.value = true
  try {
    reservations.value = ((await reservationsApi.list()) as unknown as ReservationCustomer[] | null) ?? []
  } catch {
    // the API client has already shown the error toast
  } finally {
    loading.value = false
  }
}

async function confirmCancel(): Promise<void> {
  if (!cancelTarget.value) return
  cancelling.value = true
  try {
    await reservationsApi.cancel(cancelTarget.value.id)
    toast.success(t('customer.reservationCancelled'))
    cancelTarget.value = null
    await fetchReservations()
  } catch {
    // the API client has already shown the error toast
  } finally {
    cancelling.value = false
  }
}

onMounted(fetchReservations)
</script>

<style scoped>
.reservations-page {
  padding-bottom: 56px;
}
.page-header { flex-wrap: wrap; gap: 16px; }

.status-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 24px;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--neutral-200);
  padding-bottom: 0;
}

.status-tab {
  padding: 10px 20px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  font-family: 'Poppins', sans-serif;
  font-size: 14px;
  font-weight: 500;
  color: var(--neutral-400);
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
  margin-bottom: -1px;
}

.status-tab:hover {
  color: var(--green-600);
}

.status-tab--active {
  color: var(--green-600);
  border-bottom-color: var(--green-600);
}

.reservations-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 24px;
}

@media (max-width: 480px) {
  .reservations-grid {
    grid-template-columns: 1fr;
  }
}
</style>

