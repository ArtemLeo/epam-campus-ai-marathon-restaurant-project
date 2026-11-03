// Use Vite's local proxy by default, so the browser never needs a Docker-internal API hostname.
export const BACKEND_URL: string = import.meta.env.VITE_BACKEND_URL || '/api'
