<template>
  <div class="location-page">
    <LoadingSpinner v-if="loading" :text="t('customer.loadingLocation')" />

    <div v-else-if="!location" class="container">
      <EmptyState icon="🏪" :title="t('customer.locationNotFound')" :description="t('customer.locationMissing')" />
    </div>

    <template v-else>
      <!-- Hero image -->
      <div class="location-hero">
        <img
          :src="location.imageUrl || '/assets/img/location-placeholder.jpg'"
          :alt="t('customer.restaurantAt', { address: location.address })"
          class="location-hero__img"
        />
        <div class="location-hero__overlay">
          <div class="container">
            <h1 class="location-hero__name">{{ location.address }}</h1>
          </div>
        </div>
      </div>

      <div class="container location-layout">
        <!-- Details -->
        <div class="location-details">
          <div class="card location-info">
            <h4>{{ t('customer.locationDetails') }}</h4>
            <div class="info-row">
              <img src="/assets/svg/pin.svg" alt="" class="icon-sm" />
              <span>{{ location.address }}</span>
            </div>
            <div v-if="location.rating" class="info-row">
              <img src="/assets/svg/star.svg" alt="" class="icon-sm" />
              <span>{{ formatNumber(location.rating, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) }} / {{ formatNumber(5, { minimumFractionDigits: 1 }) }}</span>
            </div>
            <div v-if="location.description" class="info-row info-row--col">
              <p class="location-info__desc text-muted">{{ localizedLocation(location).description }}</p>
            </div>
          </div>

          <!-- Dishes at this location -->
          <div v-if="dishes.length" class="location-dishes">
            <h4>{{ t('customer.menuHighlights') }}</h4>
            <div class="dishes-mini-grid">
              <DishCard v-for="dish in dishes.slice(0, 4)" :key="dish.id" :dish="dish" />
            </div>
          </div>

          <section class="card location-feedback" aria-labelledby="feedback-title">
            <h2 id="feedback-title">{{ t('customer.reviewsTitle') }}</h2>
            <div class="feedback-controls">
              <div class="feedback-field">
                <label for="feedback-type">{{ t('customer.reviewType') }}</label>
                <select id="feedback-type" v-model="feedbackType" @change="loadFeedback(1)">
                  <option value="Service">{{ t('customer.service') }}</option>
                  <option value="CuisineExperience">{{ t('customer.cuisine') }}</option>
                </select>
              </div>
              <div class="feedback-field">
                <label for="feedback-sort">{{ t('customer.sortReviews') }}</label>
                <select id="feedback-sort" v-model="feedbackSort" @change="loadFeedback(1)">
                  <option value="NewestFirst">{{ t('customer.newestFirst') }}</option>
                  <option value="OldestFirst">{{ t('customer.oldestFirst') }}</option>
                  <option value="TopRatedFirst">{{ t('customer.highestRating') }}</option>
                  <option value="LowRatedFirst">{{ t('customer.lowestRating') }}</option>
                </select>
              </div>
            </div>
            <LoadingSpinner v-if="feedbackLoading" :text="t('customer.loadingReviews')" />
            <div v-else-if="feedbackError" role="alert">
              <p>{{ feedbackError.startsWith('customer.') ? t(feedbackError) : translateApiMessage(feedbackError) }}</p>
              <button type="button" class="button button--secondary button--small" @click="loadFeedback(feedbackPage)">{{ t('customer.retryReviews') }}</button>
            </div>
            <p v-else-if="!feedback.length" class="text-muted">{{ t('customer.noReviews') }}</p>
            <template v-else>
              <ul class="feedback-list">
                <li v-for="review in feedback" :key="`${review.reservationId}-${review.createdAt}`" class="feedback-item">
                  <div class="feedback-meta">
                    <strong>{{ !review.username || review.username === 'Anonymous User' ? t('customer.anonymousGuest') : review.username }}</strong>
                    <span :aria-label="t('customer.ratingOutOfFive', { rating: review.rating })">★ {{ review.rating }} / 5</span>
                  </div>
                  <time :datetime="review.createdAt" class="text-muted">{{ formatMediumDate(review.createdAt) }}</time>
                  <p v-if="review.comment" class="feedback-comment">{{ review.comment }}</p>
                  <p v-else class="text-muted">{{ t('customer.ratingOnly') }}</p>
                </li>
              </ul>
              <nav v-if="feedbackPages > 1" class="feedback-pagination" :aria-label="t('customer.reviewPages')">
                <button type="button" class="button button--secondary button--small" :disabled="feedbackPage <= 1" @click="loadFeedback(feedbackPage - 1)">{{ t('customer.previousReviews') }}</button>
                <span aria-live="polite">{{ t('customer.pageOf', { page: feedbackPage, pages: feedbackPages }) }}</span>
                <button type="button" class="button button--secondary button--small" :disabled="feedbackPage >= feedbackPages" @click="loadFeedback(feedbackPage + 1)">{{ t('customer.nextReviews') }}</button>
              </nav>
            </template>
          </section>
        </div>

        <!-- Reservation form -->
        <div class="location-reservation">
          <div class="card"><h3>{{ t('customer.bookTable') }}</h3><p>{{ t('customer.availableTablesIntro') }}</p><RouterLink :to="{ path: '/tables', query: { locationId } }" class="button button--primary button--extra-large">{{ t('customer.availableTables') }}</RouterLink></div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { translateApiMessage } from '@/i18n/errors'
import { localizedLocation } from '@/i18n/catalog'
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import LoadingSpinner from '../components/shared/LoadingSpinner.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import DishCard from '../components/dishes/DishCard.vue'
import { locationsApi, feedbackApi } from '@/services/api'
import type { Location as LocationResponse, Feedback, FeedbackSort } from '@/services/api'
import { formatMediumDate, formatNumber } from '@/utils/formatters'
import type { DishListResponse } from '../models/dishes/dish-list-response.model'

const route = useRoute()

const locationId = String(route.params.id)
const location = ref<LocationResponse | null>(null)
const dishes = ref<DishListResponse[]>([])
const loading = ref(false)
const feedback = ref<Feedback[]>([])
const feedbackType = ref<'Service' | 'CuisineExperience'>('Service')
const feedbackSort = ref<FeedbackSort>('NewestFirst')
const feedbackPage = ref(1)
const feedbackPages = ref(0)
const feedbackLoading = ref(false)
const feedbackError = ref('')
let feedbackRequest = 0

async function loadFeedback(page = 1): Promise<void> {
  const request = ++feedbackRequest
  feedbackPage.value = page
  feedbackLoading.value = true
  feedbackError.value = ''
  try {
    const result = await feedbackApi.forLocation(locationId, feedbackType.value, feedbackSort.value, page, { skipErrorToast: true })
    if (request !== feedbackRequest) return
    feedback.value = result.items
    feedbackPages.value = result.totalPages
    feedbackPage.value = result.currentPage
  } catch (err) {
    if (request === feedbackRequest) feedbackError.value = err instanceof Error ? err.message : 'customer.reviewsError'
  } finally {
    if (request === feedbackRequest) feedbackLoading.value = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    const [loc, dishesList] = await Promise.all([
      locationsApi.get(locationId),
      locationsApi.menu(locationId).catch(() => []),
    ])
    location.value = loc
    dishes.value = dishesList ?? []
    void loadFeedback()
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
})

</script>

<style scoped>
.location-page {
  display: flex;
  flex-direction: column;
  min-height: 60vh;
}

.location-hero {
  position: relative;
  height: 360px;
  overflow: hidden;
}

.location-hero__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.location-hero__overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(to top, rgba(0,0,0,0.6) 0%, transparent 60%);
  display: flex;
  align-items: flex-end;
  padding-bottom: 32px;
}

.location-hero__name {
  color: var(--neutral-0);
  margin: 0;
  font-size: 36px;
}

.location-layout {
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 32px;
  padding-top: 32px;
  padding-bottom: 56px;
  align-items: start;
}

.location-details {
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-width: 0;
}

.location-feedback { padding: 24px; }
.location-feedback h2 { font-size: 24px; margin: 0 0 20px; }
.feedback-controls { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 16px; }
.feedback-field { display: grid; gap: 6px; font-size: 14px; flex: 1; min-width: 140px; }
.feedback-controls select { width: 100%; padding: 10px; font: inherit; background: white; border: 1px solid var(--neutral-300); border-radius: 8px; }
.feedback-list { list-style: none; padding: 0; margin: 0; }
.feedback-item { padding: 18px 0; border-top: 1px solid var(--neutral-200); overflow-wrap: anywhere; }
.feedback-meta { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
.feedback-meta span { color: var(--green-700); white-space: nowrap; }
.feedback-item time { font-size: 13px; }
.feedback-comment { white-space: pre-wrap; margin: 10px 0 0; }
.feedback-pagination { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; padding-top: 12px; }

.location-info {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.location-info h4 {
  margin: 0;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--neutral-700);
}

.info-row--col {
  flex-direction: column;
  align-items: flex-start;
}

.location-info__desc {
  margin: 0;
  line-height: 1.7;
}

.icon-sm {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.location-dishes h4 {
  margin: 0 0 16px;
}

.dishes-mini-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.location-reservation {
  position: sticky;
  top: 80px;
}

.location-reservation > * {
  background: var(--neutral-0);
  padding: 24px;
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
}

@media (max-width: 900px) {
  .location-layout {
    grid-template-columns: 1fr;
  }
  .location-reservation {
    position: static;
  }
  .dishes-mini-grid {
    grid-template-columns: 1fr;
  }
}
</style>

