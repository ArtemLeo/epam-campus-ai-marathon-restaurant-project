import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AppModal from './AppModal.vue'

describe('AppModal accessibility', () => {
  it('uses its visible heading as the dialog name', () => {
    const wrapper = mount(AppModal, {
      props: { title: 'Edit reservation' },
      global: { stubs: { teleport: true } },
    })
    const dialog = wrapper.get('[role="dialog"]')
    const heading = wrapper.get('h2')

    expect(dialog.attributes('aria-modal')).toBe('true')
    expect(dialog.attributes('aria-labelledby')).toBe(heading.attributes('id'))
    expect(heading.text()).toBe('Edit reservation')
  })
})
