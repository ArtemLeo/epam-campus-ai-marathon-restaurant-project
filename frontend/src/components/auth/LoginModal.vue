<template>
  <Teleport to="body">
    <div class="overlay" role="presentation" @click.self="close">
      <div ref="panel" tabindex="-1" class="modal" role="dialog" aria-modal="true" :aria-label="t('core.signIn')">
        <button type="button" class="icon-button modal-close" :aria-label="t('core.close')" @click="close">
          <img src="/assets/svg/close.svg" alt="" />
        </button>
        <LoginForm @success="onSuccess" @navigate="close" />
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { ref } from 'vue'
import { useDialogFocus } from '@/composables/useDialogFocus'
import { useRouter } from 'vue-router'
import LoginForm from '@/components/auth/LoginForm.vue'
import { takeRedirect } from '@/components/auth/login-modal'
import { useAuthStore } from '@/stores/auth'

const emit = defineEmits<{ close: [] }>()

const router = useRouter()
const auth = useAuthStore()

function close(): void {
  emit('close')
}

/** Same landing pages as the Angular login form; a page that asked for sign-in wins when the role may open it. */
function onSuccess(): void {
  const requested = takeRedirect()
  emit('close')
  const fallback = auth.isWaiter ? '/waiter-reservations' : auth.isAdmin ? '/admin' : '/main'
  void router.push(requested ?? fallback).catch(() => router.push(fallback))
}

const panel = ref<HTMLElement | null>(null)
useDialogFocus(panel, close)
</script>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: grid;
  place-items: center;
  padding: 16px;
  background: rgba(0, 0, 0, 0.28);
}

.modal {
  position: relative;
  width: min(450px, calc(100vw - 32px));
  max-height: calc(100vh - 48px);
  overflow: auto;
  padding: 30px 28px;
  border-radius: 16px;
  background: var(--neutral-0);
}

.modal-close {
  position: absolute;
  top: 16px;
  right: 16px;
}

@media (max-width: 540px) {
  .overlay {
    padding: 12px;
  }

  .modal {
    width: 100%;
    max-height: calc(100vh - 24px);
    padding: 16px;
    border-radius: 14px;
  }

  .modal-close {
    top: 10px;
    right: 10px;
  }
}
</style>
