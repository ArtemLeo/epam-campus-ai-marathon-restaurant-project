<template>
  <AppModal :title="t('customer.reservationConfirmed')" @close="emit('close')">
    <p>{{ t('customer.bookedAt', { address: reservation.locationAddress, count: reservation.guestCount }, reservation.guestCount) }}</p>
    <template v-if="reservation.guestCount >= 2">
      <p class="text-muted">{{ t('customer.shareInvite') }}</p>
      <LoadingSpinner v-if="loading" :text="t('customer.creatingInvite')" />
      <p v-else-if="failed" class="text-muted">{{ t('customer.inviteLater') }}</p>
      <div v-else class="invite">
        <input :value="link" readonly class="invite__input" :aria-label="t('customer.inviteLink')" />
        <AppButton size="small" @click="copy">{{ t(copied ? 'customer.copied' : 'customer.copy') }}</AppButton>
      </div>
    </template>
    <template #footer>
      <AppButton @click="emit('close')">{{ t('customer.done') }}</AppButton>
    </template>
  </AppModal>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { ref, onMounted } from 'vue'
import AppModal from '../shared/AppModal.vue'
import AppButton from '../shared/AppButton.vue'
import LoadingSpinner from '../shared/LoadingSpinner.vue'
import { reservationsApi } from '../../services/api'
import type { Reservation } from '../../services/api/types'

const props = defineProps<{ reservation: Reservation }>()
const emit = defineEmits<{ close: [] }>()

const link = ref('')
const loading = ref(props.reservation.guestCount >= 2)
const failed = ref(false)
const copied = ref(false)

onMounted(async () => {
  if (props.reservation.guestCount < 2) return
  try {
    const { token } = await reservationsApi.inviteToken(props.reservation.id)
    link.value = `${window.location.origin}/join/${token}`
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
})

async function copy() {
  try {
    await navigator.clipboard.writeText(link.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  } catch {
    copied.value = false
  }
}
</script>

<style scoped>
.invite {
  display: flex;
  gap: 8px;
}
.invite__input {
  flex: 1;
  padding: 8px 12px;
  border: 1.5px solid var(--neutral-200);
  border-radius: var(--radius-md);
  font-size: 13px;
}
</style>
