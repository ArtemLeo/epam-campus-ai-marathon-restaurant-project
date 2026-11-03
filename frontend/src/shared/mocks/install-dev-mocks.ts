import { setMockHandler } from '@/services/http/api-client'
import { applyDemoLoginFromUrl } from './auth/demo-auth'
import { createGroupOrdersMockHandler } from './group-orders/group-orders.mock-handler'

/**
 * DEV-ONLY wiring, imported from main.ts behind `import.meta.env.DEV` so it never reaches the
 * production bundle (scripts/check-bundle.mjs fails the build if it does).
 * Must run before the router and the auth store start.
 */
export function installDevMocks(): void {
  applyDemoLoginFromUrl()
  setMockHandler(createGroupOrdersMockHandler())
}
