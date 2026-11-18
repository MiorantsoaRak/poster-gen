// Waiting for a scene or an adjustment of the scene (R-POSTER-EDITOR-008, D-POSTER-EDITOR-006). What the owner is told
// comes from the job's real state, never from a timer alone; App.vue holds the timers.
export type Phase = 'queued' | 'running' | 'receiving' | 'ready' | 'failed'

// A succeeded job is « receiving » until its image is decoded on this device.
export function phase(job: { status: string }, loaded: boolean): Phase {
  if (job.status === 'queued' || job.status === 'running') return job.status
  return job.status === 'succeeded' ? (loaded ? 'ready' : 'receiving') : 'failed'
}

export function elapsedLabel(ms: number) {
  const seconds = Math.max(0, Math.floor(ms / 1000))
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

// After this long in creation a sentence says it is longer than usual, still running, and useless to start again
// (R-POSTER-EDITOR-008: 100 s, whatever the model's usual time).
export const OVERDUE_MS = 100_000
export const overdue = (current: Phase, runningMs: number) => current === 'running' && runningMs > OVERDUE_MS

// A server time on this device's clock. skew is the server's clock minus this one (a response's Date header), null
// when unknown: then, as for a missing or unreadable stamp, the moment of first sight. Never in the future. The API writes
// UTC with its offset (+00:00); a stamp without a zone is read as UTC too, never as the device's local time.
export function localTime(stamp: string | null | undefined, skew: number | null, now: number) {
  const server = stamp ? Date.parse(/(Z|[+-]\d\d:?\d\d)$/i.test(stamp) ? stamp : `${stamp}Z`) : NaN
  return skew === null || Number.isNaN(server) ? now : Math.min(now, server - skew)
}

// After a failed poll the next one waits 2 s, 4 s, 8 s, then 10 s each time.
export const retryDelay = (failures: number) => [2000, 4000, 8000][failures - 1] ?? 10000

// Why a generation failed, in the owner's words: what he can do differs with the cause.
function jobFailure(code: string | null) {
  const kept = ' Vos images et votre affiche sont conservées.'
  if (code === 'refused') return 'Le service d’images a refusé cette demande (photo ou texte non accepté). Essayez une autre photo, ou changez le titre ou l’ambiance.' + kept
  if (['timeout', 'provider_error', 'rate_limited', 'invalid_response'].includes(code ?? '')) return 'Le service d’images n’a pas répondu correctement. Réessayez dans une minute.' + kept
  if (['quota', 'auth', 'budget_exhausted'].includes(code ?? '')) return 'Le compte du service d’images doit être vérifié par l’administrateur (quota, clé ou budget). Vous pouvez encore modifier et télécharger vos affiches.'
  return `La tâche n’a pas abouti${code ? ` (code : ${code})` : ''}.${kept} Vous pouvez réessayer.`
}
/** What the owner is told when a followed job ends failed, interrupted or cancelled: its cause, then, when the job took a
 *  credit, that it is back (D-BALANCE-006). */
export function ended(job: { status: string; kind: string; error_code: string | null; credit?: string | null }) {
  const said = job.status === 'interrupted' ? 'La génération a été interrompue. Aucun nouvel appel automatique n’a été lancé.'
    : job.kind === 'look' ? 'Le style n’a pas pu être décrit à partir de cette affiche. Essayez une autre image ; rien n’est perdu.'
    : jobFailure(job.error_code)
  return job.credit === 'given_back' ? `${said} Votre crédit vous a été rendu.` : said
}

/** Under « Reprendre » and « Réessayer », and in the editor's dialog for a request that lost its answer: the server answers
 *  what it stored, so the credit is taken once (D-BALANCE-006). */
export const ONCE = '1 crédit, une seule fois pour cette demande'

/** Before every paid scene adjustment, on the chat's card and in « Ajuster la scène » (D-TERMS-005, owner decision 2).
 *  Always the page's: the server decides nothing about it, so a card read before it shows it too. */
export const FEATURES_WARNING = 'Vous demandez des caractéristiques sans les lister ? L’IA choisira les caractéristiques : vérifiez-les avant de publier.'

// The shop's credits as GET /api/balance gives them (D-BALANCE-004). The browser holds null while they are unread or
// their read failed: unknown, never 0.
export type Charged = 'scene' | 'text_texture'
export interface Balance { available: number; pending: number; purchase_fr: string; blocked: Record<Charged, { reason: string; message_fr: string } | null> }
/** What a button that makes a new image says, and whether it may send (D-BALANCE-006), in the server's order: what blocks
 *  this operation, then no credit, then few left. `stop`: nothing is sent, the dialog only closes. Unknown: the server decides.
 *  `terms`: what stops it is the conditions of use, not accepted: the control offers to read them (D-TERMS-004). */
export function credit(balance: Balance | null, kind: Charged): { stop: boolean; text: string; terms?: boolean } {
  if (!balance) return { stop: false, text: '1 crédit · solde indisponible pour le moment' }
  const blocked = balance.blocked[kind]
  if (blocked) return { stop: true, text: blocked.message_fr, ...(blocked.reason === 'terms' ? { terms: true } : {}) }
  if (balance.available <= 0) return { stop: true, text: `Il ne vous reste plus de crédit : rien ne sera envoyé. Vos affiches restent disponibles. ${balance.purchase_fr}` }
  const left = `1 crédit · il vous en reste ${balance.available}${balance.pending > 0 ? `, ${balance.pending} en attente` : ''}`
  return { stop: false, text: balance.available <= 3 ? `${left}. Bientôt à court : ${balance.purchase_fr}` : left }
}

const MONTHS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
/** The conditions' version, an ISO date (D-TERMS-001), as the dialog says it: « 17 novembre 2026 », « 1er mai 2027 ».
 *  Written by hand: Intl says « 1 mai ». A version of another shape is shown as it is. */
export function termsDate(version: string) {
  const [, year, month, day] = /^(\d{4})-(\d{2})-(\d{2})$/.exec(version) ?? []
  const name = MONTHS[Number(month) - 1]
  return name ? `${Number(day) === 1 ? '1er' : Number(day)} ${name} ${year}` : version
}
