import { ref } from 'vue'

export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface Toast {
  id: number
  type: ToastType
  message: string
  title?: string
}

// Same lifetimes as the Angular ToastService: errors stay a bit longer.
const DURATION_MS: Record<ToastType, number> = {
  success: 3000,
  info: 3000,
  warning: 4000,
  error: 5000,
}

const toasts = ref<Toast[]>([])
let nextId = 0

function remove(id: number): void {
  const index = toasts.value.findIndex((toast) => toast.id === id)
  if (index !== -1) toasts.value.splice(index, 1)
}

function show(type: ToastType, message: string, title?: string): void {
  const id = ++nextId
  toasts.value.push({ id, type, message, title })
  setTimeout(() => remove(id), DURATION_MS[type])
}

/** Test helper: forget every toast shown so far. */
export function clearToasts(): void {
  toasts.value = []
}

export function useToast() {
  return {
    toasts,
    remove,
    success: (message: string, title?: string) => show('success', message, title),
    error: (message: string, title?: string) => show('error', message, title),
    warning: (message: string, title?: string) => show('warning', message, title),
    info: (message: string, title?: string) => show('info', message, title),
  }
}
