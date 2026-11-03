/** Message the API put into an error body: a plain string, `{ error }` or `{ message }`. */
export function getServerErrorMessage(body: unknown): string {
  if (typeof body === 'string') return body
  if (body && typeof body === 'object') {
    const { error, message } = body as { error?: unknown; message?: unknown }
    if (typeof error === 'string') return error
    if (typeof message === 'string') return message
  }
  return ''
}
