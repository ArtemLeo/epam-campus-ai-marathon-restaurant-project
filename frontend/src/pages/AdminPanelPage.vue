<template>
  <div class="admin-panel">
    <div class="container">
      <h1>{{ t('staff.adminTitle') }}</h1>
      <p class="text-muted">{{ t('staff.adminSubtitle') }}</p>

      <!-- Tab navigation -->
      <nav class="tabs">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="tab"
          :class="{ 'tab--active': activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </nav>

      <!-- Locations -->
      <section v-if="activeTab === 'locations'">
        <div class="section-header">
          <h2>{{ t('staff.locations') }}</h2>
          <button class="button button--primary button--sm" @click="openLocationForm()">+ {{ t('staff.addLocation') }}</button>
        </div>
        <LoadingSpinner v-if="locationsLoading" :text="t('staff.loadingLocations')" />
        <div v-else class="card-grid">
          <article v-for="loc in locations" :key="loc.id" class="admin-card">
            <img v-if="loc.imageUrl" :src="loc.imageUrl" :alt="localizedLocation(loc).address || ''" class="admin-card__img" />
            <div class="admin-card__body">
              <h3>{{ localizedLocation(loc).address }}</h3>
              <p>{{ localizedLocation(loc).description }}</p>
              <div class="admin-card__meta">
                <span>{{ t('staff.tablesCount', { count: loc.totalCapacity }) }}</span>
                <span>{{ t('staff.occupancy', { value: loc.averageOccupancy }) }}</span>
                <span v-if="loc.rating">{{ t('staff.rating', { value: formatNumber(loc.rating, { maximumFractionDigits: 1 }) }) }}</span>
              </div>
            </div>
            <div class="admin-card__actions">
              <button class="button button--secondary button--xs" @click="openLocationForm(loc)">{{ t('staff.edit') }}</button>
              <button class="button button--danger button--xs" @click="deleteLocation(loc)">{{ t('staff.delete') }}</button>
            </div>
          </article>
        </div>
      </section>

      <!-- Dishes -->
      <section v-if="activeTab === 'dishes'">
        <div class="section-header">
          <h2>{{ t('staff.dishes') }}</h2>
          <button class="button button--primary button--sm" @click="openDishForm()">+ {{ t('staff.addDish') }}</button>
        </div>
        <LoadingSpinner v-if="dishesLoading" :text="t('staff.loadingDishes')" />
        <div v-else class="card-grid">
          <article v-for="dish in dishes" :key="dish.id" class="admin-card">
            <img v-if="dish.imageUrl" :src="dish.imageUrl" :alt="localizedDish(dish).name" class="admin-card__img" />
            <div class="admin-card__body">
              <h3>{{ localizedDish(dish).name }}</h3>
              <p>{{ localizedDish(dish).description }}</p>
              <div class="admin-card__meta">
                <span class="badge" :class="'badge--' + dish.state.toLowerCase().replace(' ', '-')">{{ dishStateLabel(dish.state) }}</span>
                <span>{{ dishTypeLabel(dish.dishType) }}</span>
                <span>{{ formatCurrency(dish.price) }}</span>
                <span>{{ localizedDish(dish).weight }}</span>
              </div>
            </div>
            <div class="admin-card__actions">
              <button class="button button--secondary button--xs" @click="openDishForm(dish)">{{ t('staff.edit') }}</button>
              <button class="button button--danger button--xs" @click="deleteDish(dish)">{{ t('staff.delete') }}</button>
            </div>
          </article>
        </div>
      </section>

      <!-- Tables -->
      <section v-if="activeTab === 'tables'">
        <div class="section-header">
          <h2>{{ t('staff.tables') }}</h2>
          <button class="button button--primary button--sm" @click="openTableForm()">+ {{ t('staff.addTable') }}</button>
        </div>
        <div class="filter-row">
          <label>{{ t('staff.location') }}:
            <select v-model="tableLocationFilter" @change="loadTables()">
              <option value="">{{ t('staff.selectLocation') }}</option>
              <option v-for="loc in locations" :key="loc.id" :value="loc.id">{{ localizedLocation(loc).address }}</option>
            </select>
          </label>
        </div>
        <LoadingSpinner v-if="tablesLoading" :text="t('staff.loadingTables')" />
        <EmptyState v-else-if="!tableLocationFilter" icon="📍" :title="t('staff.selectLocationTitle')" :description="t('staff.selectLocationTables')" />
        <div v-else class="card-grid card-grid--compact">
          <article v-for="tbl in tables" :key="tbl.id" class="admin-card admin-card--small">
            <div class="admin-card__body">
              <h3>{{ t('staff.tableNumber', { number: tbl.tableNumber }) }}</h3>
              <p>{{ t('staff.capacitySeats', { count: tbl.capacity }) }}</p>
            </div>
            <div class="admin-card__actions">
              <button class="button button--secondary button--xs" @click="openTableForm(tbl)">{{ t('staff.edit') }}</button>
              <button class="button button--danger button--xs" @click="deleteTable(tbl)">{{ t('staff.delete') }}</button>
            </div>
          </article>
        </div>
      </section>

      <!-- Waiters -->
      <section v-if="activeTab === 'waiters'">
        <div class="section-header">
          <h2>{{ t('staff.waiters') }}</h2>
          <button class="button button--primary button--sm" @click="waiterLocationId = waiterLocationFilter || locations[0]?.id || ''; showWaiterForm = true">+ {{ t('staff.addWaiter') }}</button>
        </div>
        <div class="filter-row">
          <label>{{ t('staff.location') }}:
            <select v-model="waiterLocationFilter" @change="loadWaitersForLocation()">
              <option value="">{{ t('staff.selectLocation') }}</option>
              <option v-for="loc in locations" :key="loc.id" :value="loc.id">{{ localizedLocation(loc).address }}</option>
            </select>
          </label>
        </div>
        <LoadingSpinner v-if="waitersLoading" :text="t('staff.loadingWaiters')" />
        <EmptyState v-else-if="!waiterLocationFilter" icon="📍" :title="t('staff.selectLocationTitle')" :description="t('staff.selectLocationWaiters')" />
        <div v-else class="card-grid card-grid--compact">
          <article v-for="w in waiters" :key="w.email" class="admin-card admin-card--small">
            <div class="admin-card__body">
              <h3>{{ w.firstName }} {{ w.lastName }}</h3>
              <p>{{ w.email }}</p>
            </div>
            <div class="admin-card__actions">
              <button class="button button--danger button--xs" @click="removeWaiter(w)">{{ t('staff.remove') }}</button>
            </div>
          </article>
        </div>
      </section>
    </div>

    <!-- Location form modal -->
    <AppModal v-if="locationFormVisible" :title="t(editingLocation ? 'staff.editLocation' : 'staff.addLocation')" size="lg" @close="locationFormVisible = false">
      <form id="location-form" class="form" @submit.prevent="saveLocation">
        <div class="form-group">
          <label for="admin-address">{{ t('staff.address') }}</label>
          <input id="admin-address" v-model="locationForm.address" required />
        </div>
        <div class="form-group">
          <label for="admin-description">{{ t('staff.description') }}</label>
          <textarea id="admin-description" v-model="locationForm.description" rows="3" required />
        </div>
        <details class="translation-fields">
          <summary>{{ t('staff.translations') }}</summary>
          <p>{{ t('staff.translationHint') }}</p>
          <label class="form-group" for="location-translation-language">{{ t('staff.translationLanguage') }}
            <select id="location-translation-language" v-model="translationLanguage">
              <option v-for="language in translationLanguages" :key="language.code" :value="language.code">{{ language.name }}</option>
            </select>
          </label>
          <label class="form-group" for="location-translated-description">{{ t('staff.translatedDescription') }}
            <textarea id="location-translated-description" v-model="translatedLocationDescription" rows="3" maxlength="2000" />
          </label>
        </details>
        <div class="form-row">
          <div class="form-group">
            <label for="admin-avg-occupancy">{{ t('staff.averageOccupancy') }}</label>
            <input id="admin-avg-occupancy" v-model="locationForm.averageOccupancy" placeholder="65%" required />
          </div>
        </div>
        <div class="form-group">
          <label for="admin-image">{{ t('staff.image') }}</label>
          <input id="admin-image" type="file" accept="image/*" @change="onLocationImage" />
        </div>
      </form>
      <template #footer>
        <button class="button button--secondary" @click="locationFormVisible = false">{{ t('staff.cancel') }}</button>
        <button class="button button--primary" :disabled="savingLocation" type="submit" form="location-form">
          {{ t(savingLocation ? 'staff.saving' : 'staff.save') }}
        </button>
      </template>
    </AppModal>

    <!-- Dish form modal -->
    <AppModal v-if="dishFormVisible" :title="t(editingDish ? 'staff.editDish' : 'staff.addDish')" size="lg" @close="dishFormVisible = false">
      <form id="dish-form" class="form" @submit.prevent="saveDish">
        <div class="form-row">
          <div class="form-group">
            <label for="admin-name">{{ t('staff.name') }}</label>
            <input id="admin-name" v-model="dishForm.name" required />
          </div>
          <div class="form-group">
            <label for="admin-type">{{ t('staff.type') }}</label>
            <select id="admin-type" v-model="dishForm.dishType" required>
              <option value="Appetizer">{{ t('staff.appetizer') }}</option>
              <option value="MainCourse">{{ t('staff.mainCourse') }}</option>
              <option value="Dessert">{{ t('staff.dessert') }}</option>
            </select>
          </div>
        </div>
        <div class="form-group">
          <label for="admin-description">{{ t('staff.description') }}</label>
          <textarea id="admin-description" v-model="dishForm.description" rows="2" required />
        </div>
        <details class="translation-fields">
          <summary>{{ t('staff.translations') }}</summary>
          <p>{{ t('staff.translationHint') }}</p>
          <label class="form-group" for="dish-translation-language">{{ t('staff.translationLanguage') }}
            <select id="dish-translation-language" v-model="translationLanguage">
              <option v-for="language in translationLanguages" :key="language.code" :value="language.code">{{ language.name }}</option>
            </select>
          </label>
          <label class="form-group" for="dish-translated-name">{{ t('staff.translatedName') }}
            <input id="dish-translated-name" v-model="translatedDishName" maxlength="200" />
          </label>
          <label class="form-group" for="dish-translated-description">{{ t('staff.translatedDescription') }}
            <textarea id="dish-translated-description" v-model="translatedDishDescription" rows="2" maxlength="2000" />
          </label>
        </details>
        <div class="form-row">
          <div class="form-group"><label for="admin-price">{{ t('staff.price') }}</label><input id="admin-price" v-model.number="dishForm.price" type="number" min="0" step="0.01" required /></div>
          <div class="form-group"><label for="admin-weight">{{ t('staff.weight') }}</label><input id="admin-weight" v-model="dishForm.weight" :placeholder="t('staff.gramsExample', { amount: 350 })" required /></div>
          <div class="form-group">
            <label for="admin-state">{{ t('staff.state') }}</label>
            <select id="admin-state" v-model="dishForm.state" required>
              <option value="Available">{{ t('staff.available') }}</option>
              <option value="OnStop">{{ t('staff.onStop') }}</option>
              <option value="OutOfStock">{{ t('staff.outOfStock') }}</option>
            </select>
          </div>
        </div>
        <div class="form-row">
          <div class="form-group"><label for="admin-calories">{{ t('staff.calories') }}</label><input id="admin-calories" v-model="dishForm.calories" :placeholder="t('staff.caloriesExample')" required /></div>
          <div class="form-group"><label for="admin-proteins">{{ t('staff.proteins') }}</label><input id="admin-proteins" v-model="dishForm.proteins" :placeholder="t('staff.gramsExample', { amount: 12 })" required /></div>
          <div class="form-group"><label for="admin-fats">{{ t('staff.fats') }}</label><input id="admin-fats" v-model="dishForm.fats" :placeholder="t('staff.gramsExample', { amount: 14 })" required /></div>
        </div>
        <div class="form-row">
          <div class="form-group"><label for="admin-carbohydrates">{{ t('staff.carbohydrates') }}</label><input id="admin-carbohydrates" v-model="dishForm.carbohydrates" :placeholder="t('staff.gramsExample', { amount: 40 })" required /></div>
          <div class="form-group"><label for="admin-vitamins">{{ t('staff.vitamins') }}</label><input id="admin-vitamins" v-model="dishForm.vitamins" placeholder="A, C, E" required /></div>
        </div>
        <div class="form-group">
          <label>{{ t('staff.locations') }}</label>
          <div class="checkbox-group">
            <label v-for="loc in locations" :key="loc.id" class="checkbox-label">
              <input v-model="dishForm.locationIds" type="checkbox" :value="loc.id" />
              {{ localizedLocation(loc).address }}
            </label>
          </div>
        </div>
        <div class="form-group">
          <label for="admin-image">{{ t('staff.image') }}</label>
          <input id="admin-image" type="file" accept="image/*" @change="onDishImage" />
        </div>
      </form>
      <template #footer>
        <button class="button button--secondary" @click="dishFormVisible = false">{{ t('staff.cancel') }}</button>
        <button class="button button--primary" :disabled="savingDish" type="submit" form="dish-form">
          {{ t(savingDish ? 'staff.saving' : 'staff.save') }}
        </button>
      </template>
    </AppModal>

    <!-- Table form modal -->
    <AppModal v-if="tableFormVisible" :title="t(editingTable ? 'staff.editTable' : 'staff.addTable')" size="sm" @close="tableFormVisible = false">
      <form id="table-form" class="form" @submit.prevent="saveTable">
        <div class="form-group">
          <label for="admin-location">{{ t('staff.location') }}</label>
          <select id="admin-location" v-model="tableForm.locationId" required :disabled="!!editingTable">
            <option v-for="loc in locations" :key="loc.id" :value="loc.id">{{ localizedLocation(loc).address }}</option>
          </select>
        </div>
        <div class="form-row">
          <div class="form-group"><label for="admin-table-number">{{ t('staff.tableNumberLabel') }}</label><input id="admin-table-number" v-model.number="tableForm.tableNumber" type="number" min="1" required /></div>
          <div class="form-group"><label for="admin-capacity">{{ t('staff.capacity') }}</label><input id="admin-capacity" v-model.number="tableForm.capacity" type="number" min="1" required /></div>
        </div>
      </form>
      <template #footer>
        <button class="button button--secondary" @click="tableFormVisible = false">{{ t('staff.cancel') }}</button>
        <button class="button button--primary" :disabled="savingTable" type="submit" form="table-form">
          {{ t(savingTable ? 'staff.saving' : 'staff.save') }}
        </button>
      </template>
    </AppModal>

    <!-- Waiter form modal -->
    <AppModal v-if="showWaiterForm" :title="t('staff.addWaiter')" size="sm" @close="showWaiterForm = false">
      <form id="waiter-form" class="form" @submit.prevent="addWaiter">
        <div class="form-group">
          <label for="admin-email-must-be-a-registered-user">{{ t('staff.registeredEmail') }}</label>
          <input id="admin-email-must-be-a-registered-user" v-model="waiterEmail" type="email" required />
        </div>
        <div class="form-group">
          <label for="admin-location">{{ t('staff.location') }}</label>
          <select id="admin-location" v-model="waiterLocationId" required>
            <option v-for="loc in locations" :key="loc.id" :value="loc.id">{{ localizedLocation(loc).address }}</option>
          </select>
        </div>
      </form>
      <template #footer>
        <button class="button button--secondary" @click="showWaiterForm = false">{{ t('staff.cancel') }}</button>
        <button class="button button--primary" :disabled="addingWaiter" type="submit" form="waiter-form">
          {{ t(addingWaiter ? 'staff.adding' : 'staff.addWaiter') }}
        </button>
      </template>
    </AppModal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { t, supportedLocales, languageNames, type Locale } from '@/i18n'
import { localizedDish, localizedLocation } from '@/i18n/catalog'
import { formatCurrency, formatNumber } from '@/utils/formatters'
import { locationsApi, dishesApi, tablesApi, waitersApi } from '@/services/api'
import type { Location, Dish, Table, DishTypeName, DishRequest, DishTranslations, Waiter } from '@/services/api/types'
import AppModal from '@/components/shared/AppModal.vue'
import LoadingSpinner from '@/components/shared/LoadingSpinner.vue'
import EmptyState from '@/components/shared/EmptyState.vue'
import { useToast } from '@/composables/useToast'

const { success: showSuccess } = useToast()

function dishStateLabel(state: string): string {
  const key = ({ Available: 'available', OnStop: 'onStop', 'On stop': 'onStop', OutOfStock: 'outOfStock', 'Out of stock': 'outOfStock' } as Record<string, string>)[state]
  return key ? t(`staff.${key}`) : state
}
function dishTypeLabel(type: string): string {
  const key = ({ Appetizer: 'appetizer', MainCourse: 'mainCourse', 'Main course': 'mainCourse', Dessert: 'dessert' } as Record<string, string>)[type]
  return key ? t(`staff.${key}`) : type
}

const tabKeys = ['locations', 'dishes', 'tables', 'waiters'] as const
const tabs = computed(() => tabKeys.map(key => ({ key, label: t(`staff.${key}`) })))
type TabKey = (typeof tabKeys)[number]
const activeTab = ref<TabKey>('locations')

const translationLanguages = supportedLocales.map(code => ({ code, name: languageNames[code] }))
const translationLanguage = ref<Locale>('uk')
function copyTranslations(translations?: DishTranslations): DishTranslations {
  return Object.fromEntries(Object.entries(translations ?? {}).map(([code, fields]) => [code, { ...fields }]))
}
function setTranslation(translations: DishTranslations, field: 'name' | 'description', value: string) {
  const language = translationLanguage.value
  if (value) translations[language] = { ...translations[language], [field]: value }
  else {
    delete translations[language]?.[field]
    if (!Object.keys(translations[language] ?? {}).length) delete translations[language]
  }
}

// --- Locations ---
const locations = ref<Location[]>([])
const locationsLoading = ref(false)
const locationFormVisible = ref(false)
const editingLocation = ref<Location | null>(null)
const savingLocation = ref(false)
const locationForm = ref({ address: '', description: '', averageOccupancy: '50%', imageBase64: null as string | null, translations: {} as DishTranslations })
const translatedLocationDescription = computed({
  get: () => locationForm.value.translations[translationLanguage.value]?.description ?? '',
  set: (value: string) => setTranslation(locationForm.value.translations, 'description', value),
})

async function loadLocations() {
  locationsLoading.value = true
  try { locations.value = await locationsApi.list() } catch { /* toast shows */ }
  finally { locationsLoading.value = false }
}

function openLocationForm(loc?: Location) {
  editingLocation.value = loc ?? null
  locationForm.value = loc
    ? { address: loc.address, description: loc.description, averageOccupancy: loc.averageOccupancy, imageBase64: null, translations: copyTranslations(loc.translations) }
    : { address: '', description: '', averageOccupancy: '50%', imageBase64: null, translations: {} }
  locationFormVisible.value = true
}

function onLocationImage(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => { locationForm.value.imageBase64 = (reader.result as string).split(',')[1] }
  reader.readAsDataURL(file)
}

async function saveLocation() {
  savingLocation.value = true
  try {
    const body = { ...locationForm.value, ...(locationForm.value.imageBase64 ? { imageBase64: locationForm.value.imageBase64 } : {}) }
    if (editingLocation.value) {
      await locationsApi.update(editingLocation.value.id, body)
      showSuccess(t('staff.locationUpdated'))
    } else {
      await locationsApi.create(body)
      showSuccess(t('staff.locationCreated'))
    }
    locationFormVisible.value = false
    await loadLocations()
  } catch { /* toast */ }
  finally { savingLocation.value = false }
}

async function deleteLocation(loc: Location) {
  if (!confirm(t('staff.confirmDeleteLocation', { name: localizedLocation(loc).address || loc.address }))) return
  try {
    await locationsApi.remove(loc.id)
    showSuccess(t('staff.locationDeleted'))
    await loadLocations()
  } catch { /* toast */ }
}

// --- Dishes ---
const dishes = ref<Dish[]>([])
const dishesLoading = ref(false)
const dishFormVisible = ref(false)
const editingDish = ref<Dish | null>(null)
const savingDish = ref(false)
const dishForm = ref(emptyDishForm())
const translatedDishName = computed({
  get: () => dishForm.value.translations[translationLanguage.value]?.name ?? '',
  set: (value: string) => setTranslation(dishForm.value.translations, 'name', value),
})
const translatedDishDescription = computed({
  get: () => dishForm.value.translations[translationLanguage.value]?.description ?? '',
  set: (value: string) => setTranslation(dishForm.value.translations, 'description', value),
})

function emptyDishForm() {
  return {
    name: '', description: '', dishType: 'MainCourse' as DishTypeName, price: 0, weight: '',
    calories: '', proteins: '', fats: '', carbohydrates: '', vitamins: '',
    state: 'Available' as DishRequest['state'], imageBase64: null as string | null, locationIds: [] as string[], translations: {} as DishTranslations,
  }
}

async function loadDishes() {
  dishesLoading.value = true
  try { dishes.value = await dishesApi.list() } catch { /* toast */ }
  finally { dishesLoading.value = false }
}

function openDishForm(dish?: Dish) {
  editingDish.value = dish ?? null
  dishForm.value = dish
    ? {
        name: dish.name, description: dish.description,
        dishType: ({ 'Main course': 'MainCourse' }[dish.dishType] ?? dish.dishType) as DishTypeName,
        price: dish.price, weight: dish.weight, calories: dish.calories ?? '', proteins: dish.proteins ?? '',
        fats: dish.fats ?? '', carbohydrates: dish.carbohydrates ?? '', vitamins: dish.vitamins ?? '',
        state: ({ 'On stop': 'OnStop', 'Out of stock': 'OutOfStock' }[dish.state] ?? dish.state) as DishRequest['state'],
        imageBase64: null, locationIds: [...(dish.locationIds ?? [])], translations: copyTranslations(dish.translations),
      }
    : emptyDishForm()
  dishFormVisible.value = true
}

function onDishImage(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => { dishForm.value.imageBase64 = (reader.result as string).split(',')[1] }
  reader.readAsDataURL(file)
}

async function saveDish() {
  savingDish.value = true
  try {
    const body: DishRequest = { ...dishForm.value }
    if (editingDish.value) {
      await dishesApi.update(editingDish.value.id, body)
      showSuccess(t('staff.dishUpdated'))
    } else {
      await dishesApi.create(body)
      showSuccess(t('staff.dishCreated'))
    }
    dishFormVisible.value = false
    await loadDishes()
  } catch { /* toast */ }
  finally { savingDish.value = false }
}

async function deleteDish(dish: Dish) {
  if (!confirm(t('staff.confirmDeleteDish', { name: localizedDish(dish).name }))) return
  try {
    await dishesApi.remove(dish.id, true)
    showSuccess(t('staff.dishDeleted'))
    await loadDishes()
  } catch { /* toast */ }
}

// --- Tables ---
const tables = ref<Table[]>([])
const tablesLoading = ref(false)
const tableLocationFilter = ref('')
const tableFormVisible = ref(false)
const editingTable = ref<Table | null>(null)
const savingTable = ref(false)
const tableForm = ref({ locationId: '', tableNumber: 1, capacity: 2 })

async function loadTables() {
  if (!tableLocationFilter.value) { tables.value = []; return }
  tablesLoading.value = true
  try { tables.value = await locationsApi.tables(tableLocationFilter.value) } catch { /* toast */ }
  finally { tablesLoading.value = false }
}

function openTableForm(tbl?: Table) {
  editingTable.value = tbl ?? null
  tableForm.value = tbl
    ? { locationId: tbl.locationId, tableNumber: tbl.tableNumber, capacity: tbl.capacity }
    : { locationId: tableLocationFilter.value || (locations.value[0]?.id ?? ''), tableNumber: 1, capacity: 2 }
  tableFormVisible.value = true
}

async function saveTable() {
  savingTable.value = true
  try {
    if (editingTable.value) {
      await tablesApi.update(editingTable.value.id, { capacity: tableForm.value.capacity, tableNumber: tableForm.value.tableNumber })
      showSuccess(t('staff.tableUpdated'))
    } else {
      await tablesApi.create(tableForm.value)
      showSuccess(t('staff.tableCreated'))
    }
    tableFormVisible.value = false
    await loadTables()
    await loadLocations()
  } catch { /* toast */ }
  finally { savingTable.value = false }
}

async function deleteTable(tbl: Table) {
  if (!confirm(t('staff.confirmDeleteTable', { number: tbl.tableNumber }))) return
  try {
    await tablesApi.remove(tbl.id)
    showSuccess(t('staff.tableDeleted'))
    await loadTables()
    await loadLocations()
  } catch { /* toast */ }
}

// --- Waiters ---
const waiters = ref<Waiter[]>([])
const waitersLoading = ref(false)
const waiterLocationFilter = ref('')
const showWaiterForm = ref(false)
const waiterEmail = ref('')
const waiterLocationId = ref('')
const addingWaiter = ref(false)

async function loadWaitersForLocation() {
  waitersLoading.value = true
  try { waiters.value = (await waitersApi.list()).filter(w => w.locationId === waiterLocationFilter.value) }
  catch { waiters.value = [] }
  finally { waitersLoading.value = false }
}

async function addWaiter() {
  addingWaiter.value = true
  try {
    await waitersApi.add(waiterEmail.value, waiterLocationId.value || waiterLocationFilter.value)
    showSuccess(t('staff.waiterAdded', { email: waiterEmail.value }))
    showWaiterForm.value = false
    waiterEmail.value = ''
    await loadWaitersForLocation()
  } catch { /* toast */ }
  finally { addingWaiter.value = false }
}

async function removeWaiter(w: Waiter) {
  if (!confirm(t('staff.confirmRemoveWaiter', { email: w.email }))) return
  try {
    await waitersApi.remove(w.email)
    showSuccess(t('staff.waiterRemoved'))
    waiters.value = waiters.value.filter(x => x.email !== w.email)
  } catch { /* toast */ }
}

// --- Init ---
onMounted(async () => {
  await loadLocations()
  await loadDishes()
})
</script>

<style scoped>
.admin-panel {
  padding: 32px 0;
  min-height: 80vh;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 16px;
}

h1 {
  margin: 0 0 4px;
  font-size: 28px;
  color: var(--neutral-900);
}

.text-muted {
  color: var(--neutral-500);
  margin: 0 0 24px;
}

.tabs {
  display: flex;
  gap: 4px;
  border-bottom: 2px solid var(--neutral-200);
  margin-bottom: 24px;
}

.tab {
  padding: 10px 20px;
  background: none;
  border: none;
  font-size: 14px;
  font-weight: 500;
  color: var(--neutral-500);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: color 0.15s, border-color 0.15s;
}

.tab:hover { color: var(--neutral-700); }
.tab--active { color: var(--green-600); border-bottom-color: var(--green-500); }

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h2 {
  margin: 0;
  font-size: 20px;
  color: var(--neutral-800);
}

.filter-row {
  margin-bottom: 16px;
}

.filter-row label {
  font-size: 14px;
  color: var(--neutral-600);
}

.filter-row select {
  margin-left: 8px;
  padding: 6px 12px;
  border: 1px solid var(--neutral-300);
  border-radius: var(--radius-md);
  font-size: 14px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}

.card-grid--compact {
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
}

.admin-card {
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: var(--neutral-0);
  display: flex;
  flex-direction: column;
}

.admin-card--small .admin-card__body { padding: 12px 16px; }

.admin-card__img {
  width: 100%;
  height: 160px;
  object-fit: cover;
}

.admin-card__body {
  padding: 16px;
  flex: 1;
}

.admin-card__body h3 {
  margin: 0 0 6px;
  font-size: 16px;
  color: var(--neutral-900);
}

.admin-card__body p {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--neutral-500);
  line-height: 1.5;
}

.admin-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: var(--neutral-500);
}

.admin-card__actions {
  padding: 12px 16px;
  border-top: 1px solid var(--neutral-100);
  display: flex;
  gap: 8px;
}

.badge { padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }
.badge--available { background: var(--green-100); color: var(--green-700); }
.badge--on-stop { background: var(--amber-100); color: var(--amber-700); }
.badge--out-of-stock { background: var(--red-100); color: var(--red-700); }

.form { display: flex; flex-direction: column; gap: 16px; }
.form-group { display: flex; flex-direction: column; gap: 4px; flex: 1; }
.form-group label { font-size: 13px; font-weight: 500; color: var(--neutral-700); }
.form-group input, .form-group select, .form-group textarea {
  padding: 8px 12px;
  border: 1px solid var(--neutral-300);
  border-radius: var(--radius-md);
  font-size: 14px;
}
.form-row { display: flex; gap: 12px; }
.translation-fields { border: 1px solid var(--neutral-200); border-radius: var(--radius-md); padding: 12px; }
.translation-fields summary { cursor: pointer; font-weight: 500; }
.translation-fields p { font-size: 13px; color: var(--neutral-600); }
.translation-fields .form-group + .form-group { margin-top: 12px; }

.checkbox-group { display: flex; flex-wrap: wrap; gap: 8px; }
.checkbox-label { display: flex; align-items: center; gap: 6px; font-size: 13px; cursor: pointer; }

.button { padding: 8px 16px; border: none; border-radius: var(--radius-md); font-size: 14px; font-weight: 500; cursor: pointer; transition: background 0.15s; }
.button--primary { background: var(--green-500); color: white; }
.button--primary:hover { background: var(--green-600); }
.button--secondary { background: var(--neutral-100); color: var(--neutral-700); }
.button--secondary:hover { background: var(--neutral-200); }
.button--danger { background: var(--red-100); color: var(--red-700); }
.button--danger:hover { background: var(--red-200); }
.button--sm { padding: 6px 14px; font-size: 13px; }
.button--xs { padding: 4px 10px; font-size: 12px; }
.button:disabled { opacity: 0.6; cursor: not-allowed; }

@media (max-width: 600px) {
  .form-row { flex-direction: column; }
  .card-grid { grid-template-columns: 1fr; }
  .tabs { overflow-x: auto; }
}
</style>
