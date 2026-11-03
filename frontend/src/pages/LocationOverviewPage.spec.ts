import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { nextTick } from 'vue'
import { setLocale } from '@/i18n'
import { feedbackApi, locationsApi, type Feedback, type FeedbackPage, type Location } from '@/services/api'
import LocationOverviewPage from './LocationOverviewPage.vue'

enableAutoUnmount(afterEach)
const review: Feedback = { reservationId: 'r1', locationId: 'loc1', userId: 'c1', username: 'Олена', comment: 'Смачний обід', rating: 5, type: 0, createdAt: '2027-01-02T12:00:00Z' }
beforeEach(() => {
  vi.spyOn(locationsApi, 'get').mockResolvedValue({ id: 'loc1', address: 'Restaurant', description: 'City centre', rating: 5 } as Location)
  vi.spyOn(locationsApi, 'menu').mockResolvedValue([])
})
async function renderLocation() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/location/:id', component: LocationOverviewPage }] })
  await router.push('/location/loc1')
  return mount(LocationOverviewPage, { global: { plugins: [router] } })
}

describe('public location reviews', () => {
  it('renders reviews, paginates, and resets the page when type or sorting changes', async () => {
    vi.spyOn(feedbackApi, 'forLocation').mockImplementation(async (_id, _type, _sort, page) => ({ items: [{ ...review, comment: page === 1 ? 'Смачний обід' : 'Друга сторінка' }], totalPages: 2, currentPage: page }))
    const wrapper = await renderLocation(); await flushPromises()
    expect(wrapper.text()).toContain('Олена')
    expect(wrapper.text()).toContain('Смачний обід')
    expect(wrapper.find('[aria-label="5 out of 5 stars"]').exists()).toBe(true)
    await wrapper.findAll('button').find(button => button.text() === 'Next reviews')!.trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('Page 2 of 2')
    expect(wrapper.text()).toContain('Друга сторінка')
    await wrapper.get('#feedback-type').setValue('CuisineExperience'); await flushPromises()
    expect(feedbackApi.forLocation).toHaveBeenLastCalledWith('loc1', 'CuisineExperience', 'NewestFirst', 1, { skipErrorToast: true })
    await wrapper.get('#feedback-sort').setValue('TopRatedFirst'); await flushPromises()
    expect(feedbackApi.forLocation).toHaveBeenLastCalledWith('loc1', 'CuisineExperience', 'TopRatedFirst', 1, { skipErrorToast: true })
    expect(wrapper.findAll('button').find(button => button.text() === 'Previous reviews')!.element.disabled).toBe(true)
  })

  it('shows an inline retry on failure, then a clear empty state', async () => {
    vi.spyOn(feedbackApi, 'forLocation').mockRejectedValueOnce(new Error('Reviews are unavailable.')).mockResolvedValue({ items: [], totalPages: 0, currentPage: 1 })
    const wrapper = await renderLocation(); await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('Reviews are unavailable.')
    await wrapper.findAll('button').find(button => button.text() === 'Try reviews again')!.trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('No reviews of this type yet.')
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="Review pages"]').exists()).toBe(false)
  })

  it('translates an already visible connection error when the guest changes language', async () => {
    vi.spyOn(feedbackApi, 'forLocation').mockRejectedValue(new Error('Network error. Check your connection and try again.'))
    const wrapper = await renderLocation(); await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('Network error.')
    setLocale('uk'); await nextTick()
    expect(wrapper.get('[role="alert"]').text()).toContain('Немає зв’язку із сервером.')
    setLocale('fr'); await nextTick()
    expect(wrapper.get('[role="alert"]').text()).toContain('Connexion au serveur impossible.')
    expect(feedbackApi.forLocation).toHaveBeenCalledTimes(1)
    setLocale('en')
  })

  it('does not replace the selected cuisine results with a slower service response', async () => {
    let resolveService!: (result: FeedbackPage) => void
    vi.spyOn(feedbackApi, 'forLocation').mockImplementation((_id, type) => type === 'Service'
      ? new Promise(resolve => { resolveService = resolve })
      : Promise.resolve({ items: [{ ...review, comment: 'Cuisine review', type: 1 }], totalPages: 1, currentPage: 1 }))
    const wrapper = await renderLocation(); await flushPromises()
    expect(wrapper.text()).toContain('Loading reviews...')
    await wrapper.get('#feedback-type').setValue('CuisineExperience'); await flushPromises()
    resolveService({ items: [review], totalPages: 1, currentPage: 1 }); await flushPromises()
    expect(wrapper.text()).toContain('Cuisine review')
    expect(wrapper.text()).not.toContain('Смачний обід')
  })
})
