import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { reservationsApi, type Reservation } from '@/services/api'
import { restaurantDateTimeToIso } from '@/utils/date-time'
import type { ReservationCustomer } from '@/models/reservations/reservation.model'
import EditReservationModal from './EditReservationModal.vue'

describe('editing the last visit of the day', () => {
  it('offers 20:30 as the final start and saves a visit ending at closing time', async () => {
    vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-11-01T12:00:00Z'))
    vi.spyOn(reservationsApi, 'edit').mockResolvedValue({} as Reservation)
    const startTime = restaurantDateTimeToIso('2027-01-02', '20:30')!
    const wrapper = mount(EditReservationModal, { props: { reservation: { id: 'r1', startTime, guestCount: 2 } as ReservationCustomer } })
    const times = wrapper.findAll('option').map(option => option.element.value)
    expect(times.at(-1)).toBe('20:30')
    expect(times).not.toContain('21:00')
    expect(wrapper.get<HTMLSelectElement>('select').element.value).toBe('20:30')
    await wrapper.get('form').trigger('submit'); await flushPromises()
    expect(reservationsApi.edit).toHaveBeenCalledWith({ reservationId: 'r1', startTime, endTime: restaurantDateTimeToIso('2027-01-02', '22:00'), guestCount: 2 })
    expect(wrapper.emitted('saved')).toHaveLength(1)
    wrapper.unmount()
  })
})
