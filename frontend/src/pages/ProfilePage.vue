<template>
  <div class="profile-page container">
    <div class="page-header">
      <h2>{{ t('core.myProfile') }}</h2>
    </div>

    <LoadingSpinner v-if="loading" :text="t('core.loadingProfile')" />

    <div v-else class="profile-layout">
      <!-- Avatar -->
      <div class="profile-avatar-col">
        <div class="avatar-wrap card">
          <img
            :src="avatarSrc"
            :alt="t('core.profilePicture')"
            class="avatar-img"
            @error="avatarSrc = '/assets/img/avatar.png'"
          />
          <div class="avatar-actions">
            <label class="button button--secondary button--small" style="cursor:pointer">
              {{ t(uploadingPhoto ? 'core.uploading' : 'core.changePhoto') }}
              <input type="file" accept="image/jpeg,image/png,image/webp" :disabled="uploadingPhoto" class="sr-only" @change="handleImageUpload" />
            </label>
          </div>
          <div class="avatar-info">
            <h4>{{ auth.fullName }}</h4>
            <span class="badge badge--confirmed">{{ roleLabel(auth.user?.role) }}</span>
          </div>
        </div>
      </div>

      <!-- Profile info -->
      <div class="profile-info-col">
        <!-- Edit name -->
        <div class="card profile-section">
          <h4 class="profile-section__title">{{ t('core.personalInfo') }}</h4>
          <form @submit.prevent="saveProfile">
            <div class="form-row">
              <AppInput v-model="profileForm.firstName" :label="t('core.firstName')" :error="profileErrors.firstName" required />
              <AppInput v-model="profileForm.lastName" :label="t('core.lastName')" :error="profileErrors.lastName" required />
            </div>
            <AppInput :model-value="auth.user?.email ?? ''" :label="t('core.email')" disabled />
            <p v-if="profileMsg" class="profile-msg" :class="profileMsg.type === 'error' ? 'text-danger' : 'text-success'">
              {{ messageText(profileMsg) }}
            </p>
            <AppButton type="submit" :loading="savingProfile" size="large">{{ t('core.saveChanges') }}</AppButton>
          </form>
        </div>

        <!-- Change password -->
        <div class="card profile-section">
          <h4 class="profile-section__title">{{ t('core.changePassword') }}</h4>
          <form @submit.prevent="savePassword">
            <AppInput
              v-model="passwordForm.oldPassword"
              :label="t('core.currentPassword')"
              type="password"
              :error="passwordErrors.oldPassword"
              required
            />
            <AppInput
              v-model="passwordForm.newPassword"
              :label="t('core.newPassword')"
              type="password"
              :error="passwordErrors.newPassword"
              required
            />
            <AppInput
              v-model="passwordForm.confirmNew"
              :label="t('core.confirmNewPassword')"
              type="password"
              :error="passwordErrors.confirmNew"
              required
            />
            <p v-if="passwordMsg" class="profile-msg" :class="passwordMsg.type === 'error' ? 'text-danger' : 'text-success'">
              {{ messageText(passwordMsg) }}
            </p>
            <AppButton type="submit" :loading="savingPassword" size="large">{{ t('core.updatePassword') }}</AppButton>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { t, roleLabel } from '@/i18n'
import { ref, reactive, computed, onMounted } from 'vue'
import { translateApiMessage } from '@/i18n/errors'
import { isApiError } from '@/services/http/api-client'
import { getServerErrorMessage } from '@/shared/helpers/http-error-helpers'
import AppInput from '../components/shared/AppInput.vue'
import AppButton from '../components/shared/AppButton.vue'
import LoadingSpinner from '../components/shared/LoadingSpinner.vue'
import { useAuthStore } from '../stores/auth'
import { authApi } from '@/services/api'
import { isPasswordAcceptable, nameError } from '@/components/auth/password-rules'
import { useToast } from '../composables/useToast'

interface FormMessage {
  type: 'success' | 'error'
  key: string
  error?: unknown
}

const auth = useAuthStore()
const toast = useToast()
const loading = ref(false)

// Profile form
const profileForm = reactive({
  firstName: auth.user?.firstName || '',
  lastName: auth.user?.lastName || '',
})
const profileAttempted = ref(false)
const profileErrors = computed(() => ({
  firstName: profileAttempted.value ? nameError(profileForm.firstName.trim(), 'First name') : '',
  lastName: profileAttempted.value ? nameError(profileForm.lastName.trim(), 'Last name') : '',
}))
const profileMsg = ref<FormMessage | null>(null)
const savingProfile = ref(false)

// Password form
const passwordForm = reactive({ oldPassword: '', newPassword: '', confirmNew: '' })
const passwordAttempted = ref(false)
const passwordErrors = computed(() => ({
  oldPassword: passwordAttempted.value && !passwordForm.oldPassword ? t('core.required') : '',
  newPassword: passwordAttempted.value && !isPasswordAcceptable(passwordForm.newPassword) ? t('core.passwordPolicy') : '',
  confirmNew: passwordAttempted.value && passwordForm.newPassword !== passwordForm.confirmNew ? t('core.passwordMismatch') : '',
}))
const passwordMsg = ref<FormMessage | null>(null)
const savingPassword = ref(false)

const avatarSrc = ref('/assets/img/avatar.png')
const uploadingPhoto = ref(false)

async function loadPhoto(): Promise<void> {
  if (!auth.user?.id) return
  const image = await authApi.profileImage(auth.user.id, { skipErrorToast: true })
  avatarSrc.value = typeof image === 'object' ? image.presignedUrl : '/assets/img/avatar.png'
}

function messageText(message: FormMessage): string {
  const error = message.error
  const raw = isApiError(error) ? getServerErrorMessage(error.body) || error.message : error instanceof Error ? error.message : ''
  return raw ? translateApiMessage(raw) : t(message.key)
}

onMounted(async () => {
  loading.value = true
  try {
    await auth.fetchMe()
    profileForm.firstName = auth.user?.firstName || ''
    profileForm.lastName = auth.user?.lastName || ''
    await loadPhoto()
  } catch {
    // Failed API calls already display a message.
  } finally {
    loading.value = false
  }
})

async function saveProfile(): Promise<void> {
  profileAttempted.value = true
  if (profileErrors.value.firstName || profileErrors.value.lastName) return
  savingProfile.value = true
  profileMsg.value = null
  try {
    await auth.updateProfile(profileForm.firstName, profileForm.lastName)
    profileMsg.value = { type: 'success', key: 'core.profileSaved' }
    toast.success(t('core.profileToast'))
  } catch (err) {
    profileMsg.value = { type: 'error', key: 'core.profileError', error: err }
  } finally {
    savingProfile.value = false
  }
}

async function savePassword(): Promise<void> {
  passwordAttempted.value = true
  if (passwordErrors.value.oldPassword || passwordErrors.value.newPassword || passwordErrors.value.confirmNew) return
  savingPassword.value = true
  passwordMsg.value = null
  try {
    await auth.changePassword(passwordForm.oldPassword, passwordForm.newPassword)
    passwordMsg.value = { type: 'success', key: 'core.passwordSaved' }
    toast.success(t('core.passwordToast'))
    passwordForm.oldPassword = ''
    passwordForm.newPassword = ''
    passwordForm.confirmNew = ''
    passwordAttempted.value = false
  } catch (err) {
    passwordMsg.value = { type: 'error', key: 'core.passwordError', error: err }
  } finally {
    savingPassword.value = false
  }
}

function handleImageUpload(event: Event): void {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 3 * 1024 * 1024) { toast.error(t('core.photoHint')); return }
  uploadingPhoto.value = true
  const reader = new FileReader()
  reader.onload = async () => {
    const base64Image = String(reader.result).split(',')[1] ?? ''
    try {
      await authApi.uploadProfileImage(base64Image)
      await loadPhoto()
      toast.success(t('core.photoSaved'))
    } catch {
      // the API client has already shown the error toast
    } finally { uploadingPhoto.value = false }
  }
  reader.onerror = () => { uploadingPhoto.value = false; toast.error(t('core.photoReadError')) }
  reader.readAsDataURL(file)
}
</script>

<style scoped>
.profile-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 24px;
  align-items: start;
  padding-bottom: 48px;
}

.avatar-wrap {
  padding: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  text-align: center;
}

.avatar-img {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  object-fit: cover;
  border: 3px solid var(--green-150);
}

.avatar-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.avatar-info h4 { margin: 0; }

.profile-info-col {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.profile-section {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.profile-section__title {
  margin: 0;
}

.profile-section form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.profile-msg {
  margin: 0;
  font-size: 13px;
}

@media (max-width: 768px) {
  .profile-layout {
    grid-template-columns: 1fr;
  }
  .form-row {
    grid-template-columns: 1fr;
  }
}
</style>

