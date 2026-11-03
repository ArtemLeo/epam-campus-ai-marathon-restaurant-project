/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Optional override of the dev-server API URL (see src/config/env.development.ts). */
  readonly VITE_BACKEND_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
