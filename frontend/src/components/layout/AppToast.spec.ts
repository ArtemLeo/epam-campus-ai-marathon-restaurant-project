import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { clearToasts, useToast } from '@/composables/useToast'
import AppToast from './AppToast.vue'

beforeEach(clearToasts)

afterEach(() => {
  clearToasts()
  document.body.innerHTML = ''
})

describe('AppToast accessibility', () => {
  it('announces errors urgently and routine messages politely', async () => {
    const toast = useToast()
    toast.success('Profile updated.')
    toast.error('Profile update failed.')
    const wrapper = mount(AppToast, { global: { stubs: { teleport: true } } })
    await nextTick()

    const success = wrapper.get('.toast--success')
    const error = wrapper.get('.toast--error')
    expect(success.attributes('role')).toBe('status')
    expect(success.attributes('aria-live')).toBe('polite')
    expect(error.attributes('role')).toBe('alert')
    expect(error.attributes('aria-live')).toBe('assertive')
    expect(error.get('.toast__icon').attributes('aria-hidden')).toBe('true')

    wrapper.unmount()
  })
})
