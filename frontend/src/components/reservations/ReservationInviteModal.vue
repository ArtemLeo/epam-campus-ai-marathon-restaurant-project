<template>
  <AppModal :title="t('customer.inviteGuests')" size="sm" @close="emit('close')">
    <LoadingSpinner v-if="loading" :text="t('customer.loadingInvite')" />
    <div v-else-if="link" class="invite">
      <p>{{ t('customer.shareGroupInvite') }}</p>
      <div class="invite__link">
        <code>{{ link }}</code>
        <button type="button" class="button button--secondary button--small" @click="copy">{{ t('customer.copy') }}</button>
      </div>
    </div>
    <p v-else class="text-muted">{{ t('customer.inviteUnavailable') }}</p>
  </AppModal>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { computed, onMounted, ref } from 'vue'
import AppModal from '../shared/AppModal.vue'
import LoadingSpinner from '../shared/LoadingSpinner.vue'
import { reservationsApi } from '../../services/api'
import { useToast } from '../../composables/useToast'

const props = defineProps<{ reservationId: string }>()
const emit = defineEmits<{ close: [] }>()
const toast = useToast()
const token = ref('')
const loading = ref(true)

const link = computed(() => (token.value ? `${window.location.origin}/join/${token.value}` : ''))

async function copy(): Promise<void> {
  try {
    await navigator.clipboard.writeText(link.value)
    toast.success(t('customer.linkCopied'))
  } catch {
    toast.error(t('customer.copyError'))
  }
}

onMounted(async () => {
  try {
    token.value = (await reservationsApi.inviteToken(props.reservationId)).token ?? ''
  } catch {
    // the API client has already shown the error toast
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.invite { display: flex; flex-direction: column; gap: 12px; }
.invite__link {
  display: flex; align-items: center; gap: 10px; background: var(--neutral-100);
  padding: 10px 14px; border-radius: var(--radius-md); word-break: break-all;
}
.invite__link code { flex: 1; font-size: 13px; }
</style>
