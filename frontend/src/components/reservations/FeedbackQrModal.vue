<template>
  <AppModal :title="t('customer.feedbackQr')" size="sm" @close="emit('close')">
    <div class="qr">
      <p>{{ t('customer.scanFeedback') }}</p>
      <img v-if="dataUrl" :src="dataUrl" :alt="t('customer.feedbackQrAlt')" class="qr__img" />
      <p v-else-if="failed" class="text-muted">{{ t('customer.qrError') }}</p>
      <code class="qr__url">{{ url }}</code>
    </div>
  </AppModal>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { onMounted, ref } from 'vue'
import QRCode from 'qrcode'
import { reservationsApi } from '@/services/api'
import AppModal from '../shared/AppModal.vue'

const props = defineProps<{ reservationId: string }>()
const emit = defineEmits<{ close: [] }>()
const dataUrl = ref('')
const failed = ref(false)

const url = ref('')

onMounted(async () => {
  try {
    const { token } = await reservationsApi.feedbackToken(props.reservationId)
    url.value = `${window.location.origin}/feedback?${new URLSearchParams({ reservationId: props.reservationId, token })}`
    dataUrl.value = await QRCode.toDataURL(url.value, { width: 240, margin: 1 })
  } catch {
    failed.value = true
  }
})
</script>

<style scoped>
.qr { display: flex; flex-direction: column; align-items: center; gap: 12px; text-align: center; }
.qr__img { width: 240px; height: 240px; }
.qr__url { font-size: 12px; word-break: break-all; }
</style>
