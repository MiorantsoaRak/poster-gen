// The operator's requests (D-ADMIN-005). Nothing of the shops' client is imported (a test holds it): the session is the
// HttpOnly cookie the server sets on /api/admin, so this page never holds a token, and the browser sends Origin itself.

// Sent with every request (X-Affiche-Bundle); the server refuses a state-changing request from a lower one with
// `bundle_outdated` (backend api.py BUNDLE). The same number as the shops' api.ts: a test fails when they differ.
export const BUNDLE = 3
export const TIMEOUT_MS = 30_000

export class AdminError extends Error {
  // message: the server's `detail` (the operator's refusals, in English), else its `message_fr`, else empty.
  constructor(public code: string, message: string, public status: number, public field?: string, public existing?: unknown) { super(message) }
}

// The authentication state a request belongs to. A sign-in, a sign-out and a session lost each start a new one; an
// answer to a request sent before it is dropped: its caller's promise never settles, so no code of the earlier state
// runs on to show a password, a shop's data or a message in the new one (whoever started the new state reset the rest).
let epoch = 0
export function newEpoch() { epoch++ }
const never = () => new Promise<never>(() => {})

export function call<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const sent = epoch
  return send<T>(path, method, body).then(data => sent === epoch ? data : never(), error => sent === epoch ? Promise.reject(error) : never())
}

async function send<T>(path: string, method: string, body?: unknown): Promise<T> {
  const signal = AbortSignal.timeout(TIMEOUT_MS)
  const lost = (reason: unknown) => new AdminError((reason as Error)?.name === 'TimeoutError' ? 'timeout' : 'network', '', 0)
  let response: Response
  try {
    response = await fetch(path, { method, credentials: 'same-origin', signal, body: body === undefined ? undefined : JSON.stringify(body),
      headers: { 'X-Affiche-Bundle': String(BUNDLE), ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) } })
  } catch (reason) { throw lost(reason) }
  let data: any
  try { data = await response.json() }
  catch (reason) { throw signal.aborted ? lost(reason) : new AdminError('invalid_response', '', response.status) }
  if (!response.ok) {
    const error = data?.error ?? {}
    throw new AdminError(error.code ?? 'server_error', error.detail ?? error.message_fr ?? '', response.status, error.field, error.existing)
  }
  return data as T
}
