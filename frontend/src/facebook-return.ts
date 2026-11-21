// The return address of Facebook's dialog, /facebook.html (D-FB-PUBLISH-002). The page's own first lines have already
// taken what Facebook sent out of the address (facebook.html); it goes to the API with the application's own request
// helper (Origin, bundle and shop checked as for any change), and the page gives way to « Mon compte », whose card reads
// the outcome from the API. Nothing is kept in the browser.
import { api, ApiError, ask, failed, open, state } from './api'

declare global { interface Window { facebookReturn?: Record<'code' | 'state' | 'error', string | null>; facebookLost(): void } }
const { code, state: sent, error } = window.facebookReturn ?? { code: null, state: null, error: null }
delete window.facebookReturn
let lost = false
try {
  // The shop's requests leave only once the gate is open: the session's answer opens it on this tab's shop, as at the
  // application's start (App.vue openShop). Signed out, or another shop: nothing is sent, and « Mon compte » says why.
  await ask()
  // The session could not be read (the network, the server): ask() keeps that to itself, and nothing can be sent.
  if (failed.value && sent && (code || error)) lost = true
  else if (state.value === 'shown' && sent && (code || error)) {
    open()
    // The server makes three calls of 20 s at most before it answers.
    await api('/api/facebook/code', { method: 'POST', timeout: 90_000, headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(code ? { code, state: sent } : { state: sent, error }) })
  }
} catch (reason) {
  // The server's own refusal of this connection is kept there for the card (last_error). Anything else (the session's
  // read failed, the request never arrived, an error before the route) left no sentence anywhere: it is said here.
  lost = !(reason instanceof ApiError && reason.code.startsWith('facebook_'))
}
if (lost) window.facebookLost()
else location.replace('/#compte')
