<template>
  <div class="menu-page container">
    <div class="page-header">
      <h2>{{ t('customer.menuTitle') }}</h2>
      <p class="text-muted">{{ t('customer.menuSubtitle') }}</p>
    </div>

    <div class="menu-controls">
      <div class="menu-categories" role="group" :aria-label="t('customer.dishCategory')">
        <button
          v-for="cat in categories"
          :key="cat.value"
          type="button"
          class="chip"
          :class="{ 'chip--active': dishType === cat.value }"
          @click="dishType = cat.value"
        >
          {{ cat.label }}
        </button>
      </div>
      <select v-model="sortBy" class="menu-sort" :aria-label="t('customer.sortDishes')">
        <option v-for="opt in sortOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
      </select>
      <AppInput v-model="searchQuery" :placeholder="t('customer.searchDishes')" style="max-width: 320px" />
    </div>

    <LoadingSpinner v-if="loading" :text="t('customer.loadingMenu')" />

    <EmptyState
      v-else-if="visibleDishes.length === 0"
      icon="🍽️"
      :title="t('customer.noDishes')"
      :description="t('customer.adjustSearch')"
    />

    <div v-else class="dishes-grid">
      <DishCard
        v-for="dish in visibleDishes"
        :key="dish.id"
        :dish="dish"
        class="menu-card"
        interactive
        @click="selected = dish"
      />
    </div>

    <DishModal v-if="selected" :dish="selected" @close="selected = null" />
  </div>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { localizedDish } from '@/i18n/catalog'
import { ref, computed, watch, onMounted } from 'vue'
import DishCard from '../components/dishes/DishCard.vue'
import DishModal from '../components/dishes/DishModal.vue'
import AppInput from '../components/shared/AppInput.vue'
import LoadingSpinner from '../components/shared/LoadingSpinner.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import { dishesApi, type Dish, type DishSortName, type DishTypeName } from '@/services/api'

const categories = computed<{ label: string; value: DishTypeName | '' }[]>(() => [
  { label: t('customer.all'), value: '' },
  { label: t('customer.appetizer'), value: 'Appetizer' },
  { label: t('customer.mainCourse'), value: 'MainCourse' },
  { label: t('customer.dessert'), value: 'Dessert' },
])
const sortOptions = computed<{ label: string; value: DishSortName | '' }[]>(() => [
  { label: t('customer.sortBy'), value: '' },
  { label: t('customer.priceAscending'), value: 'PriceAscending' },
  { label: t('customer.priceDescending'), value: 'PriceDescending' },
  { label: t('customer.popularityAscending'), value: 'PopularityAscending' },
  { label: t('customer.popularityDescending'), value: 'PopularityDescending' },
])

const dishes = ref<Dish[]>([])
const loading = ref(false)
const searchQuery = ref('')
const dishType = ref<DishTypeName | ''>('')
const sortBy = ref<DishSortName | ''>('')
const selected = ref<Dish | null>(null)
const normalizeSearch = (value: string) => value.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()
const visibleDishes = computed(() => {
  const search = normalizeSearch(searchQuery.value.trim())
  return dishes.value.filter(dish => normalizeSearch(`${dish.name} ${localizedDish(dish).name}`).includes(search))
})

let requestId = 0

async function load(): Promise<void> {
  const current = ++requestId
  loading.value = true
  try {
    const result = await dishesApi.list({
      dishType: dishType.value || undefined,
      sortBy: sortBy.value || undefined,
    })
    if (current === requestId) dishes.value = result ?? []
  } catch {
    if (current === requestId) dishes.value = []
  } finally {
    if (current === requestId) loading.value = false
  }
}

watch([dishType, sortBy], () => void load())
onMounted(load)
</script>

<style scoped>
.menu-page {
  padding-bottom: 56px;
}

.menu-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
  margin-bottom: 24px;
}

.menu-categories {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  padding: 8px 16px;
  border: 1px solid #d1d5db;
  border-radius: 999px;
  background: #fff;
  cursor: pointer;
  font: inherit;
}

.chip--active {
  background: var(--green-600);
  border-color: var(--green-600);
  color: #fff;
}

.menu-sort {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  font: inherit;
}

.dishes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 24px;
}

.menu-card {
  cursor: pointer;
}
</style>
