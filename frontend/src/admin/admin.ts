// The operator's page: what it reads from the address and what it says of a refusal (D-ADMIN-005). English, for the
// operator (owner decision 10).
import type { AdminError } from './adminApi'

export type Route = { view: 'shops' } | { view: 'shop'; id: number }
/** The view of an address's hash: `#/shops/<id>` is one shop, anything else the shop list (the home). */
export function route(hash: string): Route {
  const found = /^#\/shops\/([1-9][0-9]{0,8})$/.exec(hash)
  return found ? { view: 'shop', id: Number(found[1]) } : { view: 'shops' }
}

export const NOT_SET = 'No operator password is set. On the server run: python -m affiche.shops operator-password (deploy/README.md, « Operator dashboard »).'
const SENTENCES: Record<string, string> = {
  wrong_credentials: 'Wrong password.',
  rate_limited: 'Too many wrong passwords from this address. Wait 15 minutes, then try again.',
  operator_not_set: NOT_SET,
  unauthenticated: 'Your session has ended. Sign in again.',
  bundle_outdated: 'This page is out of date: nothing was saved. Reload it, then try again.',
  forbidden_origin: 'The server refused a request from this page’s address.',
  not_found: 'This shop does not exist.',
  network: 'No answer from the server: the connection was lost.',
  timeout: 'No answer from the server within 30 seconds.',
  invalid_response: 'The server’s answer could not be read.',
  storage_unavailable: 'The server’s storage is busy or unavailable.',
}
/** What a refusal says: the page's own sentence for the codes it knows, else the server's `detail` (the operator's
 *  refusals, in English), else its French sentence, else the code. Server text is shown as text, never as HTML. */
export function sentence(error: AdminError): string {
  if (error.code === 'validation_error')
    return error.field?.endsWith('name') ? 'The name was not accepted: 1 to 160 characters.' : `This value was not accepted: ${error.field ?? 'unknown field'}.`
  return SENTENCES[error.code] ?? (error.status >= 500 ? `The server failed (error ${error.status}).` : error.message || `Refused (${error.code}).`)
}
/** No definite answer: the server may have done it (a 5xx proves no rollback, D-ADMIN-005). */
export const uncertain = (error: AdminError) => error.status === 0 || error.status >= 500 || error.code === 'invalid_response'

export const count = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`
/** Micro-USD as the operator reads dollars. */
export const dollars = (micros: number) => `$${(micros / 1e6).toFixed(2)}`
