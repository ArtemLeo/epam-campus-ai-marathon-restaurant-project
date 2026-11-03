import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, disposePinia } from 'pinia'
import { guestApi, locationsApi, dishesApi, waitersApi, reportsApi, reservationsApi, ordersApi, type Dish, type Location, type Order, type Reservation } from '@/services/api'
import { setApiBaseUrl, setMockHandler, type ApiRequest } from '@/services/http/api-client'
import * as http from '@/services/http/api-client'
import GuestPreOrderPage from './GuestPreOrderPage.vue'
import AdminPanelPage from './AdminPanelPage.vue'
import ReportingDashboardPage from './ReportingDashboardPage.vue'
import WaiterPreOrderPage from './WaiterPreOrderPage.vue'
import DishModal from '@/components/dishes/DishModal.vue'

enableAutoUnmount(afterEach)
const location: Location = { id: 'loc1', address: 'Test Restaurant', description: 'A restaurant', totalCapacity: 2, averageOccupancy: '50%', imageUrl: null, rating: 0 }
function button(wrapper: VueWrapper, text: string) {
  const found = wrapper.findAll('button').find(b => b.text() === text)
  if (!found) throw new Error(`Button missing: ${text}`)
  return found
}
beforeEach(() => { setMockHandler(undefined); setApiBaseUrl('https://api.test') })
afterEach(() => { setMockHandler(undefined) })

describe('real guest API contract', () => {
  it('joins by name, persists the token, restores its cart, removes on the server and submits', async () => {
    const calls: ApiRequest[] = []
    let quantity = 0
    let submitted = false
    const dish = { id: 'dish1', name: 'Soup', description: 'Vegetable soup', price: 10, state: 'Available', selectable: true }
    setMockHandler(request => {
      calls.push(request)
      let body: unknown = {}
      if (request.path === '/guest/invites/invite1') body = { GroupReservationId: 'group1', InviterName: 'Host', LocationAddress: 'Restaurant', StartTime: '2027-01-01T12:00:00Z' }
      else if (request.path === '/guest/sessions' && request.method === 'POST') body = { SessionId: 'session1', SessionToken: 'guest-token' }
      else if (request.path === '/guest/sessions/session1/menu') body = { dishes: { Appetizer: [dish] } }
      else if (request.path === '/guest/sessions/session1') body = { name: 'Olena', items: quantity ? [{ dish, quantity }] : [], total: quantity * 10, isSubmitted: submitted }
      else if (request.path.endsWith('/dishes')) quantity += request.method === 'DELETE' ? -1 : 1
      else if (request.path.endsWith('/submit')) submitted = true
      else return Promise.resolve({ status: 404, body: { message: request.path } })
      return Promise.resolve({ status: 200, body })
    })
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/join/:token', component: GuestPreOrderPage }] })
    await router.push('/join/invite1')
    const wrapper = mount(GuestPreOrderPage, { global: { plugins: [router] } })
    await flushPromises()
    await wrapper.get('input[autocomplete="name"]').setValue('Olena')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(calls.find(c => c.path === '/guest/sessions')?.body).toEqual({ groupReservationId: 'group1', guestName: 'Olena' })
    expect(JSON.parse(localStorage.getItem('guest-session:invite1')!)).toEqual({ SessionId: 'session1', SessionToken: 'guest-token' })
    await button(wrapper, 'Add').trigger('click'); await flushPromises()
    await button(wrapper, 'Add').trigger('click'); await flushPromises()
    await button(wrapper, 'Remove one').trigger('click'); await flushPromises()
    expect(quantity).toBe(1)
    const removal = calls.find(c => c.method === 'DELETE')!
    expect(removal.body).toEqual({ dishId: 'dish1', quantity: 1 })
    expect(removal.headers.Authorization).toBe('Bearer guest-token')
    wrapper.unmount()
    const restored = mount(GuestPreOrderPage, { global: { plugins: [router] } })
    await flushPromises()
    expect(calls.filter(c => c.path === '/guest/sessions')).toHaveLength(1)
    expect(restored.text()).toContain('1 × Soup')
    await button(restored, 'Submit Pre-Order').trigger('click'); await flushPromises()
    expect(submitted).toBe(true)
    expect(restored.text()).toContain('Your pre-order has been submitted')
    expect(restored.findAll('button').some(b => b.text() === 'Add')).toBe(false)
  })

  it('shows a server rejection without leaving an optimistic dish in the cart', async () => {
    localStorage.setItem('guest-session:invite2', JSON.stringify({ SessionId: 's2', SessionToken: 't2' }))
    vi.spyOn(guestApi, 'invite').mockResolvedValue({ GroupReservationId: 'g2', StartTime: '2027-01-01T12:00:00Z' } as Awaited<ReturnType<typeof guestApi.invite>>)
    vi.spyOn(guestApi, 'session').mockResolvedValue({ name: 'Olena', items: [], total: 0, isSubmitted: false })
    vi.spyOn(guestApi, 'menu').mockResolvedValue({ dishes: { Appetizer: [{ id: 'd2', name: 'Soup', selectable: true, price: 10 }] as Awaited<ReturnType<typeof guestApi.menu>>['dishes']['Appetizer'] } })
    vi.spyOn(guestApi, 'addDish').mockRejectedValue(new Error('Dish is no longer available'))
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/join/:token', component: GuestPreOrderPage }] })
    await router.push('/join/invite2')
    const wrapper = mount(GuestPreOrderPage, { global: { plugins: [router] } })
    await flushPromises()
    await button(wrapper, 'Add').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('Dish is no longer available')
    expect(wrapper.text()).toContain('Choose a dish from the menu.')
  })
})

describe('administrator screens', () => {
  it.each([['On stop', 'OnStop'], ['Out of stock', 'OutOfStock']])('preserves API dish labels when editing %s', async (state, expectedState) => {
    const dish: Dish = { id: 'd1', name: 'Khinkali', description: 'Dumplings', dishType: 'Main course', state, price: 10, weight: '200 g', calories: '100', proteins: '10', fats: '10', carbohydrates: '10', vitamins: 'B', imageUrl: null, locationIds: ['loc1'] }
    vi.spyOn(locationsApi, 'list').mockResolvedValue([location])
    vi.spyOn(dishesApi, 'list').mockResolvedValue([dish])
    vi.spyOn(dishesApi, 'update').mockResolvedValue(dish)
    const wrapper = mount(AdminPanelPage)
    await flushPromises(); await button(wrapper, 'Dishes').trigger('click'); await flushPromises()
    await button(wrapper, 'Edit').trigger('click')
    expect(wrapper.get<HTMLSelectElement>('#admin-type').element.value).toBe('MainCourse')
    expect(wrapper.get<HTMLSelectElement>('#admin-state').element.value).toBe(expectedState)
    await wrapper.get('#dish-form').trigger('submit'); await flushPromises()
    expect(dishesApi.update).toHaveBeenCalledWith('d1', expect.objectContaining({ dishType: 'MainCourse', state: expectedState, locationIds: ['loc1'] }))
  })
  it('closes a successful create dialog and reloads the visible locations', async () => {
    const created = { ...location, id: 'new', address: 'New Restaurant' }
    vi.spyOn(locationsApi, 'list').mockResolvedValueOnce([location]).mockResolvedValue([location, created])
    vi.spyOn(dishesApi, 'list').mockResolvedValue([])
    vi.spyOn(locationsApi, 'create').mockResolvedValue(created)
    const wrapper = mount(AdminPanelPage)
    await flushPromises()
    await button(wrapper, '+ Add Location').trigger('click')
    await wrapper.get('#admin-address').setValue(created.address)
    await wrapper.get('#admin-description').setValue(created.description)
    await wrapper.get('#location-form').trigger('submit'); await flushPromises()
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('New Restaurant')
    expect(locationsApi.create).toHaveBeenCalledTimes(1)
  })
  it('lists real waiters and removes the selected person', async () => {
    vi.spyOn(locationsApi, 'list').mockResolvedValue([location])
    vi.spyOn(dishesApi, 'list').mockResolvedValue([])
    vi.spyOn(waitersApi, 'list').mockResolvedValue([{ userId: 'w1', email: 'waiter@test.com', firstName: 'Nino', lastName: 'Beridze', locationId: 'loc1' }])
    vi.spyOn(waitersApi, 'remove').mockResolvedValue({ message: 'Removed' })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const wrapper = mount(AdminPanelPage)
    await flushPromises(); await button(wrapper, 'Waiters').trigger('click')
    await wrapper.get('.filter-row select').setValue('loc1'); await flushPromises()
    expect(wrapper.text()).toContain('Nino Beridze')
    await button(wrapper, 'Remove').trigger('click'); await flushPromises()
    expect(waitersApi.remove).toHaveBeenCalledWith('waiter@test.com')
    expect(wrapper.text()).not.toContain('Nino Beridze')
  })
  it('generates the selected report and downloads binary output without posting to a missing route', async () => {
    vi.spyOn(locationsApi, 'list').mockResolvedValue([location])
    vi.spyOn(reportsApi, 'history').mockResolvedValue([])
    vi.spyOn(reportsApi, 'generate').mockResolvedValue([])
    const download = { blob: new Blob(['report']), fileName: 'report.csv' }
    vi.spyOn(reportsApi, 'download').mockResolvedValue(download)
    vi.spyOn(http, 'saveFile').mockImplementation(() => {})
    const wrapper = mount(ReportingDashboardPage)
    await flushPromises()
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(reportsApi.generate).toHaveBeenCalledWith(expect.objectContaining({ locationId: 'loc1', type: 1 }))
    await button(wrapper, 'Download').trigger('click'); await flushPromises()
    expect(reportsApi.download).toHaveBeenCalledWith(expect.objectContaining({ locationId: 'loc1', type: 1 }), 'csv')
    expect(http.saveFile).toHaveBeenCalledWith(download)
    expect(reportsApi.generate).toHaveBeenCalledTimes(1)
  })
})

describe('waiter order review', () => {
  it('opens the reservation from the dashboard link and confirms a real order line', async () => {
    vi.spyOn(reservationsApi, 'list').mockResolvedValue([{ id: 'r1', startTime: '2027-01-01T12:00:00Z', locationAddress: 'Test Restaurant', status: 0 }] as Reservation[])
    const order = { reservationId: 'r1', orderId: 'o1', status: 3, orderItems: [{ dish: { id: 'd1', name: 'Soup', price: 10 }, quantity: 1, state: 0 }] } as Order
    vi.spyOn(ordersApi, 'get').mockResolvedValue(order)
    vi.spyOn(ordersApi, 'confirmDish').mockResolvedValue({ message: 'Confirmed' })
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/waiter-pre-order', component: WaiterPreOrderPage }] })
    await router.push('/waiter-pre-order?reservationId=r1')
    const wrapper = mount(WaiterPreOrderPage, { global: { plugins: [router, createPinia()] } })
    await flushPromises()
    expect(wrapper.get('select').element.value).toBe('r1')
    expect(wrapper.text()).toContain('Soup')
    await button(wrapper, 'Confirm').trigger('click'); await flushPromises()
    expect(ordersApi.confirmDish).toHaveBeenCalledWith('r1', 'd1')
  })
})

describe('customer pre-order eligibility', () => {
  it('offers only future bookings in this dish location with an editable order', async () => {
    const token = `e30.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600, 'cognito:groups': ['Customer'] }))}.signature`
    localStorage.setItem('auth', JSON.stringify({ idToken: token, accessToken: token }))
    const pinia = createPinia()
    const future = new Date(Date.now() + 86_400_000).toISOString()
    const booking = { id: 'eligible', locationId: 'loc1', startTime: future, status: 0, locationAddress: 'Restaurant' } as Reservation
    vi.spyOn(reservationsApi, 'list').mockResolvedValue([
      booking,
      { ...booking, id: 'different-location', locationId: 'loc2' },
      { ...booking, id: 'final-group' },
      { ...booking, id: 'past-cutoff', startTime: new Date(Date.now() + 20 * 60_000).toISOString() },
    ])
    vi.spyOn(ordersApi, 'list').mockResolvedValue([{ reservationId: 'final-group', canEdit: false }] as Order[])
    const wrapper = mount(DishModal, { props: { dish: { id: 'd1', name: 'Soup', price: 10, state: 'Available', locationIds: ['loc1'] } as Dish }, global: { plugins: [pinia] } })
    await flushPromises()
    expect(wrapper.findAll('option').map(option => option.element.value)).toEqual(['eligible'])
    expect(wrapper.get<HTMLButtonElement>('button.button--primary').element.disabled).toBe(false)
    wrapper.unmount(); disposePinia(pinia)
  })
})

describe('account recovery and email confirmation', () => {
  it('uses the local recovery code and saves the new password through the reset endpoint', async () => {
    const { default: ResetPasswordPage } = await import('./ResetPasswordPage.vue')
    const { authApi } = await import('@/services/api')
    vi.spyOn(authApi, 'forgotPassword').mockResolvedValue({ message: 'Sent', resetCode: '123456' })
    vi.spyOn(authApi, 'resetPassword').mockResolvedValue({ message: 'Changed' })
    const wrapper = mount(ResetPasswordPage)
    await wrapper.get('input[type="email"]').setValue('customer@example.com')
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(wrapper.text()).toContain('Local demo recovery code: 123456')
    await wrapper.get('input[autocomplete="one-time-code"]').setValue('123456')
    const passwords = wrapper.findAll('input[type="password"]')
    await passwords[0]!.setValue('NewPassword#2026')
    await passwords[1]!.setValue('NewPassword#2026')
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(authApi.resetPassword).toHaveBeenCalledWith('customer@example.com', '123456', 'NewPassword#2026')
    expect(wrapper.text()).toContain('Your password has been changed.')
  })
  it('confirms an existing unverified account without creating a duplicate', async () => {
    const { default: RegisterPage } = await import('./RegisterPage.vue')
    const { authApi } = await import('@/services/api')
    vi.spyOn(authApi, 'register').mockResolvedValue({ message: 'Created', confirmationRequired: true })
    vi.spyOn(authApi, 'confirmRegistration').mockResolvedValue({ message: 'Confirmed' })
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/signup', component: RegisterPage }, { path: '/main', component: { template: '<div />' } }] })
    await router.push('/signup?confirmEmail=customer%40example.com')
    const wrapper = mount(RegisterPage, { global: { plugins: [router, createPinia()] } })
    await wrapper.get('input[autocomplete="one-time-code"]').setValue('123456')
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(authApi.register).not.toHaveBeenCalled()
    expect(authApi.confirmRegistration).toHaveBeenCalledWith('customer@example.com', '123456')
    expect(router.currentRoute.value.path).toBe('/main')
  })
})
