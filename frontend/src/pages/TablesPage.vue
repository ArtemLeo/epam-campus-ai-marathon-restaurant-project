<template>
  <div class="tables-page container">
    <div class="page-header">
      <h2>{{ t('customer.bookTable') }}</h2>
      <p class="text-muted">{{ t('customer.tableIntro', { timezone: RESTAURANT_TIMEZONE }) }}</p>
    </div>

    <div class="tables-controls">
      <div class="filter-row">
        <label class="form-label" for="loc">{{ t('customer.location') }}</label>
        <select id="loc" v-model="locationId" class="app-select filter-select">
          <option v-for="loc in locations" :key="loc.id" :value="loc.id">{{ loc.address }}</option>
        </select>
      </div>
      <div class="filter-row">
        <label class="form-label" for="date">{{ t('customer.date') }}</label>
        <input id="date" v-model="date" type="date" :min="today" class="app-select" />
      </div>
      <div class="filter-row">
        <label class="form-label" for="cap">{{ t('customer.guests') }}</label>
        <select id="cap" v-model="capacity" class="app-select filter-select">
          <option value="">{{ t('customer.any') }}</option>
          <option v-for="n in [1, 2, 4, 6, 8]" :key="n" :value="String(n)">{{ n }}+</option>
        </select>
      </div>
    </div>

    <LoadingSpinner v-if="loading" :text="t('customer.loadingTables')" />
    <EmptyState
      v-else-if="tables.length === 0"
      icon="🪑"
      :title="t('customer.noTables')"
      :description="t('customer.tryOtherTable')"
    />
    <div v-else class="tables-grid">
      <TableCard v-for="table in tables" :key="table.id" :table="{ ...table, available: true }">
        <template #action>
          <button type="button" class="button button--primary button--small button--full-width" @click="pickTable(table)">
            {{ t('customer.viewSlots') }}
          </button>
        </template>
      </TableCard>
    </div>

    <TimeSlotsModal v-if="selectedTable && !selectedSlot" :table="selectedTable" :date="date" @close="selectedTable = null" @select="selectedSlot = $event" />
    <MakeReservationModal
      v-if="selectedTable && selectedSlot"
      :table="selectedTable"
      :time-slot="selectedSlot"
      :initial-guests="capacity ? Number(capacity) : 1"
      @close="selectedSlot = null"
      @booked="onBooked"
    />
    <ReservationConfirmedModal v-if="confirmed" :reservation="confirmed" @close="confirmed = null" />
  </div>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { bookingSearchStart, restaurantToday, RESTAURANT_TIMEZONE } from '@/utils/date-time'
import TableCard from '../components/tables/TableCard.vue'
import TimeSlotsModal from '../components/tables/TimeSlotsModal.vue'
import MakeReservationModal from '../components/tables/MakeReservationModal.vue'
import ReservationConfirmedModal from '../components/tables/ReservationConfirmedModal.vue'
import LoadingSpinner from '../components/shared/LoadingSpinner.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import { locationsApi, tablesApi } from '../services/api'
import { useToast } from '../composables/useToast'
import type { Location, Reservation, Table, TimeSlot } from '../services/api/types'

const route = useRoute()
const today = restaurantToday()
const locations = ref<Location[]>([])
const tables = ref<Table[]>([])
const locationId = ref('')
const date = ref(today)
const capacity = ref('')
const loading = ref(false)
const selectedTable = ref<Table | null>(null)
const selectedSlot = ref<TimeSlot | null>(null)
const confirmed = ref<Reservation | null>(null)

let requestSeq = 0
async function loadTables() {
  if (!locationId.value || !date.value) return
  const seq = ++requestSeq
  loading.value = true
  try {
    const result = await tablesApi.available({
      locationId: locationId.value,
      capacity: capacity.value ? Number(capacity.value) : undefined,
      startTime: bookingSearchStart(date.value),
    })
    if (seq === requestSeq) tables.value = result ?? []
  } catch {
    if (seq !== requestSeq) return
    tables.value = []
    // The API client already displays the failure.
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

function pickTable(table: Table) {
  selectedSlot.value = null
  selectedTable.value = table
}

function onBooked(reservation: Reservation) {
  selectedTable.value = null
  selectedSlot.value = null
  confirmed.value = reservation
  useToast().success(t('customer.reservationCreated'))
  loadTables()
}

watch([locationId, date, capacity], loadTables)

onMounted(async () => {
  try {
    locations.value = (await locationsApi.list()) ?? []
    const requested = String(route.query.locationId ?? '')
    locationId.value = locations.value.find(loc => loc.id === requested)?.id ?? locations.value[0]?.id ?? ''
  } catch {
    // The API client already displays the failure.
  }
})
</script>

<style scoped>
.tables-page {
  padding-bottom: 56px;
}

.tables-controls {
  display: flex;
  gap: 24px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.app-select {
  padding: 8px 14px;
  border: 1.5px solid var(--neutral-200);
  border-radius: var(--radius-md);
  font-family: 'Poppins', sans-serif;
  font-size: 14px;
  color: var(--neutral-900);
  background: var(--neutral-0);
  outline: none;
  transition: border-color 0.15s;
}

.app-select:focus {
  border-color: var(--green-400);
}

.filter-select {
  min-width: 140px;
}

.tables-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 24px;
}
</style>

