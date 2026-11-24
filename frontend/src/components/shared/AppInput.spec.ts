import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AppInput from './AppInput.vue'

describe('AppInput accessibility', () => {
  it('connects an invalid field to its error message', () => {
    const wrapper = mount(AppInput, { props: { label: 'Email', error: 'Enter a valid email.' } })
    const input = wrapper.get('input')
    const error = wrapper.get('.app-input__error')

    expect(input.attributes('aria-invalid')).toBe('true')
    expect(input.attributes('aria-describedby')).toBe(error.attributes('id'))
  })

  it('connects a valid field to its hint', () => {
    const wrapper = mount(AppInput, { props: { label: 'Password', hint: 'Use at least eight characters.' } })
    const input = wrapper.get('input')
    const hint = wrapper.get('.app-input__hint')

    expect(input.attributes('aria-invalid')).toBeUndefined()
    expect(input.attributes('aria-describedby')).toBe(hint.attributes('id'))
  })
})
