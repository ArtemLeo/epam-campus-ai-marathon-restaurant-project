<template>
  <form class="form" novalidate @submit.prevent="onSubmit">
    <h2 class="title">{{ t('core.signInTitle') }}</h2>

    <div v-if="isAccountLocked" class="banner-error" role="alert">
      {{ t('core.accountLocked') }}
    </div>

    <label class="field">
      <span class="label">{{ t('core.email') }}</span>
      <input
        v-model.trim="email"
        class="input"
        type="text"
        name="email"
        autocomplete="email"
        :placeholder="t('core.emailExample', { at: '@' })"
        :class="{ 'input-error': emailError }"
        :aria-invalid="emailError ? true : undefined"
        @blur="touched.email = true"
      />
      <span v-if="emailError" class="field-error">{{ emailError }}</span>
    </label>

    <div class="field">
      <label class="label" :for="passwordId">{{ t('core.password') }}</label>
      <div class="password-wrapper">
        <input
          :id="passwordId"
          v-model="password"
          class="input"
          :type="showPassword ? 'text' : 'password'"
          name="password"
          autocomplete="current-password"
          :class="{ 'input-error': passwordRequired || unsuccessfulLogin }"
          :aria-invalid="passwordRequired || unsuccessfulLogin ? true : undefined"
          @blur="touched.password = true"
        />
        <button
          type="button"
          class="eye-btn"
          :aria-label="t(showPassword ? 'core.hidePassword' : 'core.showPassword')"
          @click="showPassword = !showPassword"
        >
          <img :src="showPassword ? '/assets/svg/eye_closed.svg' : '/assets/svg/eye.svg'" alt="" />
        </button>
      </div>
      <span v-if="passwordRequired" class="field-error">
        {{ t('core.passwordRequired') }}
      </span>
      <span v-else-if="confirmationRequired" class="field-error">
        {{ t('core.confirmBeforeLogin') }}
        <RouterLink :to="{ path: '/signup', query: { confirmEmail: email } }" @click="emit('navigate')">{{ t('core.enterConfirmation') }}</RouterLink>
      </span>
      <span v-else-if="unsuccessfulLogin" class="field-error" role="alert">
        {{ t('core.invalidLogin') }}
      </span>
      <RouterLink class="forgot-link" to="/forgot-password" @click="emit('navigate')">{{ t('core.forgotPassword') }}</RouterLink>
    </div>

    <button type="submit" class="button button--primary button--extra-large button--full-width" :disabled="!isValid || loading">
      {{ t(loading ? 'core.signingIn' : 'core.signIn') }}
    </button>

    <div class="bottom">
      <span>{{ t('core.noAccount') }}</span>
      <RouterLink class="link" to="/signup" @click="emit('navigate')">{{ t('core.createAccountLink') }}</RouterLink>
    </div>
  </form>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { computed, reactive, ref, useId, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { clearDraft, saveDraft, useLoginModal } from '@/components/auth/login-modal'
import { getServerErrorMessage } from '@/shared/helpers/http-error-helpers'
import { isApiError } from '@/services/http/api-client'
import { EMAIL_PATTERN } from '@/components/auth/password-rules'

const emit = defineEmits<{ success: []; navigate: [] }>()

const auth = useAuthStore()
const modal = useLoginModal()
const passwordId = useId()

const email = ref(modal.draft.email)
const password = ref(modal.draft.password)
const showPassword = ref(false)
const loading = ref(false)
const unsuccessfulLogin = ref(false)
const errorMessage = ref<string | null>(null)
const confirmationRequired = ref(false)
const touched = reactive({ email: false, password: false })

// Keep what was typed when the dialog is closed and opened again.
watch([email, password], ([nextEmail, nextPassword]) => saveDraft({ email: nextEmail, password: nextPassword }))

const emailError = computed(() => {
  if (!touched.email) return ''
  if (!email.value) return t('core.emailRequired')
  if (!EMAIL_PATTERN.test(email.value)) return t('core.emailInvalid', { at: '@' })
  return ''
})
const passwordRequired = computed(() => touched.password && !password.value)
const isValid = computed(
  () => EMAIL_PATTERN.test(email.value) && password.value.length >= 8 && password.value.length <= 16,
)
const isAccountLocked = computed(() => {
  const message = (errorMessage.value ?? '').toLowerCase()
  return message.includes('locked') || message.includes('too many') || message.includes('attempts exceeded')
})

async function onSubmit(): Promise<void> {
  unsuccessfulLogin.value = false
  confirmationRequired.value = false
  errorMessage.value = null
  if (!isValid.value) {
    touched.email = true
    touched.password = true
    return
  }
  loading.value = true
  try {
    await auth.login(email.value, password.value)
    clearDraft()
    emit('success')
  } catch (error) {
    unsuccessfulLogin.value = true
    confirmationRequired.value = isApiError(error) && !!error.body && typeof error.body === 'object' && 'errorCode' in error.body && error.body.errorCode === 'ConfirmationRequired'
    errorMessage.value = isApiError(error) ? getServerErrorMessage(error.body) || error.message : null
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.title {
  margin: 0 0 8px;
  font-size: 26px;
  line-height: 28px;
  font-weight: 500;
  color: var(--neutral-900);
}

.banner-error {
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--red-100);
  font-size: 14px;
  line-height: 24px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.label {
  font-size: 12px;
  line-height: 16px;
  color: var(--neutral-900);
  font-weight: 500;
}

.input {
  width: 100%;
  height: 40px;
  border-radius: 8px;
  border: 1px solid var(--neutral-200);
  padding: 0 12px;
  font: inherit;
  font-size: 14px;
  color: var(--neutral-900);
  outline: none;
}

.input::placeholder {
  color: var(--neutral-400);
}

.input:focus-visible {
  border-color: var(--orange-400);
}

.input-error {
  border-color: var(--red-400) !important;
}

.field-error {
  color: var(--red-400);
  font-size: 12px;
  line-height: 16px;
}

.password-wrapper {
  position: relative;
  width: 100%;
}

.password-wrapper .input {
  padding-right: 44px;
}

.eye-btn {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0;
}

.eye-btn img {
  width: 18px;
  height: 18px;
}

.forgot-link {
  align-self: flex-end;
  font-size: 14px;
  line-height: 16px;
  color: var(--blue-500);
  font-weight: 600;
  text-decoration: underline;
}

.forgot-link:hover {
  text-decoration: none;
}

.bottom {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
  font-size: 12px;
  line-height: 16px;
  color: var(--neutral-600);
}

.link {
  color: var(--blue-500);
  font-size: 14px;
  font-weight: 600;
  text-decoration: underline;
}

.link:hover {
  text-decoration: none;
}

@media (max-width: 540px) {
  .form {
    gap: 16px;
  }

  .title {
    font-size: 20px;
  }
}
</style>
