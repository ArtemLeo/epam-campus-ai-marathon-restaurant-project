<template>
  <AppModal :title="t('customer.confirmReservation')" @close="emit('close')">
    <dl class="summary">
      <dt>{{ t('customer.table') }}</dt><dd>#{{ table.tableNumber }}</dd>
      <dt>{{ t('customer.timezone') }}</dt><dd>{{ RESTAURANT_TIMEZONE }}</dd>
      <dt>{{ t('customer.date') }}</dt><dd>{{ day }}</dd>
      <dt>{{ t('customer.start') }}</dt><dd>{{ time(timeSlot.start) }}</dd>
      <dt>{{ t('customer.end') }}</dt><dd>{{ time(timeSlot.end) }}</dd>
    </dl>
    <label class="form-label" for="guest-count">{{ t('customer.maxGuests', { count: table.capacity }) }}</label>
    <input id="guest-count" v-model.number="guestCount" type="number" min="1" :max="table.capacity" class="guest-input" />
    <p v-if="error" class="error">{{ error.startsWith('customer.') ? t(error) : translateApiMessage(error) }}</p>
    <template #footer>
      <AppButton variant="secondary" @click="emit('close')">{{ t('customer.cancel') }}</AppButton>
      <AppButton :loading="submitting" :disabled="!valid" @click="submit">{{ t('customer.confirm') }}</AppButton>
    </template>
  </AppModal>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { translateApiMessage } from '@/i18n/errors'
import { ref, computed } from 'vue'
import { RESTAURANT_TIMEZONE } from '@/utils/date-time'
import { formatMediumDate, formatTime } from '@/utils/formatters'
import AppModal from '../shared/AppModal.vue'
import AppButton from '../shared/AppButton.vue'
import { reservationsApi } from '../../services/api'
import type { Reservation, Table, TimeSlot } from '../../services/api/types'

const props = defineProps<{ table: Table; timeSlot: TimeSlot; initialGuests?: number }>()
const emit = defineEmits<{ close: []; booked: [reservation: Reservation] }>()

const guestCount = ref(Math.min(props.initialGuests ?? 1, props.table.capacity) || 1)
const submitting = ref(false)
const error = ref('')

const day = computed(() => formatMediumDate(props.timeSlot.start))
const time = formatTime
const valid = computed(
  () => Number.isInteger(guestCount.value) && guestCount.value >= 1 && guestCount.value <= props.table.capacity,
)

async function submit() {
  if (!valid.value) return
  submitting.value = true
  error.value = ''
  try {
    const reservation = await reservationsApi.create({
      tableId: props.table.id,
      startTime: props.timeSlot.start,
      endTime: props.timeSlot.end,
      guestCount: guestCount.value,
    })
    emit('booked', reservation)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'customer.createReservationError'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.summary {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 6px 16px;
  margin: 0 0 16px;
}
.summary dt {
  color: var(--neutral-500, #666);
}
.summary dd {
  margin: 0;
  font-weight: 600;
}
.guest-input {
  width: 100%;
  padding: 8px 14px;
  border: 1.5px solid var(--neutral-200);
  border-radius: var(--radius-md);
  font-family: 'Poppins', sans-serif;
  font-size: 14px;
  box-sizing: border-box;
}
.error {
  color: var(--red-500, #d33);
  margin-top: 8px;
}
</style>
