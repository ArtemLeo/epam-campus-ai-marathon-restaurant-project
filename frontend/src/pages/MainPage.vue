<template>
  <div class="main-page">
    <!-- Hero -->
    <section class="hero" :style="heroBg">
      <div class="hero__overlay">
        <div class="container hero__content">
          <h1 class="hero__title">{{ t('customer.heroTitle') }}</h1>
          <p class="hero__subtitle">{{ t('customer.heroSubtitle') }}</p>
          <div class="hero__actions">
            <RouterLink to="/menu" class="button button--primary button--extra-large">{{ t('customer.browseMenu') }}</RouterLink>
            <button
              v-if="!auth.isAuthenticated"
              class="button button--secondary button--extra-large"
              @click="showLogin = true"
            >
              {{ t('customer.signInReserve') }}
            </button>
            <RouterLink v-else to="/reservations" class="button button--secondary button--extra-large">
              {{ t('customer.myReservations') }}
            </RouterLink>
          </div>
        </div>
      </div>
    </section>

    <!-- Locations -->
    <section class="locations-section">
      <div class="container">
        <div class="section-header">
          <h2>{{ t('customer.locationsTitle') }}</h2>
          <p class="text-muted">{{ t('customer.locationsSubtitle') }}</p>
        </div>

        <LoadingSpinner v-if="loading" :text="t('customer.loadingLocations')" />

        <p v-else-if="error" class="error-msg">{{ error.startsWith('customer.') ? t(error) : translateApiMessage(error) }}</p>

        <div v-else-if="locations.length === 0">
          <EmptyState icon="🏪" :title="t('customer.noLocations')" :description="t('customer.checkBack')" />
        </div>

        <div v-else class="locations-grid">
          <LocationCard v-for="loc in locations" :key="loc.id" :location="loc" />
        </div>
      </div>
    </section>

    <!-- Login modal -->
    <LoginModal v-if="showLogin" @close="showLogin = false" />
  </div>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { translateApiMessage } from '@/i18n/errors'
import { ref, computed, onMounted } from 'vue'
import LocationCard from '../components/locations/LocationCard.vue'
import LoadingSpinner from '../components/shared/LoadingSpinner.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import LoginModal from '../components/auth/LoginModal.vue'
import { locationsApi } from '@/services/api'
import { useAuthStore } from '../stores/auth'
import type { Location as LocationResponse } from '@/services/api'

const auth = useAuthStore()
const locations = ref<LocationResponse[]>([])
const loading = ref(false)
const error = ref('')
const showLogin = ref(false)

const heroBg = computed(() => ({
  backgroundImage: `url('/assets/img/hero-bg.webp')`,
}))

async function fetchLocations(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    locations.value = (await locationsApi.list()) ?? []
  } catch (err) {
    error.value = err instanceof Error && err.message ? err.message : 'customer.locationsError'
  } finally {
    loading.value = false
  }
}

onMounted(fetchLocations)
</script>

<style scoped>
.main-page {
  display: flex;
  flex-direction: column;
}

/* Hero */
.hero {
  background-size: cover;
  background-position: center;
  background-color: var(--green-800);
  min-height: 520px;
  display: flex;
  position: relative;
}

.hero__overlay {
  flex: 1;
  min-width: 0;
  background: linear-gradient(
    135deg,
    rgba(15, 67, 37, 0.92) 0%,
    rgba(30, 110, 62, 0.80) 50%,
    rgba(45, 139, 82, 0.65) 100%
  );
  display: flex;
  align-items: center;
}

.hero__content {
  padding-top: 72px;
  padding-bottom: 72px;
  max-width: 680px;
}

.hero__title {
  color: var(--neutral-0);
  margin: 0 0 16px;
  overflow-wrap: anywhere;
}

.hero__subtitle {
  color: rgba(255, 255, 255, 0.88);
  font-size: 18px;
  line-height: 1.7;
  margin: 0 0 36px;
}

.hero__actions {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

/* Locations */
.locations-section {
  padding: 72px 0;
  background: var(--bg-warm);
}

.section-header {
  margin-bottom: 40px;
}

.section-header h2 {
  margin: 0 0 8px;
}

.locations-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(300px, 100%), 1fr));
  gap: 28px;
}

.error-msg {
  color: var(--red-400);
  text-align: center;
  padding: 32px;
}

@media (max-width: 768px) {
  .hero { min-height: 400px; }
  .hero__title { font-size: 36px; }
  .hero__content { padding-top: 48px; padding-bottom: 48px; }
}
</style>

