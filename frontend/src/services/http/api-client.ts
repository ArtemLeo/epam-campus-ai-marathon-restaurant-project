import { t } from '@/i18n'
import { translateApiMessage } from '@/i18n/errors'
import { BACKEND_URL } from '@/config/env'
import { readIdToken } from '@/auth/auth-storage'
import { useToast } from '@/composables/useToast'
import { getServerErrorMessage } from '@/shared/helpers/http-error-helpers'

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

export interface ApiRequestOptions {
  method?: HttpMethod
  body?: unknown
  headers?: Record<string, string>
  /**
   * Equivalent of Angular's `SKIP_ERROR_TOAST` HttpContext: the caller reports
   * the failure itself (background sync, inline form errors).
   */
  skipErrorToast?: boolean
  /** Guest pre-order flow: authorise with the guest session token instead of the user's idToken. */
  guestToken?: string
}

/** What a mock backend sees. `path` has no base URL and no query string. */
export interface ApiRequest {
  method: HttpMethod
  url: string
  path: string
  headers: Record<string, string>
  body: unknown
}

export interface ApiResponse {
  status: number
  body: unknown
}

/** Dev-only hook: answer the requests it owns, return undefined to let the rest reach the API. */
export type MockHandler = (request: ApiRequest) => Promise<ApiResponse> | undefined

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown
  readonly url: string

  constructor(status: number, message: string, body: unknown, url: string) {
    super(translateApiMessage(message, status))
    this.name = 'ApiError'
    this.status = status
    this.body = body
    this.url = url
  }
}

export function isApiError(error: unknown, status?: number): error is ApiError {
  return error instanceof ApiError && (status === undefined || error.status === status)
}

let baseUrl = BACKEND_URL.replace(/\/$/, '')
let mockHandler: MockHandler | undefined
let unauthorizedHandler: (() => void) | undefined
export function setUnauthorizedHandler(handler: (() => void) | undefined): void { unauthorizedHandler = handler }

/** Mirrors the Angular `API_BASE_URL` token; tests point it at a fake host. */
export function setApiBaseUrl(url: string): void {
  baseUrl = url.replace(/\/$/, '')
}

export function getApiBaseUrl(): string {
  return baseUrl
}

export function setMockHandler(handler: MockHandler | undefined): void {
  mockHandler = handler
}

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

async function send(request: ApiRequest): Promise<ApiResponse> {
  const response = await fetch(request.url, {
    method: request.method,
    headers: request.headers,
    body: request.body === undefined ? undefined : JSON.stringify(request.body),
  })
  return { status: response.status, body: await readBody(response) }
}

/** One toast per failed request, worded like the Angular `tokenInterceptor`. */
function reportError(error: ApiError, isGuestFlow: boolean): void {
  const toast = useToast()
  const message = error.message
  switch (error.status) {
    case 400:
      toast.error(message || t('errors.invalid'), t('errors.error'))
      break
    case 401:
      if (isGuestFlow) toast.error(t('errors.guestSession'), t('errors.unauthorized'))
      else toast.error(t('errors.login'), t('errors.unauthorized'))
      break
    case 403:
      toast.error(message || t('errors.denied'), t('errors.forbidden'))
      break
    case 404:
      toast.error(message || t('errors.missing'), t('errors.notFound'))
      break
    case 409:
      toast.error(message || t('errors.changed'), t('errors.conflict'))
      break
    case 422:
      toast.error(message || t('errors.invalid'), t('errors.error'))
      break
    case 500:
      toast.error(t('errors.server'), t('errors.serverTitle'))
      break
    default:
      toast.error(message, t('errors.error'))
  }
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const method = options.method ?? 'GET'
  const url = `${baseUrl}${path}`
  const headers: Record<string, string> = { ...options.headers }
  if (options.body !== undefined && !headers['Content-Type']) headers['Content-Type'] = 'application/json'

  const token = options.guestToken ?? readIdToken()
  if (token && !headers.Authorization) headers.Authorization = `Bearer ${token}`

  const request: ApiRequest = { method, url, path: path.split('?')[0], headers, body: options.body }

  let response: ApiResponse
  try {
    response = (await mockHandler?.(request)) ?? (await send(request))
  } catch {
    response = { status: 0, body: null } // network failure, like Angular's HttpErrorResponse status 0
  }

  if (response.status >= 200 && response.status < 300) return response.body as T

  if (response.status === 401 && token && options.guestToken === undefined && !['/signin', '/register', '/forgot-password', '/reset-password'].includes(path)) unauthorizedHandler?.()
  const error = new ApiError(
    response.status,
    getServerErrorMessage(response.body) || 'An unexpected error occurred.',
    response.body,
    url,
  )
  // A missing pre-order is a normal state for the cart, not an error (same exception as the original).
  const isMissingOrder = request.path.includes('orders') && error.status === 404
  if (!options.skipErrorToast && !isMissingOrder) reportError(error, options.guestToken !== undefined)
  throw error
}

export interface DownloadedFile {
  blob: Blob
  fileName: string
}

/** GET a file (report export). Binary bodies arrive as-is because API Gateway decodes base64 responses. */
export async function apiDownload(path: string, fallbackName: string): Promise<DownloadedFile> {
  const url = `${baseUrl}${path}`
  const token = readIdToken()
  let response: Response
  try {
    response = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  } catch {
    const error = new ApiError(0, 'Network error.', null, url)
    reportError(error, false)
    throw error
  }
  if (!response.ok) {
    if (response.status === 401 && token) unauthorizedHandler?.()
    const body = await readBody(response)
    const error = new ApiError(response.status, getServerErrorMessage(body) || 'Download failed.', body, url)
    reportError(error, false)
    throw error
  }
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const fileName = /filename="?([^";]+)"?/.exec(disposition)?.[1] ?? fallbackName
  const type = response.headers.get('Content-Type') ?? 'application/octet-stream'
  return { blob: new Blob([decodeIfBase64(new Uint8Array(await response.arrayBuffer()), type)], { type }), fileName }
}

const BINARY_SIGNATURES = [
  [0x25, 0x50, 0x44, 0x46], // %PDF
  [0x50, 0x4b, 0x03, 0x04], // PK (xlsx is a zip)
]

/**
 * Without API Gateway binary media types the Lambda's base64 body reaches the browser as text;
 * with them it arrives decoded. Accept both so downloads work either way.
 */
function decodeIfBase64(bytes: Uint8Array<ArrayBuffer>, contentType: string): Uint8Array<ArrayBuffer> {
  if (contentType.startsWith('text/') || BINARY_SIGNATURES.some((sig) => sig.every((b, i) => bytes[i] === b))) {
    return bytes
  }
  try {
    const binary = atob(new TextDecoder().decode(bytes).trim())
    return Uint8Array.from(binary, (char) => char.charCodeAt(0))
  } catch {
    return bytes
  }
}

/** Let the browser save a downloaded file. */
export function saveFile({ blob, fileName }: DownloadedFile): void {
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = fileName
  link.click()
  URL.revokeObjectURL(link.href)
}
