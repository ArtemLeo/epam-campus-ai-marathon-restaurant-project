import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, disposePinia, setActivePinia, type Pinia } from 'pinia'
import { nextTick } from 'vue'
import { setLocale } from '@/i18n'
import { authApi } from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import { clearDraft } from '@/components/auth/login-modal'
import LoginForm from '@/components/auth/LoginForm.vue'
import RegisterPage from './RegisterPage.vue'
import ResetPasswordPage from './ResetPasswordPage.vue'
import ProfilePage from './ProfilePage.vue'

enableAutoUnmount(afterEach)
let pinia: Pinia
beforeEach(() => { setLocale('en'); clearDraft(); pinia = createPinia(); setActivePinia(pinia) })
afterEach(() => { disposePinia(pinia); clearDraft(); setLocale('en') })
async function routerFor(path = '/signup') {
  const router = createRouter({ history: createMemoryHistory(), routes: ['/signup', '/main', '/forgot-password'].map(path => ({ path, component: { template: '<div />' } })) })
  await router.push(path)
  return router
}

describe('account locale changes preserve form state', () => {
  it('translates a visible login validation error without clearing email or password', async () => {
    const wrapper = mount(LoginForm, { global: { plugins: [pinia, await routerFor('/main')] } })
    await wrapper.get('input[name="email"]').setValue('not-an-email')
    await wrapper.get('input[name="email"]').trigger('blur')
    await wrapper.get('input[name="password"]').setValue('DraftPassword#1')
    expect(wrapper.text()).toContain('Invalid email address.')
    setLocale('uk'); await nextTick()
    expect(wrapper.text()).toContain('Перевірте адресу електронної пошти.')
    expect(wrapper.get<HTMLInputElement>('input[name="email"]').element.value).toBe('not-an-email')
    expect(wrapper.get<HTMLInputElement>('input[name="password"]').element.value).toBe('DraftPassword#1')
    setLocale('de'); await nextTick()
    expect(wrapper.text()).toContain('Prüfen Sie die E-Mail-Adresse.')
  })

  it('updates registration field errors and labels while retaining entered values', async () => {
    const wrapper = mount(RegisterPage, { global: { plugins: [pinia, await routerFor()] } })
    const inputs = wrapper.findAll('input')
    await inputs[0]!.setValue('1')
    await inputs[1]!.setValue('Петренко')
    await inputs[2]!.setValue('person@example.com')
    await inputs[3]!.setValue('weak')
    await inputs[4]!.setValue('different')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.text()).toContain('Passwords do not match')
    setLocale('fr'); await nextTick()
    expect(wrapper.text()).toContain('Les mots de passe ne correspondent pas')
    expect(wrapper.text()).toContain('Utilisez des lettres, espaces, traits d’union ou apostrophes.')
    expect(wrapper.findAll('input')[1]!.element.value).toBe('Петренко')
    expect(wrapper.findAll('input')[3]!.element.value).toBe('weak')
  })

  it('keeps the recovery code and password drafts when translating a validation failure', async () => {
    vi.spyOn(authApi, 'forgotPassword').mockResolvedValue({ message: 'Sent', resetCode: '123456' })
    const wrapper = mount(ResetPasswordPage)
    await wrapper.get('input[type="email"]').setValue('person@example.com')
    await wrapper.get('form').trigger('submit'); await flushPromises()
    await wrapper.get('input[autocomplete="one-time-code"]').setValue('123456')
    await wrapper.findAll('input[type="password"]')[0]!.setValue('weak')
    await wrapper.get('form').trigger('submit')
    setLocale('es'); await nextTick()
    expect(wrapper.text()).toContain('Revisa los requisitos y comprueba que las dos contraseñas coincidan.')
    expect(wrapper.text()).toContain('Código de recuperación de la demo local: 123456')
    expect(wrapper.get<HTMLInputElement>('input[autocomplete="one-time-code"]').element.value).toBe('123456')
    expect(wrapper.findAll<HTMLInputElement>('input[type="password"]')[0]!.element.value).toBe('weak')
  })

  it('translates profile name errors and role without replacing the user’s draft', async () => {
    const auth = useAuthStore()
    auth.user = { id: 'c1', firstName: 'Олена', lastName: 'Коваль', email: 'person@example.com', role: 'Customer' }
    vi.spyOn(auth, 'fetchMe').mockResolvedValue(undefined)
    vi.spyOn(authApi, 'profileImage').mockResolvedValue({ presignedUrl: '/assets/img/avatar.png' })
    const wrapper = mount(ProfilePage, { global: { plugins: [pinia] } }); await flushPromises()
    const firstForm = wrapper.findAll('form')[0]!
    await firstForm.findAll('input')[0]!.setValue('1')
    await firstForm.trigger('submit')
    setLocale('uk'); await nextTick()
    expect(wrapper.text()).toContain('Використовуйте літери, пробіли, дефіси або апострофи.')
    expect(wrapper.text()).toContain('Клієнт')
    expect(firstForm.findAll('input')[0]!.element.value).toBe('1')
    expect(firstForm.findAll('input')[1]!.element.value).toBe('Коваль')
  })
})
