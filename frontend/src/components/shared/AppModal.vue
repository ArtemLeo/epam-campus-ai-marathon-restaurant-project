<template>
  <Teleport to="body">
    <div class="modal-backdrop" role="presentation" @click.self="onBackdropClick">
      <div ref="panel" tabindex="-1" class="modal" :class="sizeClass" role="dialog" aria-modal="true" :aria-label="title || undefined">
        <div class="modal__header">
          <h2 class="modal__title">{{ title }}</h2>
          <button type="button" class="icon-button" :aria-label="t('core.close')" @click="emit('close')">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path d="M1 1l14 14M15 1L1 15" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            </svg>
          </button>
        </div>
        <div class="modal__body">
          <slot />
        </div>
        <div v-if="$slots.footer" class="modal__footer">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { t } from '@/i18n'
import { ref, computed } from 'vue'
import { useDialogFocus } from '@/composables/useDialogFocus'

const props = withDefaults(
  defineProps<{
    title?: string
    size?: 'sm' | 'md' | 'lg'
    closeOnBackdrop?: boolean
  }>(),
  {
    title: '',
    size: 'md',
    closeOnBackdrop: true,
  },
)

const emit = defineEmits<{ close: [] }>()

const sizeClass = computed(() => `modal--${props.size}`)

function onBackdropClick(): void {
  if (props.closeOnBackdrop) emit('close')
}

const panel = ref<HTMLElement | null>(null)
useDialogFocus(panel, () => emit('close'))
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.modal {
  background: var(--neutral-0);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  max-height: 90vh;
  overflow-y: auto;
  width: 100%;
  animation: modalIn 0.2s ease;
}

.modal--sm { max-width: 400px; }
.modal--md { max-width: 520px; }
.modal--lg { max-width: 720px; }

@keyframes modalIn {
  from { opacity: 0; transform: translateY(-20px) scale(0.97); }
  to   { opacity: 1; transform: translateY(0)     scale(1); }
}

.modal__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--neutral-200);
}

.modal__title {
  margin: 0;
  font-size: 18px;
  font-weight: 500;
  line-height: 1.4;
  color: var(--neutral-900);
}

.modal__body {
  padding: 24px;
  flex: 1;
}

.modal__footer {
  padding: 16px 24px;
  border-top: 1px solid var(--neutral-200);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 480px) {
  .modal-backdrop {
    padding: 12px;
  }

  .modal__footer {
    flex-wrap: wrap;
  }
}
</style>
