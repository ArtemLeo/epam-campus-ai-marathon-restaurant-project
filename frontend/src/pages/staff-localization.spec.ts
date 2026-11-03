import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { setLocale, supportedLocales, t } from '@/i18n'
import { staffMessages } from '@/i18n/staff'
import * as http from '@/services/http/api-client'
import { locationsApi, dishesApi, reservationsApi, reportsApi, type Dish, type Location } from '@/services/api'
import AdminPanelPage from './AdminPanelPage.vue'
import WaiterDashboardPage from './WaiterDashboardPage.vue'
import WaiterPreOrderPage from './WaiterPreOrderPage.vue'
import ReportingDashboardPage from './ReportingDashboardPage.vue'

enableAutoUnmount(afterEach)

const location: Location = {
  id: 'staff-loc', address: 'Original address', description: 'Original description',
  totalCapacity: 3, averageOccupancy: '50%', rating: 4.2, imageUrl: null,
  translations: { uk: { description: 'Український опис' }, fr: { description: 'Description française' } },
}
const dish: Dish = {
  id: 'staff-dish', name: 'Seasonal soup', description: 'Original soup description',
  dishType: 'Main course', state: 'On stop', price: 12.5, weight: '350 g',
  calories: '100 kcal', proteins: '12 g', fats: '10 g', carbohydrates: '14 g', vitamins: 'B',
  imageUrl: null, locationIds: [location.id],
  translations: { uk: { name: 'Сезонний суп' }, fr: { description: 'Une soupe de saison' } },
}

beforeEach(() => {
  setLocale('en')
  vi.spyOn(locationsApi, 'list').mockResolvedValue([location])
  vi.spyOn(dishesApi, 'list').mockResolvedValue([dish])
  vi.spyOn(reservationsApi, 'list').mockResolvedValue([])
  vi.spyOn(reportsApi, 'history').mockResolvedValue([])
})
afterEach(() => setLocale('en'))

describe('staff language switching', () => {
  it.each([
    { page: AdminPanelPage, title: 'adminTitle' },
    { page: WaiterDashboardPage, title: 'waiterTitle' },
    { page: WaiterPreOrderPage, title: 'preorderTitle' },
    { page: ReportingDashboardPage, title: 'reportsTitle' },
  ])('updates $title in all five languages without remounting', async ({ page, title }) => {
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/staff-test', component: page }] })
    await router.push('/staff-test')
    const wrapper = mount(page, { global: { plugins: [router, createPinia()] } })
    await flushPromises()
    for (const language of supportedLocales) {
      setLocale(language)
      await flushPromises()
      expect(wrapper.text()).toContain(staffMessages[language].staff[title])
      expect(wrapper.text()).not.toMatch(/\bstaff\.[a-zA-Z]/)
    }
    expect(vi.mocked(locationsApi.list).mock.calls.length).toBeLessThanOrEqual(1)
  })

  it('keeps original dish fields and API enums while editing independent translations', async () => {
    const update = vi.spyOn(dishesApi, 'update').mockResolvedValue(dish)
    setLocale('uk')
    const wrapper = mount(AdminPanelPage)
    await flushPromises()
    await wrapper.findAll('.tab')[1]!.trigger('click')
    expect(wrapper.text()).toContain('Сезонний суп')
    await wrapper.get('.admin-card__actions button').trigger('click')
    expect(wrapper.get<HTMLInputElement>('#admin-name').element.value).toBe('Seasonal soup')
    expect(wrapper.get<HTMLSelectElement>('#admin-type').element.value).toBe('MainCourse')
    expect(wrapper.get<HTMLSelectElement>('#admin-state').element.value).toBe('OnStop')
    await wrapper.get('#dish-translation-language').setValue('de')
    await wrapper.get('#dish-translated-name').setValue('Saisonale Suppe')
    await wrapper.get('#dish-translated-description').setValue('Gemüsesuppe')
    setLocale('fr')
    await flushPromises()
    expect(wrapper.get<HTMLInputElement>('#admin-name').element.value).toBe('Seasonal soup')
    expect(wrapper.get<HTMLTextAreaElement>('#admin-description').element.value).toBe('Original soup description')
    expect(wrapper.get<HTMLInputElement>('#dish-translated-name').element.value).toBe('Saisonale Suppe')
    expect(dish.translations?.de).toBeUndefined()
    await wrapper.get('#dish-form').trigger('submit')
    await flushPromises()
    expect(update).toHaveBeenCalledWith(dish.id, expect.objectContaining({
      name: 'Seasonal soup', description: 'Original soup description', dishType: 'MainCourse', state: 'OnStop',
      translations: {
        uk: { name: 'Сезонний суп' }, fr: { description: 'Une soupe de saison' },
        de: { name: 'Saisonale Suppe', description: 'Gemüsesuppe' },
      },
    }))
  })

  it('preserves location translations and original text when changing the interface language', async () => {
    const update = vi.spyOn(locationsApi, 'update').mockResolvedValue(location)
    const wrapper = mount(AdminPanelPage)
    await flushPromises()
    await wrapper.get('.admin-card__actions button').trigger('click')
    await wrapper.get('#location-translation-language').setValue('es')
    await wrapper.get('#location-translated-description').setValue('Descripción en español')
    setLocale('de')
    await flushPromises()
    expect(wrapper.get<HTMLInputElement>('#admin-address').element.value).toBe(location.address)
    expect(wrapper.get<HTMLTextAreaElement>('#admin-description').element.value).toBe(location.description)
    expect(location.translations?.es).toBeUndefined()
    await wrapper.get('#location-form').trigger('submit')
    await flushPromises()
    expect(update).toHaveBeenCalledWith(location.id, expect.objectContaining({
      address: location.address, description: location.description,
      translations: { ...location.translations, es: { description: 'Descripción en español' } },
    }))
  })

  it('keeps report filter values while translating their labels', async () => {
    const generate = vi.spyOn(reportsApi, 'generate').mockResolvedValue([])
    const download = vi.spyOn(reportsApi, 'download').mockResolvedValue({ blob: new Blob(['report']), fileName: 'report.csv' })
    vi.spyOn(http, 'saveFile').mockImplementation(() => {})
    const wrapper = mount(ReportingDashboardPage)
    await flushPromises()
    await wrapper.get('#report-report-type').setValue('0')
    await wrapper.get('#report-start-date').setValue('2027-01-01')
    await wrapper.get('#report-end-date').setValue('2027-01-31')
    setLocale('es')
    await flushPromises()
    expect(wrapper.get<HTMLSelectElement>('#report-report-type').element.value).toBe('0')
    expect(wrapper.get<HTMLSelectElement>('#report-location').element.value).toBe(location.id)
    expect(wrapper.text()).toContain(t('staff.serviceByWaiter'))
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(generate).toHaveBeenCalledWith({ locationId: location.id, type: 0, startDate: '2027-01-01', endDate: '2027-01-31' })
    await wrapper.findAll('.report-actions button')[1]!.trigger('click')
    await flushPromises()
    expect(download).toHaveBeenCalledWith(expect.objectContaining({ locale: 'es', type: 0, locationId: location.id }), 'csv')
  })
})
