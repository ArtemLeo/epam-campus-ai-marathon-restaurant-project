import { watch } from 'vue'
import { locale, t } from '@/i18n'
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { openLogin } from '@/components/auth/login-modal'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    requireAuth?: boolean
    guestOnly?: boolean
    requireRole?: 'Admin' | 'Waiter' | 'Customer'
    /** The page renders its own <main> landmark, so the layout must not wrap it in another one. */
    ownsMainLandmark?: boolean
  }
}

// Lazy-loaded pages
const MainPage = () => import('../pages/MainPage.vue')
const RegisterPage = () => import('../pages/RegisterPage.vue')
const ProfilePage = () => import('../pages/ProfilePage.vue')
const MenuPage = () => import('../pages/MenuPage.vue')
const TablesPage = () => import('../pages/TablesPage.vue')
const LocationOverviewPage = () => import('../pages/LocationOverviewPage.vue')
const ReservationDashboard = () => import('../pages/ReservationDashboardPage.vue')
const GroupOrderPage = () => import('../pages/GroupOrderPage.vue')
const WaiterDashboard = () => import('../pages/WaiterDashboardPage.vue')
const ReportingDashboard = () => import('../pages/ReportingDashboardPage.vue')
const WaiterPreOrderPage = () => import('../pages/WaiterPreOrderPage.vue')
const GuestPreOrderPage = () => import('../pages/GuestPreOrderPage.vue')
const GuestPreOrderExpired = () => import('../pages/GuestPreOrderExpiredPage.vue')
const AdminPanelPage = () => import('../pages/AdminPanelPage.vue')
const FeedbackPage = () => import('../pages/FeedbackPage.vue')

export const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/main' },
  { path: '/main', component: MainPage, meta: { title: 'core.main' } },
  { path: '/forgot-password', component: () => import('../pages/ResetPasswordPage.vue'), meta: { title: 'core.resetTitle' } },
  { path: '/signup', component: RegisterPage, meta: { title: 'core.createAccount', guestOnly: true } },
  { path: '/profile', component: ProfilePage, meta: { title: 'core.profile', requireAuth: true } },
  { path: '/menu', component: MenuPage, meta: { title: 'core.menu' } },
  { path: '/tables', component: TablesPage, meta: { title: 'core.tables' } },
  { path: '/locations/:id', component: LocationOverviewPage, meta: { title: 'customer.locationsTitle' } },
  {
    path: '/reservations',
    component: ReservationDashboard,
    meta: { title: 'core.reservations', requireAuth: true, requireRole: 'Customer' },
  },
  {
    // The group owner reviews every guest cart and submits one combined pre-order.
    path: '/reservations/:reservationId/group-order',
    component: GroupOrderPage,
    props: true,
    meta: { title: 'orders.groupTitle', requireAuth: true, ownsMainLandmark: true },
  },
  {
    path: '/waiter-reservations',
    component: WaiterDashboard,
    meta: { title: 'core.waiterDashboard', requireAuth: true, requireRole: 'Waiter' },
  },
  {
    path: '/reports',
    component: ReportingDashboard,
    meta: { title: 'core.reports', requireAuth: true, requireRole: 'Admin' },
  },
  {
    path: '/admin',
    component: AdminPanelPage,
    meta: { title: 'core.admin', requireAuth: true, requireRole: 'Admin' },
  },
  { path: '/feedback', component: FeedbackPage, meta: { title: 'customer.reviewsTitle' } },
  {
    path: '/waiter-pre-order',
    component: WaiterPreOrderPage,
    meta: { title: 'core.preOrder', requireAuth: true, requireRole: 'Waiter' },
  },
  { path: '/join/:token', component: GuestPreOrderPage, meta: { title: 'orders.joinGroup' } },
  { path: '/guest-pre-order-expired', component: GuestPreOrderExpired, meta: { title: 'orders.sessionExpired' } },
  // Fallback
  { path: '/:pathMatch(.*)*', redirect: '/main' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

// Navigation guards
router.beforeEach((to) => {
  const auth = useAuthStore()


  // Redirect logged-in users away from guest-only pages
  if (to.meta.guestOnly && auth.isAuthenticated) return '/main'

  // Require authentication
  if (to.meta.requireAuth && !auth.isAuthenticated) { openLogin(to.fullPath); return '/main' }

  // Require specific role
  const role = to.meta.requireRole
  if (role === 'Admin' && !auth.isAdmin) return '/main'
  if (role === 'Waiter' && !auth.isWaiter && !auth.isAdmin) return '/main'
  if (role === 'Customer' && !auth.isCustomer && !auth.isAdmin) return '/main'
  return true
})

watch([locale, () => router.currentRoute.value.meta.title], () => {
  const title = router.currentRoute.value.meta.title
  document.title = title ? `${t(title)} — Restaurant` : 'Restaurant'
}, { immediate: true })

export default router
