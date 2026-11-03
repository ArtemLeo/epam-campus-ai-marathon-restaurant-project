<template>
  <header class="app-header">
    <div class="container header-inner">
      <!-- Logo -->
      <RouterLink to="/main" class="logo">
        <img src="/assets/svg/logo.svg" :alt="t('core.logo')" class="logo__img" />
        <span class="logo__text">{{ t('core.restaurant') }}</span>
      </RouterLink>

      <!-- Primary nav -->
      <nav class="nav">
        <RouterLink to="/main" class="nav__link">{{ t('core.main') }}</RouterLink>
        <RouterLink to="/menu" class="nav__link">{{ t('core.menu') }}</RouterLink>
        <RouterLink to="/tables" class="nav__link">{{ t('core.tables') }}</RouterLink>

        <!-- Admin links -->
        <template v-if="auth.isAdmin">
          <RouterLink to="/admin" class="nav__link">{{ t('core.admin') }}</RouterLink>
          <RouterLink to="/reports" class="nav__link">{{ t('core.reports') }}</RouterLink>
        </template>

        <!-- Waiter links -->
        <template v-if="auth.isWaiter">
          <RouterLink to="/waiter-reservations" class="nav__link">{{ t('core.waiterDashboard') }}</RouterLink>
          <RouterLink to="/waiter-pre-order" class="nav__link">{{ t('core.preOrder') }}</RouterLink>
        </template>

        <!-- Customer links -->
        <template v-if="auth.isCustomer">
          <RouterLink to="/reservations" class="nav__link">{{ t('core.reservations') }}</RouterLink>
        </template>
      </nav>

      <select class="language-select" :value="locale" :aria-label="t('core.language')" @change="setLocale(($event.target as HTMLSelectElement).value)">
        <option v-for="code in supportedLocales" :key="code" :value="code" :lang="code">{{ languageNames[code] }}</option>
      </select>

      <!-- Right side actions -->
      <div class="header-actions">
        <template v-if="auth.isAuthenticated">
          <!-- Notifications -->
          <div v-if="auth.isWaiter" ref="notifRef" class="notifications-wrapper">
            <button class="icon-button notifications-btn" :title="t('core.notifications')" :aria-expanded="showNotifications" @click="toggleNotifications">
              <img src="/assets/svg/bell.svg" :alt="t('core.notifications')" />
              <span v-if="notifStore.unreadCount > 0" class="badge-dot">{{ notifStore.unreadCount }}</span>
            </button>
            <div v-if="showNotifications" class="notifications-dropdown">
              <div class="notifications-dropdown__header">
                <span>{{ t('core.notifications') }}</span>
                <button class="button button--tertiary" @click="notifStore.markAllAsRead()">{{ t('core.markRead') }}</button>
              </div>
              <div v-if="notifStore.notifications.length === 0" class="notifications-dropdown__empty">
                {{ t('core.noNotifications') }}
              </div>
              <ul v-else class="notifications-list">
                <li
                  v-for="n in notifStore.notifications"
                  :key="n.id"
                  class="notifications-list__item"
                  :class="{ 'notifications-list__item--unread': !n.isRead }"
                  role="button"
                  tabindex="0" @click="notifStore.markAsRead(n.id)"
                  @keydown.enter="notifStore.markAsRead(n.id)"
                  @keydown.space.prevent="notifStore.markAsRead(n.id)"
                >
                  <p class="notifications-list__msg">{{ notificationMessage(n) }}</p>
                </li>
              </ul>
            </div>
          </div>

          <!-- Cart -->
          <CartButton />

          <!-- User name -->
          <RouterLink to="/profile" class="user-name">
            {{ auth.fullName }}
          </RouterLink>

          <!-- Logout -->
          <button class="button button--secondary button--small" @click="handleLogout">
            {{ t('core.logout') }}
          </button>
        </template>

        <template v-else>
          <button class="button button--primary button--large" @click="$emit('open-login')">
            {{ t('core.login') }}
          </button>
        </template>
      </div>

      <!-- Mobile menu toggle -->
      <button class="icon-button mobile-menu-btn" :aria-label="t('core.toggleNav')" :aria-expanded="mobileOpen" @click="mobileOpen = !mobileOpen">
        <span class="hamburger"></span>
      </button>
    </div>

    <!-- Mobile nav -->
    <div v-if="mobileOpen" class="mobile-nav">
      <RouterLink to="/main" class="nav__link" @click="mobileOpen = false">{{ t('core.main') }}</RouterLink>
      <RouterLink to="/menu" class="nav__link" @click="mobileOpen = false">{{ t('core.menu') }}</RouterLink>
      <RouterLink to="/tables" class="nav__link" @click="mobileOpen = false">{{ t('core.tables') }}</RouterLink>
      <template v-if="auth.isAdmin">
        <RouterLink to="/admin" class="nav__link" @click="mobileOpen = false">{{ t('core.admin') }}</RouterLink>
        <RouterLink to="/reports" class="nav__link" @click="mobileOpen = false">{{ t('core.reports') }}</RouterLink>
      </template>
      <template v-if="auth.isWaiter">
        <RouterLink to="/waiter-reservations" class="nav__link" @click="mobileOpen = false">{{ t('core.waiterDashboard') }}</RouterLink>
        <RouterLink to="/waiter-pre-order" class="nav__link" @click="mobileOpen = false">{{ t('core.preOrder') }}</RouterLink>
      </template>
      <template v-if="auth.isCustomer">
        <RouterLink to="/reservations" class="nav__link" @click="mobileOpen = false">{{ t('core.reservations') }}</RouterLink>
      </template>
      <template v-if="auth.isAuthenticated">
        <RouterLink to="/profile" class="nav__link" @click="mobileOpen = false">{{ t('core.profile') }}</RouterLink>
        <button class="button button--secondary button--small" @click="handleLogout">{{ t('core.logout') }}</button>
      </template>
      <template v-else>
        <button class="button button--primary button--large" @click="() => { $emit('open-login'); mobileOpen = false }">{{ t('core.login') }}</button>
      </template>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { t, locale, setLocale, supportedLocales, languageNames } from '@/i18n'
import { notificationMessage } from '@/i18n/notifications'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { useNotificationsStore } from '../../stores/notifications'
import CartButton from '../cart/CartButton.vue'

defineEmits<{ 'open-login': [] }>()

const router = useRouter()
const auth = useAuthStore()
const notifStore = useNotificationsStore()
const mobileOpen = ref(false)
const showNotifications = ref(false)
const notifRef = ref<HTMLElement | null>(null)

// Notifications are addressed to waiters (same as the Angular header).
// Polled every 30s while signed in.
watch(
  () => auth.isAuthenticated && auth.isWaiter,
  (active) => {
    if (active) notifStore.startPolling()
    else notifStore.stopPolling()
  },
  { immediate: true },
)

function toggleNotifications(): void {
  showNotifications.value = !showNotifications.value
}

function handleClickOutside(event: MouseEvent): void {
  if (notifRef.value && !notifRef.value.contains(event.target as Node)) {
    showNotifications.value = false
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  notifStore.stopPolling()
})

async function handleLogout(): Promise<void> {
  auth.logout()
  mobileOpen.value = false
  await router.push('/main')
}
</script>

<style scoped>
.app-header {
  background: var(--neutral-0);
  box-shadow: var(--shadow-sm);
  position: sticky;
  top: 0;
  z-index: 100;
  border-bottom: 1px solid var(--neutral-200);
}

.header-inner {
  display: flex;
  align-items: center;
  height: 68px;
  gap: 16px;
}

.language-select { width: 120px; min-width: 0; flex-shrink: 0; padding: 8px 4px; border: 1px solid var(--neutral-200); border-radius: var(--radius-md); background: var(--neutral-0); color: var(--neutral-700); font: inherit; font-size: 13px; }
@media (max-width: 480px) {
  .header-inner { gap: 8px; }
  .logo__text { display: none; }
  .language-select { width: 112px; }
  .header-actions { gap: 4px; }
}
/* Logo */
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  flex-shrink: 0;
}

.logo__img {
  width: 36px;
  height: 36px;
  padding: 4px;
  border-radius: 50%;
  background: var(--green-700);
}

.logo__text {
  font-size: 18px;
  font-weight: 600;
  color: var(--green-800);
}

/* Nav */
.nav {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
}

.nav__link {
  padding: 8px 14px;
  border-radius: var(--radius-md);
  color: var(--neutral-600);
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  transition: all var(--transition-fast);
  position: relative;
}

.nav__link:hover {
  color: var(--green-600);
  background: var(--green-50);
  text-decoration: none;
}

.nav__link.router-link-active {
  color: var(--green-700);
  background: var(--green-100);
  font-weight: 600;
  text-decoration: none;
}

/* Right side */
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.user-name {
  font-weight: 500;
  color: var(--neutral-700);
  text-decoration: none;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color var(--transition-fast);
}

.user-name:hover {
  color: var(--green-600);
  text-decoration: none;
}

/* Notifications */
.notifications-wrapper {
  position: relative;
}

.notifications-btn {
  position: relative;
}

.badge-dot {
  position: absolute;
  top: 2px;
  right: 2px;
  background: var(--red-400);
  color: #fff;
  border-radius: 9999px;
  font-size: 10px;
  font-weight: 700;
  min-width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 3px;
}

.notifications-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 340px;
  background: var(--neutral-0);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  border: 1px solid var(--neutral-200);
  z-index: 200;
  overflow: hidden;
}

.notifications-dropdown__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid var(--neutral-200);
  font-weight: 600;
  font-size: 15px;
}

.notifications-dropdown__empty {
  padding: 28px;
  text-align: center;
  color: var(--neutral-400);
}

.notifications-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 320px;
  overflow-y: auto;
}

.notifications-list__item {
  padding: 12px 18px;
  border-bottom: 1px solid var(--neutral-100);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.notifications-list__item:hover {
  background: var(--neutral-50);
}

.notifications-list__item--unread {
  background: var(--green-50);
  border-left: 3px solid var(--green-400);
}

.notifications-list__msg {
  margin: 0;
  font-size: 13px;
}

/* Mobile */
.mobile-menu-btn {
  display: none;
}

.mobile-nav {
  display: none;
  flex-direction: column;
  gap: 4px;
  padding: 12px 24px 16px;
  border-top: 1px solid var(--neutral-200);
  background: var(--neutral-50);
}

@media (max-width: 1280px) {
  .nav { display: none; }
  .header-inner { gap: 12px; }
  .language-select { margin-left: auto; }
  .header-actions > .user-name, .header-actions > .button { display: none; }
  .notifications-dropdown { position: fixed; top: 72px; right: 16px; width: min(340px, calc(100vw - 32px)); }

  .mobile-menu-btn {
    display: flex;
    margin-left: 0;
  }

  .mobile-nav {
    display: flex;
  }

  .hamburger {
    display: block;
    width: 20px;
    height: 2px;
    background: var(--neutral-700);
    position: relative;
  }

  .hamburger::before,
  .hamburger::after {
    content: '';
    position: absolute;
    width: 100%;
    height: 2px;
    background: var(--neutral-700);
    left: 0;
  }

  .hamburger::before { top: -6px; }
  .hamburger::after  { top:  6px; }
}
</style>

