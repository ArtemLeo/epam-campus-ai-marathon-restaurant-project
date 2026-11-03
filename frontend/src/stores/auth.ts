import { defineStore } from 'pinia'
import { computed, ref, onScopeDispose } from 'vue'
import { useCartStore } from './cart'
import { useNotificationsStore } from './notifications'
import { setUnauthorizedHandler } from '@/services/http/api-client'
import { openLogin, clearDraft } from '@/components/auth/login-modal'
import { authApi, type RegisterRequest } from '@/services/api'
import {
  clearSession,
  isTokenValid,
  readStoredUser,
  readTokens,
  roleFromToken,
  writeTokens,
  tokenExpiresAt,
  writeUser,
} from '@/auth/auth-storage'
import type { Tokens } from '@/models/auth/tokens.model'
import type { UserModel } from '@/models/auth/user.model'
import { Roles } from '@/shared/constants/roles'

export type RegisterPayload = RegisterRequest

/** Session of the signed-in user (port of the Angular AuthenticationService). */
export const useAuthStore = defineStore('auth', () => {
  const tokens = ref<Tokens | null>(null)
  const user = ref<UserModel | null>(null)
  let expiryTimer: ReturnType<typeof setTimeout> | undefined

  function expire(): void {
    logout()
    openLogin(window.location.pathname + window.location.search)
  }
  function scheduleExpiry(): void {
    clearTimeout(expiryTimer)
    const expiry = tokens.value ? tokenExpiresAt(tokens.value.idToken) : null
    if (expiry !== null) expiryTimer = setTimeout(() => expiry > Date.now() ? scheduleExpiry() : expire(), Math.max(0, Math.min(expiry - Date.now(), 2_147_483_647)))
  }
  setUnauthorizedHandler(expire)
  onScopeDispose(() => clearTimeout(expiryTimer))

  function init(): void {
    const stored = readTokens()
    if (stored && isTokenValid(stored.idToken)) {
      tokens.value = stored
      user.value = readStoredUser()
      scheduleExpiry()
    } else {
      clearSession()
    }
  }

  const isAuthenticated = computed(() => isTokenValid(tokens.value?.idToken))
  // `/me` is the source of truth; the Cognito groups in the idToken are the fallback.
  const role = computed(() => user.value?.role || roleFromToken(tokens.value?.idToken) || null)
  const isAdmin = computed(() => role.value === Roles.ADMIN)
  const isWaiter = computed(() => role.value === Roles.WAITER)
  const isCustomer = computed(() => role.value === Roles.CUSTOMER)
  const fullName = computed(() => (user.value ? `${user.value.firstName} ${user.value.lastName}`.trim() : ''))

  /** Signs in and loads the profile. The login form reports failures itself, so no global toast. */
  async function login(email: string, password: string): Promise<void> {
    const data = await authApi.signIn(email, password, { skipErrorToast: true })
    useCartStore().reset()
    useNotificationsStore().reset()
    tokens.value = { idToken: data.idToken, accessToken: data.accessToken }
    writeTokens(tokens.value)
    try { await fetchMe(); scheduleExpiry() }
    catch (error) { logout(); throw error }
  }

  async function register(payload: RegisterPayload): Promise<{ message: string; confirmationRequired?: boolean }> {
    return authApi.register(payload, { skipErrorToast: true })
  }

  async function fetchMe(): Promise<void> {
    const currentToken = tokens.value?.idToken
    const data = await authApi.me()
    if (currentToken && currentToken === tokens.value?.idToken) { user.value = data; writeUser(data) }
  }

  async function updateProfile(firstName: string, lastName: string): Promise<void> {
    await authApi.updateMe(firstName, lastName)
    await fetchMe()
  }

  /** Cognito changes the password with the access token kept since sign-in. */
  async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
    const accessToken = tokens.value?.accessToken
    if (!accessToken || !isTokenValid(accessToken)) {
      logout()
      throw new Error('User is not authenticated. Please log in again.')
    }
    await authApi.changePassword(oldPassword, newPassword, accessToken, { skipErrorToast: true })
  }

  function logout(): void {
    clearTimeout(expiryTimer)
    useCartStore().reset()
    useNotificationsStore().reset()
    clearDraft()
    tokens.value = null
    user.value = null
    clearSession()
  }

  init()

  return {
    tokens,
    user,
    role,
    isAuthenticated,
    isAdmin,
    isWaiter,
    isCustomer,
    fullName,
    login,
    register,
    fetchMe,
    updateProfile,
    changePassword,
    logout,
  }
})
