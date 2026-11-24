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
    const wrapper = mount(AppToast)
    await nextTick()

    const success = document.body.querySelector('.toast--success')!
    const error = document.body.querySelector('.toast--error')!
    expect(success.getAttribute('role')).toBe('status')
    expect(success.getAttribute('aria-live')).toBe('polite')
    expect(error.getAttribute('role')).toBe('alert')
    expect(error.getAttribute('aria-live')).toBe('assertive')
    expect(error.querySelector('.toast__icon')?.getAttribute('aria-hidden')).toBe('true')

    wrapper.unmount()
  })
})
