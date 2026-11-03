import { nextTick, onMounted, onUnmounted, type Ref } from 'vue'

const dialogs: HTMLElement[] = []
let previousOverflow = ''

/** Shared keyboard and scroll behavior, including a dialog opened on top of the cart. */
export function useDialogFocus(panel: Ref<HTMLElement | null>, close: () => void): void {
  let element: HTMLElement | null = null
  let previousFocus: HTMLElement | null = null
  function focusable(): HTMLElement[] {
    return element ? [...element.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]')].filter(e => !e.hidden && e.getAttribute('aria-hidden') !== 'true') : []
  }
  function keydown(event: KeyboardEvent): void {
    if (dialogs.at(-1) !== element) return
    if (event.key === 'Escape') { event.preventDefault(); event.stopImmediatePropagation(); close() }
    if (event.key !== 'Tab') return
    const items = focusable()
    const first = items[0]
    const last = items.at(-1)
    if (!first || !last) { event.preventDefault(); element?.focus(); return }
    if (event.shiftKey && (document.activeElement === first || document.activeElement === element)) { event.preventDefault(); last.focus() }
    else if (!event.shiftKey && (document.activeElement === last || document.activeElement === element)) { event.preventDefault(); first.focus() }
  }
  onMounted(async () => {
    previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    element = panel.value
    if (!element) return
    if (!dialogs.length) { previousOverflow = document.body.style.overflow; document.body.style.overflow = 'hidden' }
    dialogs.push(element)
    document.addEventListener('keydown', keydown)
    await nextTick()
    if (dialogs.at(-1) === element) (focusable()[0] ?? element).focus()
  })
  onUnmounted(() => {
    document.removeEventListener('keydown', keydown)
    const index = element ? dialogs.indexOf(element) : -1
    if (index >= 0) dialogs.splice(index, 1)
    if (!dialogs.length) document.body.style.overflow = previousOverflow
    if (previousFocus?.isConnected) previousFocus.focus()
  })
}
