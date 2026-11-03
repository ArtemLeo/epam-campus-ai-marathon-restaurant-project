<template>
  <div class="app-input" :class="{ 'app-input--error': error }">
    <label v-if="label" :for="inputId" class="app-input__label">{{ label }}</label>
    <div class="app-input__wrapper">
      <span v-if="$slots.prefix" class="app-input__prefix"><slot name="prefix" /></span>
      <input
        :id="inputId"
        class="app-input__field"
        v-bind="$attrs"
        :type="type"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        @input="onInput"
        @blur="emit('blur', $event)"
      />
      <span v-if="$slots.suffix" class="app-input__suffix"><slot name="suffix" /></span>
    </div>
    <p v-if="error" class="app-input__error">{{ error }}</p>
    <p v-if="hint && !error" class="app-input__hint">{{ hint }}</p>
  </div>
</template>

<script setup lang="ts">
import { useId } from 'vue'

withDefaults(
  defineProps<{
    modelValue?: string | number
    label?: string
    type?: string
    placeholder?: string
    error?: string
    hint?: string
    disabled?: boolean
  }>(),
  {
    modelValue: '',
    label: '',
    type: 'text',
    placeholder: '',
    error: '',
    hint: '',
    disabled: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  blur: [event: FocusEvent]
}>()

// useId() keeps <label for> unique per instance (a module counter gave every input the same id).
const inputId = useId()

function onInput(event: Event): void {
  emit('update:modelValue', (event.target as HTMLInputElement).value)
}
</script>

<style scoped>
.app-input {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.app-input__label {
  font-size: 13px;
  font-weight: 500;
  color: var(--neutral-700);
}

.app-input__wrapper {
  display: flex;
  align-items: center;
  border: 1.5px solid var(--neutral-200);
  border-radius: var(--radius-md);
  background: var(--neutral-0);
  transition: border-color 0.15s;
  overflow: hidden;
}

.app-input__wrapper:focus-within {
  border-color: var(--green-400);
}

.app-input--error .app-input__wrapper {
  border-color: var(--red-400);
}

.app-input__field {
  flex: 1;
  border: none;
  outline: none;
  padding: 10px 14px;
  font-family: 'Poppins', sans-serif;
  font-size: 14px;
  color: var(--neutral-900);
  background: transparent;
  min-width: 0;
}

.app-input__field::placeholder {
  color: var(--neutral-400);
}

.app-input__field:disabled {
  background: var(--neutral-100);
  cursor: not-allowed;
}

.app-input__prefix,
.app-input__suffix {
  padding: 0 10px;
  color: var(--neutral-400);
  display: flex;
  align-items: center;
}

.app-input__error {
  margin: 0;
  font-size: 12px;
  color: var(--red-400);
}

.app-input__hint {
  margin: 0;
  font-size: 12px;
  color: var(--neutral-400);
}
</style>

