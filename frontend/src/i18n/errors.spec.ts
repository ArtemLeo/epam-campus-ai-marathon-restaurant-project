import { afterEach, describe, expect, it } from 'vitest'
import { locale, t } from './index'
import { translateApiMessage } from './errors'

afterEach(() => { locale.value = 'en' })

// Real backend messages: similar English words must not select an unrelated business explanation.
const cases = [
  ['Table number 3 already exists at this location.', 'tableNumberExists', 'номером'],
  ['Active order already exists for reservation r-1.', 'orderExists', 'кошик'],
  ['A user with this email address already exists.', 'emailExists', 'поштою'],
  ['The assigned waiter is no longer available. Choose another reservation.', 'waiterUnavailable', 'офіціанта'],
  ['No waiters found for location ID l-1.', 'waiterUnavailable', 'офіціанта'],
  ['This waiter has active reservations. Complete or cancel them before removing the assignment.', 'waiterActive', 'призначення'],
  ['This user is already added to the waiters list', 'waiterExists', 'офіціантом'],
  ["Cannot delete table 't-1' because it has 2 active upcoming reservations.", 'deleteTable', 'активні бронювання'],
  ['Move or cancel all active reservations before deleting this location.', 'deleteLocationActive', 'видаленням ресторану'],
  ["Cannot delete location 'l-1' because it has active tables or assigned waiters.", 'deleteLocationLinked', 'столики'],
  ["Cannot delete dish 'd-1' because it is currently on the menu of 2 location(s).", 'deleteDishLinked', 'усіх меню'],
  ['Capacity must be 1–50 and table number must be positive.', 'invalidCapacity', 'від 1 до 50'],
  ['Capacity cannot be negative.', 'negativeCapacity', 'від’ємною'],
  ['This capacity is smaller than an existing reservation. Move or cancel that reservation first.', 'capacityReduction', 'зменшенням місткості'],
  ['The table was removed or its capacity changed. Choose another table.', 'tableChanged', 'видалили'],
  ['Guest count (6) exceeds table capacity (4).', 'capacity', 'Кількість гостей'],
  ['Guest count must be at least 1.', 'minimumGuests', 'щонайменше один'],
  ['Reservations must be made at least 15 minutes in advance.', 'advance', '15 хвилин'],
  ['End time (12:00) must be after start time (13:00).', 'timeOrder', 'пізнішим'],
  ['Reservations must be within 10:00–22:00 (Asia/Tbilisi).', 'hours', '22:00'],
  ['A reservation lasts 90 minutes.', 'duration', '90 хвилин'],
  ['Cannot query timeslots in the past.', 'past', 'майбутню'],
  ['No submitted guest sessions found to consolidate.', 'noSubmittedCarts', 'надісланий кошик'],
  ['Cannot update a cancelled or completed reservation status.', 'reservationFinished', 'бронювання'],
  ["Only reservations in 'Reserved' status can be cancelled.", 'reservationEditable', 'бронювання'],
  ['Submitted group orders are final.', 'groupSent', 'Спільне замовлення'],
  ["Invalid dish IDs in order items or some dishes aren't available.", 'unavailable', 'страва'],
  ['The old password is incorrect or the session has expired.', 'passwordSession', 'увійдіть знову'],
] as const

describe('business error translations', () => {
  it.each(cases)('maps %s to its actual business reason', (message, key, ukrainianMeaning) => {
    locale.value = 'uk'
    expect(translateApiMessage(message)).toContain(ukrainianMeaning)
    for (const language of ['uk', 'fr', 'es', 'de'] as const) {
      locale.value = language
      expect(translateApiMessage(message)).toBe(t(`errors.${key}`))
      expect(translateApiMessage(message)).not.toBe(message)
    }
    locale.value = 'en'
    expect(translateApiMessage(message)).toBe(message)
  })

  it('does not mistake unrelated availability, duplicate or password policy errors for another issue', () => {
    locale.value = 'uk'
    for (const message of ['A document already exists.', 'An external service is unavailable.', 'Invalid password: policy requirement failed.']) {
      expect(translateApiMessage(message, 400)).toBe(t('errors.invalid'))
    }
    expect(translateApiMessage('An external service is unavailable.', 503)).toBe(t('errors.server'))
  })

  it('can retranslate a visible known error after the interface language changes', () => {
    locale.value = 'fr'
    const message = translateApiMessage('Table number 3 already exists at this location.')
    locale.value = 'de'
    expect(translateApiMessage(message)).toBe(t('errors.tableNumberExists'))
    locale.value = 'en'
    expect(translateApiMessage(message)).toBe(t('errors.tableNumberExists'))
  })
})
