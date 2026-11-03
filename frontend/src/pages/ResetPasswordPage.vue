<template>
  <div class="container recovery-page">
    <h1>{{ t('core.resetTitle') }}</h1>
    <p v-if="complete" role="status">{{ t('core.resetComplete') }} <button class="button button--primary" @click="openLogin()">{{ t('core.signInSentence') }}</button></p>
    <form v-else class="card recovery-form" @submit.prevent="submit">
      <AppInput v-model="email" :label="t('core.email')" type="email" autocomplete="email" required :disabled="codeSent" />
      <template v-if="codeSent">
        <p>{{ t('core.recoverySent') }}</p>
        <I18nT v-if="localCode" keypath="core.localCode" :i18n="i18n.global" tag="p" role="status"><template #code><strong>{{ localCode }}</strong></template></I18nT>
        <AppInput v-model="code" :label="t('core.recoveryCode')" autocomplete="one-time-code" required />
        <AppInput v-model="password" :label="t('core.recoveryNewPassword')" type="password" autocomplete="new-password" required />
        <p>{{ t('core.passwordPolicy') }}</p>
        <AppInput v-model="confirmation" :label="t('core.recoveryConfirmPassword')" type="password" autocomplete="new-password" required />
      </template>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <AppButton type="submit" :loading="busy">{{ t(codeSent ? 'core.saveNewPassword' : 'core.sendRecovery') }}</AppButton>
      <button v-if="codeSent" type="button" class="button button--secondary" :disabled="busy" @click="codeSent = false; code = ''; clearError()">{{ t('core.anotherEmail') }}</button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { t, i18n } from '@/i18n'
import { I18nT } from 'vue-i18n'
import { ref, computed } from 'vue'
import { translateApiMessage } from '@/i18n/errors'
import { isApiError } from '@/services/http/api-client'
import { getServerErrorMessage } from '@/shared/helpers/http-error-helpers'
import { authApi } from '@/services/api'
import { isPasswordAcceptable } from '@/components/auth/password-rules'
import { openLogin } from '@/components/auth/login-modal'
import AppInput from '@/components/shared/AppInput.vue'
import AppButton from '@/components/shared/AppButton.vue'
const email = ref('')
const code = ref('')
const password = ref('')
const confirmation = ref('')
const localCode = ref('')
const codeSent = ref(false)
const complete = ref(false)
const busy = ref(false)
const errorKey = ref('')
const serverError = ref<unknown>(null)
const error = computed(() => {
  if (errorKey.value) return t(errorKey.value)
  const value = serverError.value
  const raw = isApiError(value) ? getServerErrorMessage(value.body) || value.message : value instanceof Error ? value.message : ''
  return raw ? translateApiMessage(raw) : ''
})
function clearError(): void { errorKey.value = ''; serverError.value = null }
async function submit(): Promise<void> {
  clearError()
  if (codeSent.value && (!isPasswordAcceptable(password.value) || password.value !== confirmation.value)) {
    errorKey.value = 'core.checkPasswords'
    return
  }
  busy.value = true
  try {
    if (codeSent.value) {
      await authApi.resetPassword(email.value.trim(), code.value.trim(), password.value)
      complete.value = true
      password.value = ''; confirmation.value = ''; code.value = ''; localCode.value = ''
    } else {
      const result = await authApi.forgotPassword(email.value.trim())
      localCode.value = result.resetCode ?? ''
      codeSent.value = true
    }
  } catch (err) { if (err instanceof Error) serverError.value = err; else errorKey.value = 'core.retry' }
  finally { busy.value = false }
}
</script>

<style scoped>
.recovery-page { padding: 32px 16px 48px; max-width: 560px; }
.recovery-form { padding: 24px; display: grid; gap: 16px; }
.form-error { color: var(--red-600); }
</style>
