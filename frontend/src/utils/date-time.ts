/** One restaurant timezone for searches, forms and displayed booking times. API instants stay UTC. */
export const RESTAURANT_TIMEZONE = import.meta.env.VITE_RESTAURANT_TIMEZONE || 'Asia/Tbilisi'

export function dateTimeParts(value: Date | string | number, timeZone = RESTAURANT_TIMEZONE): { date: string; time: string } {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(new Date(value))
  const get = (name: string) => parts.find(p => p.type === name)?.value ?? ''
  return { date: `${get('year')}-${get('month')}-${get('day')}`, time: `${get('hour')}:${get('minute')}` }
}

/** Reject nonexistent/ambiguous DST wall times instead of silently moving a booking by an hour. */
export function restaurantDateTimeToIso(date: string, time: string, timeZone = RESTAURANT_TIMEZONE): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}$/.test(time)) return null
  const wall = Date.parse(`${date}T${time}:00Z`)
  if (!Number.isFinite(wall)) return null
  const offsets = new Set<number>()
  for (const shift of [-86_400_000, 0, 86_400_000]) {
    const sample = wall + shift
    const parts = dateTimeParts(sample, timeZone)
    offsets.add(Date.parse(`${parts.date}T${parts.time}:00Z`) - sample)
  }
  const matches = [...offsets].map(offset => wall - offset).filter(instant => {
    const parts = dateTimeParts(instant, timeZone)
    return parts.date === date && parts.time === time
  })
  return matches.length === 1 ? new Date(matches[0]!).toISOString() : null
}

export function restaurantToday(now = Date.now()): string {
  return dateTimeParts(now).date
}

/** A search for today starts now; future dates start at the restaurant's midnight. */
export function bookingSearchStart(day: string, now = Date.now()): string {
  const midnight = restaurantDateTimeToIso(day, '00:00')
  if (!midnight) throw new Error('This date is invalid in the restaurant timezone.')
  return new Date(Math.max(Date.parse(midnight), now + 1000)).toISOString()
}
