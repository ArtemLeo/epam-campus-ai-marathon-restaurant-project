import { describe, expect, it } from 'vitest'
import { bookingSearchStart, dateTimeParts, restaurantDateTimeToIso } from './date-time'

describe('restaurant booking timezone', () => {
  it('round-trips a restaurant wall time independently of the browser timezone', () => {
    const instant = restaurantDateTimeToIso('2026-11-04', '14:30', 'Asia/Tbilisi')
    expect(instant).toBe('2026-11-04T10:30:00.000Z')
    expect(dateTimeParts(instant!, 'Asia/Tbilisi')).toEqual({ date: '2026-11-04', time: '14:30' })
  })
  it('rejects a nonexistent spring-forward time and an ambiguous autumn time', () => {
    expect(restaurantDateTimeToIso('2026-03-29', '03:30', 'Europe/Kyiv')).toBeNull()
    expect(restaurantDateTimeToIso('2026-10-25', '03:30', 'Europe/Kyiv')).toBeNull()
    expect(restaurantDateTimeToIso('2026-03-29', '04:30', 'Europe/Kyiv')).toBe('2026-03-29T01:30:00.000Z')
  })
  it('does not send midnight in the past for today', () => {
    const now = Date.parse('2026-11-04T10:00:00Z')
    expect(Date.parse(bookingSearchStart('2026-11-04', now))).toBeGreaterThan(now)
    expect(bookingSearchStart('2026-11-05', now)).toBe('2026-11-04T20:00:00.000Z')
  })
  it('rejects invalid dates instead of normalizing them to another month', () => {
    expect(restaurantDateTimeToIso('2026-02-31', '12:00', 'Asia/Tbilisi')).toBeNull()
    expect(restaurantDateTimeToIso('2026-11-04', '27:00', 'Asia/Tbilisi')).toBeNull()
  })
})
