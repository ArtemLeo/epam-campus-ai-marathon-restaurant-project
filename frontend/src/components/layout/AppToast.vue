<template>
  <Teleport to="body">
    <div class="toast-container" role="status" aria-live="polite">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="toast"
          :class="`toast--${toast.type}`"
          @click="remove(toast.id)"
        >
          <span class="toast__icon">{{ icons[toast.type] }}</span>
          <span class="toast__msg">
            <strong v-if="toast.title" class="toast__title">{{ toast.title }}</strong>
            {{ toast.message }}
          </span>
          <button type="button" class="toast__close" :aria-label="t('core.dismiss')" @click.stop="remove(toast.id)">×</button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { useToast } from '../../composables/useToast'

const { toasts, remove } = useToast()

const icons = {
  success: '✓',
  error: '✕',
  warning: '⚠',
  info: 'ℹ',
} as const
</script>

<style scoped>
.toast-container {
  position: fixed;
  bottom: 24px;
  right: 16px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: min(360px, calc(100vw - 32px));
  width: 100%;
}

.toast {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  background: var(--neutral-0);
  box-shadow: var(--shadow-lg);
  border-left: 4px solid;
  cursor: pointer;
  font-size: 14px;
}

.toast--success { border-color: var(--green-400); }
.toast--error   { border-color: var(--red-400); }
.toast--warning { border-color: var(--orange-400); }
.toast--info    { border-color: var(--blue-400); }

.toast__icon {
  font-size: 16px;
  flex-shrink: 0;
}

.toast--success .toast__icon { color: var(--green-400); }
.toast--error   .toast__icon { color: var(--red-400); }
.toast--warning .toast__icon { color: var(--orange-400); }
.toast--info    .toast__icon { color: var(--blue-400); }

.toast__msg {
  flex: 1;
  color: var(--neutral-900);
}

.toast__title {
  display: block;
  font-weight: 600;
}

.toast__close {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 18px;
  color: var(--neutral-400);
  line-height: 1;
  padding: 0;
  flex-shrink: 0;
}

/* Transitions */
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(40px);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(40px);
}
</style>

