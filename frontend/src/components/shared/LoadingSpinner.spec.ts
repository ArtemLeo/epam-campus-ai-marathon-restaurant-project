import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import LoadingSpinner from './LoadingSpinner.vue'

describe('LoadingSpinner accessibility', () => {
  it('announces loading text without exposing its decorative animation', () => {
    const wrapper = mount(LoadingSpinner, { props: { text: 'Loading reservations…' } })
    const status = wrapper.get('[role="status"]')

    expect(status.attributes('aria-live')).toBe('polite')
    expect(status.attributes('aria-busy')).toBe('true')
    expect(status.text()).toBe('Loading reservations…')
    expect(wrapper.get('.spinner').attributes('aria-hidden')).toBe('true')
  })
})
