<template>
  <AppModal :title="t('customer.editReservation')" size="sm" @close="emit('close')">
    <form id="edit-reservation-form" class="edit-form" @submit.prevent="submit">
      <label class="edit-form__field">
        <span>{{ t('customer.date') }}</span>
        <input v-model="date" type="date" :min="today" required />
      </label>
      <label class="edit-form__field">
        <span>{{ t('customer.timeInZone', { timezone: RESTAURANT_TIMEZONE }) }}</span>
        <select v-model="time" required>
          <option v-for="slot in slots" :key="slot" :value="slot">{{ slot }}</option>
        </select>
      </label>
      <label class="edit-form__field">
        <span>{{ t('customer.guests') }}</span>
        <input v-model.number="guestCount" type="number" min="1" :max="maxGuests" required />
      </label>
      <p class="text-muted">{{ t('customer.editAvailability') }}</p>
      <p v-if="error" class="edit-form__error" role="alert">{{ t(error) }}</p>
    </form>
    <template #footer>
      <button type="button" class="button button--secondary" @click="emit('close')">{{ t('customer.close') }}</button>
      <button type="submit" form="edit-reservation-form" class="button button--primary" :disabled="saving">
        {{ t(saving ? 'customer.saving' : 'customer.save') }}
      </button>
    </template>
  </AppModal>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { ref } from 'vue'
import { dateTimeParts, restaurantToday, restaurantDateTimeToIso, RESTAURANT_TIMEZONE } from '@/utils/date-time'
import AppModal from '../shared/AppModal.vue'
import { reservationsApi } from '../../services/api'
import { useToast } from '../../composables/useToast'
import type { ReservationCustomer } from '../../models/reservations/reservation.model'

const props = defineProps<{ reservation: ReservationCustomer; maxGuests?: number }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const toast = useToast()

const SLOT_MINUTES = 90
const slots = Array.from({ length: 22 }, (_, i) => `${String(10 + Math.floor(i / 2)).padStart(2, '0')}:${i % 2 ? '30' : '00'}`)
const today = restaurantToday()

const iso = props.reservation.startTime
const date = ref(dateTimeParts(iso).date)
const time = ref(dateTimeParts(iso).time)
const guestCount = ref(props.reservation.guestCount)
const saving = ref(false)
const error = ref('')

async function submit(): Promise<void> {
  if (!date.value || !time.value || !(guestCount.value > 0)) {
    error.value = 'customer.fillBooking'
    return
  }
  const instant = restaurantDateTimeToIso(date.value, time.value)
  if (!instant) { error.value = 'customer.ambiguousTime'; return }
  const start = new Date(instant)
  if (start.getTime() < Date.now()) {
    error.value = 'customer.futureStart'
    return
  }
  const end = new Date(start.getTime() + SLOT_MINUTES * 60_000)
  saving.value = true
  error.value = ''
  try {
    await reservationsApi.edit({
      reservationId: props.reservation.id,
      startTime: start.toISOString(),
      endTime: end.toISOString(),
      guestCount: guestCount.value,
    })
    toast.success(t('customer.reservationUpdated'))
    emit('saved')
  } catch {
    // the API client has already shown the error toast
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.edit-form { display: flex; flex-direction: column; gap: 14px; }
.edit-form__field { display: flex; flex-direction: column; gap: 6px; font-size: 14px; font-weight: 500; }
.edit-form__field input, .edit-form__field select {
  padding: 10px 12px; border: 1px solid var(--neutral-200); border-radius: var(--radius-md); font: inherit;
}
.edit-form__error { color: var(--red-600, #c62828); margin: 0; font-size: 13px; }
</style>
