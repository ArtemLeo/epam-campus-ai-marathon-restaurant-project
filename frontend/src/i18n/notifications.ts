import { t, locale } from './index'
import { localizedDish } from './catalog'
import { formatDate, formatNumber } from '@/utils/formatters'
import type { Notification } from '@/services/api/types'

export function notificationMessage(notification: Notification): string {
  if (!notification.kind) return locale.value === 'en' ? notification.message : t('core.notificationOrder')
  const heading = t('core.newOrderNotification', {
    kind: t(notification.kind === 'GroupOrder' ? 'core.notificationGroup' : 'core.notificationOrder'),
    table: notification.tableNumber ?? '—', address: notification.locationAddress ?? '',
    time: formatDate(notification.startTime),
  })
  const dishes = notification.dishes?.map(dish => `${formatNumber(dish.quantity)} × ${localizedDish(dish).name}`).join(', ')
  return dishes ? `${heading} ${dishes}.` : heading
}
