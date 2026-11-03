<template>
  <div class="feedback-page">
    <div class="container">
      <h1>{{ t('customer.leaveFeedback') }}</h1>
      <p class="text-muted">{{ t('customer.feedbackIntro') }}</p>

      <div v-if="!reservationId" class="error-msg">
        <p>{{ t('customer.missingReservation') }}</p>
      </div>

      <div v-else-if="submitted" class="success-card">
        <div class="success-icon">&#10003;</div>
        <h2>{{ t('customer.thankYou') }}</h2>
        <p>{{ t('customer.feedbackSubmitted') }}</p>
      </div>

      <form v-else class="feedback-form" @submit.prevent="submitFeedback">
        <div class="form-group">
          <label>{{ t('customer.feedbackType') }}</label>
          <div class="radio-group">
            <label class="radio-label">
              <input v-model.number="form.type" type="radio" :value="0" /> {{ t('customer.service') }}
            </label>
            <label class="radio-label">
              <input v-model.number="form.type" type="radio" :value="1" /> {{ t('customer.cuisineExperienceLabel') }}
            </label>
          </div>
        </div>

        <div class="form-group">
          <label>{{ t('customer.rating') }}</label>
          <div class="stars">
            <button
              v-for="star in 5"
              :key="star"
              type="button"
              class="star"
              :class="{ 'star--filled': star <= form.rating }"
              :aria-label="t('customer.stars', { count: star }, star)"
              @click="form.rating = star"
            >
              &#9733;
            </button>
          </div>
        </div>

        <div class="form-group">
          <label for="feedback-comment">{{ t('customer.commentOptional') }}</label>
          <textarea id="feedback-comment" v-model="form.comment" rows="4" :placeholder="t('customer.commentPlaceholder')" />
        </div>

        <button type="submit" class="button button--primary" :disabled="submitting || form.rating === 0">
          {{ t(submitting ? 'customer.submitting' : 'customer.submitFeedback') }}
        </button>

        <p v-if="error" class="error-msg">{{ error.startsWith('customer.') ? t(error) : translateApiMessage(error) }}</p>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { translateApiMessage } from '@/i18n/errors'
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { feedbackApi } from '@/services/api'
import type { FeedbackTypeCode } from '@/services/api/types'

const route = useRoute()
const reservationId = computed(() => (route.query.reservationId as string) || '')

const form = ref<{ type: FeedbackTypeCode; rating: number; comment: string }>({
  type: 0,
  rating: 0,
  comment: '',
})

const submitting = ref(false)
const submitted = ref(false)
const error = ref('')

async function submitFeedback() {
  if (!reservationId.value || form.value.rating === 0) return
  submitting.value = true
  error.value = ''
  try {
    await feedbackApi.create({
      reservationId: reservationId.value,
      token: typeof route.query.token === 'string' ? route.query.token : undefined,
      rating: form.value.rating,
      type: form.value.type,
      comment: form.value.comment || undefined,
    })
    submitted.value = true
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : 'customer.feedbackError'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.feedback-page {
  padding: 48px 0;
  min-height: 70vh;
}

.container {
  max-width: 520px;
  margin: 0 auto;
  padding: 0 16px;
}

h1 { margin: 0 0 4px; font-size: 24px; color: var(--neutral-900); }
.text-muted { color: var(--neutral-500); margin: 0 0 32px; }

.feedback-form { display: flex; flex-direction: column; gap: 24px; }

.form-group { display: flex; flex-direction: column; gap: 8px; }
.form-group > label { font-size: 14px; font-weight: 500; color: var(--neutral-700); }
.form-group textarea {
  padding: 10px 14px;
  border: 1px solid var(--neutral-300);
  border-radius: var(--radius-md);
  font-size: 14px;
  resize: vertical;
}

.radio-group { display: flex; flex-wrap: wrap; gap: 20px; }
.radio-label { display: flex; align-items: center; gap: 6px; font-size: 14px; cursor: pointer; }

.stars { display: flex; gap: 4px; }
.star {
  background: none; border: none; font-size: 32px; cursor: pointer;
  color: var(--neutral-300); transition: color 0.1s;
}
.star--filled { color: var(--amber-400); }
.star:hover { color: var(--amber-300); }

.button { padding: 10px 20px; border: none; border-radius: var(--radius-md); font-size: 14px; font-weight: 500; cursor: pointer; }
.button--primary { background: var(--green-500); color: white; }
.button--primary:hover { background: var(--green-600); }
.button:disabled { opacity: 0.6; cursor: not-allowed; }

.error-msg { color: var(--red-600); font-size: 14px; }

.success-card {
  text-align: center;
  padding: 48px 24px;
  border: 1px solid var(--green-200);
  border-radius: var(--radius-xl);
  background: var(--green-50);
}
.success-icon { font-size: 48px; color: var(--green-500); margin-bottom: 16px; }
.success-card h2 { margin: 0 0 8px; color: var(--green-700); }
.success-card p { margin: 0; color: var(--green-600); }
</style>
