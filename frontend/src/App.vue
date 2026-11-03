<template>
  <AppHeader @open-login="openLogin()" />
  <component :is="route.meta.ownsMainLandmark ? 'div' : 'main'" class="main-content">
    <RouterView />
  </component>
  <AppToast />
  <LoginModal v-if="loginModal.open" @close="closeLogin()" />
</template>

<script setup lang="ts">
import { watch, onMounted, onBeforeUnmount } from 'vue'
import { t, locale } from '@/i18n'
import { installNativeValidation } from '@/i18n/validation'
import { useAuthStore } from '@/stores/auth'
import { openLogin, closeLogin, useLoginModal } from '@/components/auth/login-modal'
import { useRoute, useRouter } from 'vue-router'
import AppHeader from './components/layout/AppHeader.vue'
import AppToast from './components/layout/AppToast.vue'
import LoginModal from './components/auth/LoginModal.vue'

const route = useRoute()
const loginModal = useLoginModal()
const auth = useAuthStore()
const router = useRouter()
let removeNativeValidation: (() => void) | undefined
onMounted(() => { removeNativeValidation = installNativeValidation(t, locale) })
onBeforeUnmount(() => removeNativeValidation?.())
watch(() => auth.isAuthenticated, authenticated => {
  if (!authenticated && route.meta.requireAuth) void router.push('/main')
})
</script>

<style scoped>
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
}
</style>
