<template>
  <AppModal :title="t('customer.tableSlots', { number: table.tableNumber })" @close="emit('close')">
    <p class="text-muted">{{ t('customer.slotsIntro', { date: displayDate, count: table.capacity, timezone: RESTAURANT_TIMEZONE }) }}</p>
    <LoadingSpinner v-if="loading" :text="t('customer.loadingSlots')" />
    <EmptyState v-else-if="slots.length === 0" icon="🕒" :title="t('customer.noSlots')" :description="t('customer.tryAnotherDay')" />
    <div v-else class="slots">
      <button v-for="slot in slots" :key="slot.start" type="button" class="slot" @click="emit('select', slot)">
        {{ fmt(slot.start) }} - {{ fmt(slot.end) }}
      </button>
    </div>
  </AppModal>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { ref, computed, onMounted } from 'vue'
import AppModal from '../shared/AppModal.vue'
import LoadingSpinner from '../shared/LoadingSpinner.vue'
import EmptyState from '../shared/EmptyState.vue'
import { tablesApi } from '../../services/api'
import { bookingSearchStart, restaurantDateTimeToIso, RESTAURANT_TIMEZONE } from '@/utils/date-time'
import { formatMediumDate, formatTime } from '@/utils/formatters'
import type { Table, TimeSlot } from '../../services/api/types'

const props = defineProps<{ table: Table; date: string }>()
const displayDate = computed(() => formatMediumDate(restaurantDateTimeToIso(props.date, '12:00')))
const emit = defineEmits<{ close: []; select: [slot: TimeSlot] }>()

const slots = ref<TimeSlot[]>([])
const loading = ref(true)

function fmt(iso: string): string {
  return formatTime(iso)
}

onMounted(async () => {
  try {
    slots.value = (await tablesApi.timeSlots(props.table.id, bookingSearchStart(props.date))) ?? []
  } catch {
    // The API client displays the failure.
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.slots {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px;
  margin-top: 12px;
}
.slot {
  padding: 10px;
  border: 1.5px solid var(--neutral-200);
  border-radius: var(--radius-md);
  background: var(--neutral-0);
  font-family: 'Poppins', sans-serif;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.slot:hover {
  border-color: var(--green-400);
  background: var(--green-50, var(--neutral-0));
}
</style>
