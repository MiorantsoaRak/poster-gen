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

// Publishing on the Page from the final panel (D-FB-PUBLISH-003, 004): GET /api/creations/{id}/publications's items,
// newest first, and what the panel makes of them. The words of a line are the server's (message_fr).
export interface Publication {
  id: string; status: 'sending' | 'published' | 'failed' | 'unknown'; page_id: string; page_name: string; sent_at: string
  settled_at: string | null; link: string | null; error_code: string | null; said_by_owner: boolean; message_fr: string
}
const onPage = (page: { id: string }, item: Publication) => item.page_id === page.id
/** What « Publier sur ma Page » does: with no Page connected, or one to reconnect, it leads to « Mon compte »; while a
 *  publication of this poster on this Page waits for its outcome (`sending`, `unknown`) nothing is offered; else the sheet. */
export function publishAction(page: FacebookAnswer['page'], items: Publication[]): 'account' | 'wait' | 'sheet' {
  if (!page || page.state !== 'connected') return 'account'
  return items.some(item => onPage(page, item) && (item.status === 'sending' || item.status === 'unknown')) ? 'wait' : 'sheet'
}
/** `seen`: the last publication of this poster on this Page that the sheet shows, or null when there is none. */
export const seenOf = (page: { id: string }, items: Publication[]) => items.find(item => onPage(page, item))?.id ?? null
/** The sheet's « already published »: the last publication of this poster on this Page that is on it, the owner's word
 *  included. */
export const publishedOn = (page: { id: string }, items: Publication[]) =>
  items.find(item => onPage(page, item) && item.status === 'published') ?? null
/** A publication's line under the buttons: its state, the link it carries, and whether the owner is asked to say. A link
 *  that is not Facebook's own is not shown. */
export function lineOf(item: Publication): { state: string; link: { href: string; label: string } | null; ask: boolean } {
  if (item.status === 'unknown') return { state: item.message_fr, link: { href: `https://www.facebook.com/${item.page_id}`, label: 'Ouvrir ma Page' }, ask: true }
  const link = item.status === 'published' && item.link?.startsWith('https://www.facebook.com/')
    ? { href: item.link, label: item.said_by_owner ? 'Ouvrir la Page' : 'Voir la publication' } : null
  return { state: item.message_fr, link, ask: false }
}
