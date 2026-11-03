import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { notificationsApi, type Notification } from '@/services/api'

export const useNotificationsStore = defineStore('notifications', () => {
  const notifications = ref<Notification[]>([])
  const loading = ref(false)
  const unreadCount = computed(() => notifications.value.filter((item) => !item.isRead).length)

  let revision = 0
  async function fetchNotifications(): Promise<void> {
    const requestRevision = revision
    loading.value = true
    try {
      const result = await notificationsApi.unread({ skipErrorToast: true })
      if (requestRevision === revision) notifications.value = result ?? []
    } catch (err) {
      console.error('Failed to fetch notifications:', err)
    } finally {
      if (requestRevision === revision) loading.value = false
    }
  }

  async function markAsRead(id: string): Promise<void> {
    try {
      await notificationsApi.markRead(id)
      const notification = notifications.value.find((item) => item.id === id)
      if (notification) notification.isRead = true
    } catch (err) {
      console.error('Failed to mark notification as read:', err)
    }
  }

  async function markAllAsRead(): Promise<void> {
    for (const notification of notifications.value.filter((item) => !item.isRead)) {
      await markAsRead(notification.id)
    }
  }

  let timer: ReturnType<typeof setInterval> | null = null

  /** Fetch now and then every `intervalMs` until stopPolling(). */
  function startPolling(intervalMs = 30_000): void {
    stopPolling()
    void fetchNotifications()
    timer = setInterval(() => void fetchNotifications(), intervalMs)
  }

  function stopPolling(): void {
    if (timer) clearInterval(timer)
    timer = null
  }

  function reset(): void {
    revision++
    stopPolling()
    notifications.value = []
    loading.value = false
  }

  return {
    reset,
    startPolling,
    stopPolling,
    notifications,
    unreadCount,
    loading,
    fetchNotifications,
    markAsRead,
    markAllAsRead,
  }
})
