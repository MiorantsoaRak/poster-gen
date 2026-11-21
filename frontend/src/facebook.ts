// The « Page Facebook » card of « Mon compte » (D-FB-PUBLISH-004): GET /api/facebook's answer, and the form it gives the
// card. Nothing of this feature is kept in the browser.
export interface FacebookAnswer {
  page: { id: string; name: string; state: 'connected' | 'reconnect' } | null
  choice: { id: string; name: string }[] | null
  last_error?: { code: string; message_fr: string } | null  // a refusal answered to the return page, said once
}
/** A choice waiting comes first: the owner is back from Facebook's dialog, even with a Page connected before. */
export function facebookCard(answer: FacebookAnswer): 'choose' | 'connected' | 'reconnect' | 'connect' {
  if (answer.choice?.length) return 'choose'
  return answer.page ? answer.page.state === 'reconnect' ? 'reconnect' : 'connected' : 'connect'
}
