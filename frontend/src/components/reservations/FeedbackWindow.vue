<template>
  <AppModal :title="t('customer.yourFeedback')" @close="emit('close')">
    <LoadingSpinner v-if="loading" :text="t('customer.loadingFeedback')" />
    <div v-else class="feedback">
      <section v-for="section in sections" :key="section.type" class="feedback__section">
        <h4>{{ section.label }}</h4>
        <div class="feedback__stars" role="radiogroup" :aria-label="t('customer.ratingFor', { type: section.label })">
          <button
            v-for="n in 5"
            :key="n"
            type="button"
            class="feedback__star"
            :class="{ 'feedback__star--on': n <= forms[section.type].rating }"
            :aria-label="t('customer.stars', { count: n }, n)"
            @click="forms[section.type].rating = n"
          >
            ★
          </button>
        </div>
        <textarea v-model="forms[section.type].comment" rows="3" :placeholder="t('customer.commentOptional')" />
        <button
          type="button"
          class="button button--primary button--small"
          :disabled="saving || forms[section.type].rating < 1"
          @click="save(section.type)"
        >
          {{ t(forms[section.type].exists ? 'customer.update' : 'customer.submit') }}
        </button>
      </section>
    </div>
  </AppModal>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { onMounted, computed, reactive, ref } from 'vue'
import AppModal from '../shared/AppModal.vue'
import LoadingSpinner from '../shared/LoadingSpinner.vue'
import { feedbackApi, reservationsApi, type Feedback, type FeedbackTypeCode } from '../../services/api'
import { useToast } from '../../composables/useToast'

const props = defineProps<{ reservationId: string }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const toast = useToast()

const sections = computed<{ type: FeedbackTypeCode; label: string }[]>(() => [
  { type: 0, label: t('customer.service') },
  { type: 1, label: t('customer.cuisineExperience') },
])
const loading = ref(true)
const saving = ref(false)
const forms = reactive<Record<FeedbackTypeCode, { rating: number; comment: string; exists: boolean }>>({
  0: { rating: 0, comment: '', exists: false },
  1: { rating: 0, comment: '', exists: false },
})

function fill(type: FeedbackTypeCode, feedback: Feedback | null): void {
  if (!feedback) return
  forms[type] = { rating: feedback.rating, comment: feedback.comment ?? '', exists: true }
}

async function save(type: FeedbackTypeCode): Promise<void> {
  const form = forms[type]
  const body = {
    reservationId: props.reservationId,
    rating: form.rating,
    type,
    comment: form.comment.trim() || null,
  }
  saving.value = true
  try {
    if (form.exists) await feedbackApi.update(body)
    else await feedbackApi.create(body)
    form.exists = true
    toast.success(t('customer.feedbackSaved'))
    emit('saved')
  } catch {
    // the API client has already shown the error toast
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const data = await reservationsApi.feedback(props.reservationId)
    fill(0, data.service)
    fill(1, data.cuisineExperience)
  } catch {
    // the API client has already shown the error toast
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.feedback { display: flex; flex-direction: column; gap: 20px; }
.feedback__section { display: flex; flex-direction: column; gap: 8px; align-items: flex-start; }
.feedback__section h4 { margin: 0; }
.feedback__stars { display: flex; gap: 2px; }
.feedback__star { background: none; border: none; font-size: 26px; color: var(--neutral-200); cursor: pointer; padding: 0 2px; }
.feedback__star--on { color: #f5a623; }
.feedback textarea {
  width: 100%; padding: 10px 12px; border: 1px solid var(--neutral-200); border-radius: var(--radius-md); font: inherit; resize: vertical;
}
</style>
