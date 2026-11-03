import { vi, type Mock } from 'vitest'

export interface FakeResponse {
  status?: number
  body?: unknown
}

/**
 * Replaces global fetch, answering calls in order — the Vitest stand-in for Angular's
 * HttpTestingController (`expectOne(url)` → `flush(body)`).
 */
export function mockFetch(...responses: FakeResponse[]): Mock<typeof fetch> {
  const fetchMock = vi.fn<typeof fetch>()
  for (const { status = 200, body = null } of responses) {
    fetchMock.mockResolvedValueOnce(
      new Response(body === null ? '' : JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
  }
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** URL, method, headers and parsed body of the n-th fetch call. */
export function fetchCall(fetchMock: Mock<typeof fetch>, index = 0) {
  const [url, init = {}] = fetchMock.mock.calls[index] ?? []
  return {
    url: String(url),
    method: init.method ?? 'GET',
    headers: (init.headers ?? {}) as Record<string, string>,
    body: typeof init.body === 'string' ? (JSON.parse(init.body) as unknown) : undefined,
  }
}
