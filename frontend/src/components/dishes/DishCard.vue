<template>
  <component :is="interactive ? 'button' : 'article'" :type="interactive ? 'button' : undefined" class="dish-card card" :class="{ 'dish-card--interactive': interactive }">
    <div class="dish-card__image-wrap">
      <img
        :src="dish.imageUrl || '/assets/svg/dish-placeholder.svg'"
        :alt="displayDish.name"
        class="dish-card__image"
        loading="lazy"
      />
    </div>
    <div class="dish-card__body">
      <h5 class="dish-card__name">{{ displayDish.name }}</h5>
      <p class="dish-card__desc text-muted">{{ displayDish.description }}</p>
      <div class="dish-card__footer">
        <span class="dish-card__price">{{ formatCurrency(dish.price) }}</span>
        <slot name="action" />
      </div>
    </div>
  </component>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { localizedDish } from '@/i18n/catalog'
import { formatCurrency } from '@/utils/formatters'
import type { DishListResponse } from '../../models/dishes/dish-list-response.model'

const props = defineProps<{
  dish: DishListResponse
  interactive?: boolean
}>()
const displayDish = computed(() => localizedDish(props.dish))
</script>

<style scoped>
.dish-card {
  font: inherit;
  text-align: left;
  color: inherit;
  padding: 0;
  width: 100%;
  border: 1px solid var(--neutral-200);
  display: flex;
  flex-direction: column;
}

.dish-card--interactive { cursor: pointer; }
.dish-card--interactive:focus-visible { outline: 3px solid var(--green-600); outline-offset: 3px; }

.dish-card__image-wrap {
  height: 180px;
  overflow: hidden;
}

.dish-card__image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s;
}

.dish-card:hover .dish-card__image {
  transform: scale(1.04);
}

.dish-card__body {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.dish-card__name {
  margin: 0;
  font-size: 15px;
}

.dish-card__desc {
  margin: 0;
  font-size: 13px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.dish-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  padding-top: 8px;
}

.dish-card__price {
  font-size: 16px;
  font-weight: 600;
  color: var(--green-600);
}
</style>

