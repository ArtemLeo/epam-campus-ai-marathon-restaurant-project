import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AppButton from './AppButton.vue'

describe('AppButton accessibility', () => {
  it('exposes its busy state while keeping the spinner decorative', () => {
    const wrapper = mount(AppButton, {
      props: { loading: true },
      slots: { default: 'Save changes' },
    })
    const button = wrapper.get('button')

    expect(button.attributes('aria-busy')).toBe('true')
    expect(button.attributes('disabled')).toBeDefined()
    expect(wrapper.get('.btn-spinner').attributes('aria-hidden')).toBe('true')
    expect(button.text()).toBe('Save changes')
  })

  it('omits the busy state when idle', () => {
    const wrapper = mount(AppButton, { slots: { default: 'Save changes' } })

    expect(wrapper.get('button').attributes('aria-busy')).toBeUndefined()
    expect(wrapper.find('.btn-spinner').exists()).toBe(false)
  })
})
