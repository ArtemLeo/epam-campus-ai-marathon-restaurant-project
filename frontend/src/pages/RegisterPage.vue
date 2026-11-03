<template>
  <div class="auth-page">
    <div class="auth-card card">
      <div class="auth-card__logo">
        <img src="/assets/svg/logo.svg" :alt="t('core.logo')" />
        <span>{{ t('core.restaurant') }}</span>
      </div>

      <h3 class="auth-card__title">{{ t('core.createAccount') }}</h3>
      <p class="auth-card__sub text-muted">{{ t('core.registerSubtitle') }}</p>

      <form v-if="confirmationRequired" class="auth-form" @submit.prevent="confirmRegistration">
        <p>{{ t('core.codeSentTo', { email: form.email }) }}</p>
        <AppInput v-model="confirmationCode" :label="t('core.confirmationCode')" autocomplete="one-time-code" required />
        <p v-if="globalError" class="form-error" role="alert">{{ globalError }}</p>
        <AppButton type="submit" :loading="loading">{{ t('core.confirmEmail') }}</AppButton>
        <AppButton variant="secondary" :disabled="loading" @click="resendConfirmation">{{ t('core.resendCode') }}</AppButton>
      </form>
      <form v-else class="auth-form" @submit.prevent="handleSubmit">
        <div class="form-row">
          <AppInput
            v-model="form.firstName"
            :label="t('core.firstName')"
            :placeholder="t('core.firstNameExample')"
            :error="errors.firstName"
            required
          />
          <AppInput
            v-model="form.lastName"
            :label="t('core.lastName')"
            :placeholder="t('core.lastNameExample')"
            :error="errors.lastName"
            required
          />
        </div>

        <AppInput
          v-model="form.email"
          :label="t('core.email')"
          type="email"
          :placeholder="t('core.emailExample', { at: '@' })"
          :error="errors.email"
          required
        />

        <AppInput
          v-model="form.password"
          :label="t('core.password')"
          type="password"
          :placeholder="t('core.passwordHint')"
          :error="errors.password"
          required
        />

        <AppInput
          v-model="form.confirmPassword"
          :label="t('core.confirmPassword')"
          type="password"
          :placeholder="t('core.repeatPassword')"
          :error="errors.confirmPassword"
          required
        />

        <p v-if="globalError" class="form-error">{{ globalError }}</p>

        <AppButton type="submit" :loading="loading" full-width variant="primary" size="extra-large">
          {{ t('core.createAccount') }}
        </AppButton>

        <p class="auth-form__signin">
          {{ t('core.existingAccount') }}
          <button type="button" class="button button--tertiary" @click="openLogin()">{{ t('core.signInSentence') }}</button>
        </p>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { ref, reactive, computed } from 'vue'
import { translateApiMessage } from '@/i18n/errors'
import { isApiError } from '@/services/http/api-client'
import { getServerErrorMessage } from '@/shared/helpers/http-error-helpers'
import { useRouter, useRoute } from 'vue-router'
import { authApi } from '@/services/api'
import { openLogin } from '@/components/auth/login-modal'
import { isPasswordAcceptable, nameError, EMAIL_PATTERN } from '@/components/auth/password-rules'
import AppInput from '../components/shared/AppInput.vue'
import AppButton from '../components/shared/AppButton.vue'
import { useAuthStore } from '../stores/auth'
import { useToast } from '../composables/useToast'

const router = useRouter()
const route = useRoute()
const confirmationRequired = ref(typeof route.query.confirmEmail === 'string')
const confirmationCode = ref('')
const auth = useAuthStore()
const toast = useToast()

const loading = ref(false)
const serverError = ref<{ message: string; fallback: string } | null>(null)
const globalError = computed(() => serverError.value ? (serverError.value.message ? translateApiMessage(serverError.value.message) : t(serverError.value.fallback)) : '')
function showError(error: unknown, fallback: string): void {
  serverError.value = { message: isApiError(error) ? getServerErrorMessage(error.body) || error.message : error instanceof Error ? error.message : '', fallback }
}

const form = reactive({
  firstName: '',
  lastName: '',
  email: typeof route.query.confirmEmail === 'string' ? route.query.confirmEmail : '',
  password: '',
  confirmPassword: '',
})

const attempted = ref(false)
const errors = computed(() => ({
  firstName: attempted.value ? nameError(form.firstName.trim(), 'First name') : '',
  lastName: attempted.value ? nameError(form.lastName.trim(), 'Last name') : '',
  email: attempted.value && !EMAIL_PATTERN.test(form.email.trim()) ? t('core.validEmail') : '',
  password: attempted.value && !isPasswordAcceptable(form.password) ? t('core.passwordPolicy') : '',
  confirmPassword: attempted.value && form.password !== form.confirmPassword ? t('core.passwordMismatch') : '',
}))

function validate(): boolean {
  attempted.value = true
  return Object.values(errors.value).every((message) => !message)
}

async function handleSubmit(): Promise<void> {
  if (!validate()) return
  loading.value = true
  serverError.value = null
  try {
    const result = await auth.register({
      firstName: form.firstName.trim(),
      lastName: form.lastName.trim(),
      email: form.email.trim(),
      password: form.password,
      confirmPassword: form.confirmPassword,
    })
    form.password = ''; form.confirmPassword = ''
    attempted.value = false
    if (result.confirmationRequired) confirmationRequired.value = true
    else await finishRegistration()
  } catch (err) {
    showError(err, 'core.registerError')
  } finally {
    loading.value = false
  }
}
async function finishRegistration(): Promise<void> {
  toast.success(t('core.readyAccount'))
  await router.push('/main')
  openLogin()
}
async function confirmRegistration(): Promise<void> {
  loading.value = true; serverError.value = null
  try { await authApi.confirmRegistration(form.email.trim(), confirmationCode.value.trim()); await finishRegistration() }
  catch (err) { showError(err, 'core.confirmError') }
  finally { loading.value = false }
}
async function resendConfirmation(): Promise<void> {
  loading.value = true; serverError.value = null
  try { await authApi.resendConfirmation(form.email.trim()); toast.success(t('core.codeSent')) }
  catch (err) { showError(err, 'core.resendError') }
  finally { loading.value = false }
}
</script>

<style scoped>
.auth-page {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  background: var(--bg-green);
}

.auth-card {
  width: 100%;
  max-width: 520px;
  padding: 40px;
}

.auth-card__logo {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 24px;
}

.auth-card__logo img {
  width: 36px;
  height: 36px;
}

.auth-card__logo span {
  font-size: 18px;
  font-weight: 600;
  color: var(--green-800);
}

.auth-card__title {
  margin: 0 0 6px;
}

.auth-card__sub {
  margin: 0 0 24px;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.auth-form__signin {
  text-align: center;
  color: var(--neutral-600);
  font-size: 13px;
  margin: 0;
}

@media (max-width: 480px) {
  .auth-card { padding: 24px 20px; }
  .form-row  { grid-template-columns: 1fr; }
}
</style>

