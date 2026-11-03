import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { setLocale } from '@/i18n'
import { dishesApi, feedbackApi, reservationsApi, type Dish, type Feedback } from '@/services/api'
import type { ReservationCustomer } from '@/models/reservations/reservation.model'
import MenuPage from './MenuPage.vue'
import ReservationCard from '@/components/reservations/ReservationCard.vue'
import FeedbackWindow from '@/components/reservations/FeedbackWindow.vue'

enableAutoUnmount(afterEach)
beforeEach(() => setLocale('en'))
afterEach(() => setLocale('en'))

describe('customer pages in five languages', () => {
  it('switches menu labels and catalogue text reactively, searches accents and preserves API enum values', async () => {
    const dish = {
      id: 'd1', name: 'Vegetable soup', description: 'A light vegetable soup', price: 12.5, imageUrl: null,
      translations: { fr: { name: 'Velouté de légumes', description: 'Un velouté léger' }, de: { name: 'Gemüsesuppe', description: 'Eine leichte Gemüsesuppe' } },
    } as Dish
    vi.spyOn(dishesApi, 'list').mockResolvedValue([dish])
    const wrapper = mount(MenuPage); await flushPromises()
    expect(wrapper.text()).toContain('Our Menu')
    setLocale('fr'); await nextTick()
    expect(wrapper.text()).toContain('Notre carte')
    expect(wrapper.text()).toContain('Velouté de légumes')
    await wrapper.get('input').setValue('veloute'); await nextTick()
    expect(wrapper.findAll('.dish-card')).toHaveLength(1)
    expect(dishesApi.list).toHaveBeenCalledTimes(1)
    await wrapper.get('input').setValue('')
    setLocale('de'); await nextTick()
    expect(wrapper.text()).toContain('Unsere Speisekarte')
    expect(wrapper.text()).toContain('Gemüsesuppe')
    expect(wrapper.get('input').attributes('placeholder')).toBe('Gerichte suchen…')
    await wrapper.findAll('button').find(button => button.text() === 'Hauptgerichte')!.trigger('click'); await flushPromises()
    expect(dishesApi.list).toHaveBeenLastCalledWith({ dishType: 'MainCourse', sortBy: undefined })
  })

  it('uses Ukrainian guest plurals and translates reservation status without altering its value', async () => {
    const reservation = { id: 'r1', restaurantName: 'Green & Tasty', locationAddress: 'Rustaveli Avenue', status: 0, guestCount: 1, startTime: '2027-01-02T12:00:00Z' } as ReservationCustomer
    const wrapper = mount(ReservationCard, { props: { reservation } })
    setLocale('uk'); await nextTick()
    expect(wrapper.text()).toContain('1 гість')
    expect(wrapper.text()).toContain('Заброньовано')
    await wrapper.setProps({ reservation: { ...reservation, guestCount: 2 } })
    expect(wrapper.text()).toContain('2 гості')
    await wrapper.setProps({ reservation: { ...reservation, guestCount: 5 } })
    expect(wrapper.text()).toContain('5 гостей')
    setLocale('fr'); await nextTick()
    expect(wrapper.text()).toContain('5 convives')
    expect(wrapper.text()).toContain('Réservée')
    expect(reservation.status).toBe(0)
  })

  it('keeps a written review and rating when switching to longer German labels, then submits unchanged data', async () => {
    vi.spyOn(reservationsApi, 'feedback').mockResolvedValue({ service: null, cuisineExperience: null })
    vi.spyOn(feedbackApi, 'create').mockResolvedValue({} as Feedback)
    const wrapper = mount(FeedbackWindow, { props: { reservationId: 'r1' } }); await flushPromises()
    setLocale('uk'); await nextTick()
    await wrapper.findAll('textarea')[0]!.setValue('Дякую за гостинність!')
    await wrapper.findAll('[aria-label="5 зірок"]')[0]!.trigger('click')
    setLocale('de'); await nextTick()
    expect(wrapper.text()).toContain('Kulinarisches Erlebnis')
    expect(wrapper.findAll('textarea')[0]!.element.value).toBe('Дякую за гостинність!')
    expect(wrapper.findAll('textarea')[0]!.attributes('placeholder')).toBe('Kommentar (optional)')
    await wrapper.findAll('button.button--primary')[0]!.trigger('click'); await flushPromises()
    expect(feedbackApi.create).toHaveBeenCalledWith({ reservationId: 'r1', rating: 5, type: 0, comment: 'Дякую за гостинність!' })
    setLocale('fr'); await nextTick()
    expect(wrapper.text()).toContain('Mettre à jour')
  })
})
