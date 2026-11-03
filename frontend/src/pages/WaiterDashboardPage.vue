<template>
  <div class="waiter-page container">
    <div class="page-header">
      <div>
        <h2>{{ t('staff.waiterTitle') }}</h2>
        <p class="text-muted">{{ t('staff.waiterSubtitle') }}</p>
      </div>
      <button type="button" class="button button--primary" @click="walkInOpen = true">+ {{ t('staff.walkIn') }}</button>
    </div>

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

    <div class="filters">
      <label>{{ t('staff.date') }} <input v-model="dateFilter" type="date" /></label>
      <label>
        {{ t('staff.table') }}
        <select v-model="tableFilter">
          <option value="">{{ t('staff.allTables') }}</option>
          <option v-for="table in tables" :key="table.id" :value="table.id">{{ tableLabel(table, false) }}</option>
        </select>
      </label>
      <button v-if="dateFilter || tableFilter" type="button" class="button button--secondary button--small" @click="dateFilter = ''; tableFilter = ''">
        {{ t('staff.clear') }}
      </button>
    </div>

    <LoadingSpinner v-if="loading" :text="t('staff.loadingReservations')" />

    <EmptyState
      v-else-if="filteredReservations.length === 0"
      icon="📋"
      :title="t('staff.noReservations')"
      :description="t('staff.noMatchingReservations')"
    />

    <div v-else class="reservations-grid">
      <ReservationCard v-for="res in filteredReservations" :key="res.id" :reservation="res">
        <template #actions>
          <button
            v-if="key(res) === 'reserved'"
            class="button button--primary button--small"
            @click="setStatus(res.id, 2)"
          >
            {{ t('staff.markInProgress') }}
          </button>
          <button
            v-if="key(res) === 'in-progress'"
            class="button button--secondary button--small"
            @click="setStatus(res.id, 3)"
          >
            {{ t('staff.complete') }}
          </button>
          <button
            v-if="key(res) === 'reserved' || key(res) === 'in-progress'"
            class="button button--danger button--small"
            @click="setStatus(res.id, 1)"
          >
            {{ t('staff.cancel') }}
          </button>
          <select
            v-if="key(res) === 'reserved' || key(res) === 'in-progress'"
            class="table-select"
            :value="res.tableId"
            :aria-label="t('staff.changeTable')"
            @change="changeTable(res, ($event.target as HTMLSelectElement).value)"
          >
            <option v-for="table in tables" :key="table.id" :value="table.id" :disabled="table.capacity < res.guestCount">
              {{ tableLabel(table) }}
            </option>
          </select>
          <RouterLink
            :to="`/waiter-pre-order?reservationId=${res.id}`"
            class="button button--secondary button--small"
          >
            {{ t('staff.preOrder') }}
          </RouterLink>
          <button
            v-if="key(res) === 'finished'"
            class="button button--secondary button--small"
            @click="qrId = res.id"
          >
            {{ t('staff.feedbackQr') }}
          </button>
        </template>
      </ReservationCard>
    </div>

    <FeedbackQrModal v-if="qrId" :reservation-id="qrId" @close="qrId = ''" />

    <AppModal v-if="walkInOpen" :title="t('staff.walkIn')" size="sm" @close="walkInOpen = false">
      <form id="walk-in-form" class="form" @submit.prevent="createWalkIn">
        <label class="form-field">
          {{ t('staff.table') }}
          <select v-model="walkIn.tableId" required>
            <option value="" disabled>{{ t('staff.selectTable') }}</option>
            <option v-for="table in tables" :key="table.id" :value="table.id">{{ tableLabel(table) }}</option>
          </select>
        </label>
        <label class="form-field">{{ t('staff.date') }} <input v-model="walkIn.date" type="date" required /></label>
        <label class="form-field">{{ t('staff.time', { timezone: RESTAURANT_TIMEZONE }) }} <input v-model="walkIn.time" type="time" required /></label>
        <label class="form-field">{{ t('staff.guests') }} <input v-model.number="walkIn.guestCount" type="number" min="1" required /></label>
        <label class="form-field">{{ t('staff.optionalCustomerEmail') }} <input v-model="walkIn.email" type="email" /></label>
        <p v-if="walkInError" class="form-error" role="alert">{{ t(walkInError) }}</p>
      </form>
      <template #footer>
        <button type="button" class="button button--secondary" @click="walkInOpen = false">{{ t('staff.close') }}</button>
        <button type="submit" form="walk-in-form" class="button button--primary" :disabled="walkInSaving">{{ t('staff.create') }}</button>
      </template>
    </AppModal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { t } from '@/i18n'
import { dateTimeParts, restaurantDateTimeToIso, RESTAURANT_TIMEZONE } from '@/utils/date-time'
import ReservationCard from '../components/reservations/ReservationCard.vue'
import FeedbackQrModal from '../components/reservations/FeedbackQrModal.vue'
import LoadingSpinner from '../components/shared/LoadingSpinner.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import AppModal from '../components/shared/AppModal.vue'
import { reservationsApi, waitersApi, locationsApi, type ReservationStatusCode, type Table } from '../services/api'
import { useAuthStore } from '../stores/auth'
import { useToast } from '../composables/useToast'
import { reservationStatusKey, type ReservationCustomer, type ReservationStatusKey } from '../models/reservations/reservation.model'

type Tab = 'all' | ReservationStatusKey

const toast = useToast()
const auth = useAuthStore()
const reservations = ref<ReservationCustomer[]>([])
const tables = ref<Table[]>([])
const loading = ref(false)
const activeTab = ref<Tab>('all')
const dateFilter = ref('')
const tableFilter = ref('')
const qrId = ref('')
const walkInOpen = ref(false)
const walkInSaving = ref(false)
const walkInError = ref('')
const walkIn = reactive({ tableId: '', date: '', time: '', guestCount: 2, email: '' })

const tabs = computed<{ label: string; value: Tab }[]>(() => [
  { label: t('staff.all'), value: 'all' },
  { label: t('staff.upcoming'), value: 'reserved' },
  { label: t('staff.inProgress'), value: 'in-progress' },
  { label: t('staff.finished'), value: 'finished' },
  { label: t('staff.cancelled'), value: 'cancelled' },
])
function tableLabel(table: Table, showSeats = true): string {
  return t(showSeats ? 'staff.tableSeats' : 'staff.tableOption', { number: table.tableNumber, count: table.capacity })
}

function key(reservation: ReservationCustomer): ReservationStatusKey | null {
  return reservationStatusKey(reservation.status)
}

const filteredReservations = computed(() =>
  reservations.value.filter(
    (r) =>
      (activeTab.value === 'all' || key(r) === activeTab.value) &&
      (!dateFilter.value || dateTimeParts(r.startTime).date === dateFilter.value) &&
      (!tableFilter.value || r.tableId === tableFilter.value),
  ),
)

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

async function fetchTables(): Promise<void> {
  if (!auth.user?.id) return
  try {
    const { locationId } = await waitersApi.location(auth.user.id)
    tables.value = (await locationsApi.tables(locationId)) ?? []
  } catch {
    // the API client has already shown the error toast
  }
}

async function setStatus(id: string, status: ReservationStatusCode): Promise<void> {
  try {
    await reservationsApi.updateStatus(id, status)
    toast.success(t('staff.reservationUpdated'))
    await fetchReservations()
  } catch {
    // the API client has already shown the error toast
  }
}

async function changeTable(res: ReservationCustomer, tableId: string): Promise<void> {
  if (tableId === res.tableId) return
  try {
    await reservationsApi.changeTable(res.id, tableId)
    toast.success(t('staff.tableChanged'))
  } catch {
    // the API client has already shown the error toast
  }
  await fetchReservations()
}

async function createWalkIn(): Promise<void> {
  const instant = restaurantDateTimeToIso(walkIn.date, walkIn.time)
  const start = new Date(instant ?? NaN)
  if (!walkIn.tableId || Number.isNaN(start.getTime()) || !(walkIn.guestCount > 0)) {
    walkInError.value = 'staff.completeWalkIn'
    return
  }
  walkInSaving.value = true
  walkInError.value = ''
  try {
    await reservationsApi.create({
      tableId: walkIn.tableId,
      startTime: start.toISOString(),
      endTime: new Date(start.getTime() + 90 * 60_000).toISOString(),
      guestCount: walkIn.guestCount,
      customerEmail: walkIn.email.trim() || null,
    })
    toast.success(t('staff.reservationCreated'))
    walkInOpen.value = false
    await fetchReservations()
  } catch {
    // the API client has already shown the error toast
  } finally {
    walkInSaving.value = false
  }
}

onMounted(() => {
  void fetchReservations()
  void fetchTables()
})
</script>

<style scoped>
.waiter-page {
  padding-bottom: 56px;
}

.status-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 24px;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--neutral-200);
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

.status-tab:hover { color: var(--green-600); }

.status-tab--active {
  color: var(--green-600);
  border-bottom-color: var(--green-600);
}

.reservations-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 340px), 1fr));
  gap: 24px;
}

.filters { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end; margin-bottom: 20px; }
.filters label, .form-field { display: flex; flex-direction: column; gap: 4px; font-size: 13px; font-weight: 500; }
.filters input, .filters select, .form-field input, .form-field select, .table-select {
  padding: 8px 10px; border: 1px solid var(--neutral-200); border-radius: var(--radius-md); font: inherit;
}
.form { display: flex; flex-direction: column; gap: 14px; }
.form-error { color: var(--red-600, #c62828); margin: 0; font-size: 13px; }
.page-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
</style>
