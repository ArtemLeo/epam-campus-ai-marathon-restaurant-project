import { reactive, readonly } from 'vue'

/**
 * Who shows the Sign In dialog and what it remembers between openings.
 * The Angular app opened it on the `/login` URL; here `/login` (and any page that needs a session)
 * calls `openLogin()` and lands on /main with the dialog on top.
 */
const state = reactive({
  open: false,
  /** Page the visitor tried to open before being asked to sign in. */
  redirectTo: null as string | null,
  /** Typed values survive closing the dialog (Angular LoginDraftService). */
  draft: { email: '', password: '' },
})

export function openLogin(redirectTo: string | null = null): void {
  state.open = true
  state.redirectTo = redirectTo
}

export function closeLogin(): void {
  state.open = false
}

export function takeRedirect(): string | null {
  const target = state.redirectTo
  state.redirectTo = null
  return target
}

export function saveDraft(draft: { email: string; password: string }): void {
  state.draft = { ...draft }
}

export function clearDraft(): void {
  state.draft = { email: '', password: '' }
}

export function useLoginModal() {
  return readonly(state)
}
