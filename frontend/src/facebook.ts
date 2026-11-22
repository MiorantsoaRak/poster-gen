import type { Post } from './publish'

// The « Page Facebook » card of « Mon compte » (D-FB-PUBLISH-004): GET /api/facebook's answer, and the form it gives the
// card. Page names, choices and errors come from the server.
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

const returnKey = 'affiche.facebook-publish-return'
export function isPublishOrigin(value: unknown): value is string {
  return typeof value === 'string' && (value === 'publier' ||
    /^publier-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(value) && value.length === 44)
}

// One departure per tab. The binding is checked after the account is authenticated again.
export function keepFacebookOrigin(shop: number, origin: string): boolean {
  if (!Number.isSafeInteger(shop) || shop <= 0 || !isPublishOrigin(origin)) return false
  try {
    const record = JSON.stringify({ shop, origin })
    sessionStorage.setItem(returnKey, record)
    if (sessionStorage.getItem(returnKey) === record) return true
  } catch { /* Mon compte offers a manual return when this tab cannot keep the route. */ }
  clearFacebookOrigin()
  return false
}

export function clearFacebookOrigin() {
  try { sessionStorage.removeItem(returnKey) } catch { /* Storage is unavailable; the in-memory origin is cleared by the caller. */ }
}

export function takeFacebookOrigin(shop: number): string | null {
  try {
    const raw = sessionStorage.getItem(returnKey)
    if (!raw) return null
    sessionStorage.removeItem(returnKey)
    const record = JSON.parse(raw)
    return Number.isSafeInteger(shop) && shop > 0 && record?.shop === shop && isPublishOrigin(record.origin) ? record.origin : null
  } catch { return null } // Missing access or malformed record: keep the normal account navigation.
}

/** The final panel's read of the posts that hold its poster: the first page, or the one after the last post shown. */
export const postsAddress = (poster: string, after: string | null) =>
  `/api/facebook/posts?creation=${encodeURIComponent(poster)}${after ? `&before=${encodeURIComponent(after)}` : ''}`

/** The final panel's line for a post that holds its poster (D-FB-POST-005): alone or with others, its state in the
 *  server's words, Facebook's own link to the post (not the Page's, which the owner's word gives), and whether the owner
 *  is to answer for it on the page « Publier sur Facebook ». */
export function panelLine(post: Post) {
  const link = post.status === 'published' && !post.said_by_owner && post.link?.startsWith('https://www.facebook.com/') ? post.link : null
  return { alone: post.count === 1 ? 'seule' : `dans une publication de ${post.count} images`, state: post.message_fr, link,
    answer: post.status === 'unknown' }
}
