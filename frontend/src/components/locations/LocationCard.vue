<template>
  <RouterLink :to="`/locations/${location.id}`" class="location-card card">
    <div class="location-card__image-wrap">
      <img
        :src="location.imageUrl || '/assets/img/location-placeholder.jpg'"
        :alt="t('customer.restaurantAt', { address: location.address })"
        class="location-card__image" loading="lazy"
      />
    </div>
    <div class="location-card__body">
      <p class="location-card__address">
        <img src="/assets/svg/pin.svg" alt="" class="icon-sm" />
        {{ location.address }}
      </p>
      <div v-if="location.rating" class="location-card__rating">
        <img src="/assets/svg/star.svg" :alt="t('customer.rating')" class="icon-sm" />
        <span>{{ formatNumber(location.rating, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) }}</span>
      </div>
    </div>
    <div class="location-card__footer">
      <span class="button button--primary button--small">{{ t('customer.bookTable') }}</span>
    </div>
  </RouterLink>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { formatNumber } from '@/utils/formatters'
import type { Location as LocationResponse } from '@/services/api'

defineProps<{
  location: LocationResponse
}>()
</script>

<style scoped>
.location-card {
  display: flex;
  flex-direction: column;
  text-decoration: none;
  color: inherit;
  transition: box-shadow 0.2s, transform 0.2s;
}

.location-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
  text-decoration: none;
}

.location-card__image-wrap {
  height: 200px;
  overflow: hidden;
}

.location-card__image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s;
}

.location-card:hover .location-card__image {
  transform: scale(1.04);
}

.location-card__body {
  padding: 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.location-card__name {
  margin: 0;
  color: var(--neutral-900);
  font-size: 16px;
}

.location-card__address {
  margin: 0;
  font-size: 13px;
  color: var(--neutral-600);
  display: flex;
  align-items: center;
  gap: 4px;
}

.location-card__rating {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  font-weight: 500;
  color: var(--orange-400);
}

.location-card__footer {
  padding: 12px 16px;
  border-top: 1px solid var(--neutral-100);
}

.icon-sm {
  width: 14px;
  height: 14px;
}
</style>

