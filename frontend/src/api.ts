import { ref } from 'vue'

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number, public currentRevision?: number, public field?: string) { super(message) }
}

// The server's clock minus this device's, from the last response's Date header (whole seconds); null until one is read.
export let clockSkew: number | null = null

// The top progress line (D-POSTER-EDITOR-007 point 3): on once requests the owner waits for have been in flight for
// 300 ms, off when none has been for a frame (sequential requests of one action leave gaps of a few microtasks).
// Background requests (job polls, autosave) pass quiet and never show it.
export const progress = ref(false)
let inFlight = 0, showing: ReturnType<typeof setTimeout> | undefined, hiding: ReturnType<typeof setTimeout> | undefined
function begin() {
  inFlight++; clearTimeout(hiding); hiding = undefined
  if (!showing && !progress.value) showing = setTimeout(() => { showing = undefined; if (inFlight) progress.value = true }, 300)
}
function end() {
  if (--inFlight) return
  hiding = setTimeout(() => { hiding = undefined; clearTimeout(showing); showing = undefined; progress.value = false }, 16)
}

// Sent with every request (X-Affiche-Bundle); the server refuses a state-changing request from a lower one with
// `bundle_outdated` (backend api.py BUNDLE). Raise both together when a change makes an older open tab unsafe: one that
// would pay beside a card it does not know, or carry out a card without what it promises (ADR-103).
export const BUNDLE = 2

// timeout (ms) is opt-in: the request is given up after it, headers and body together. Without it nothing changes.
export async function api<T>(path: string, { quiet = false, timeout, ...options }: RequestInit & { quiet?: boolean; timeout?: number } = {}): Promise<T> {
  if (!quiet) begin()
  const limit = timeout ? new AbortController() : undefined, timer = limit && setTimeout(() => limit.abort(), timeout)
  const late = () => new ApiError('timeout', 'Le serveur met trop de temps à répondre. Réessayez.', 0)
  try {
    let response: Response
    try { response = await fetch(path, { ...options, headers: { ...options.headers as Record<string, string> | undefined, 'X-Affiche-Bundle': String(BUNDLE) }, credentials: 'same-origin', ...(limit ? { signal: limit.signal } : {}) }) }
    catch { throw limit?.signal.aborted ? late() : new ApiError('network', 'Connexion interrompue. Vos modifications restent dans cet onglet.', 0) }
    const date = Date.parse(response.headers.get('Date') ?? '')
    if (!Number.isNaN(date)) clockSkew = date - Date.now()
    let data: any
    try { data = await response.json() }
    catch { throw limit?.signal.aborted ? late() : new ApiError('invalid_response', 'Réponse du serveur illisible. Réessayez.', response.status) }
    if (!response.ok) throw new ApiError(data.error?.code ?? 'server_error', data.error?.message_fr ?? 'La demande a échoué.', response.status, data.error?.current_revision, data.error?.field)
    return data as T
  } finally { clearTimeout(timer); if (!quiet) end() }
}

// Reading a chat message is a paid call (D-TEXT-FIRST-002), bounded at 30 s here. The caller owns the record (key and
// exact body, chat.ts `Pending`) and sends it again unchanged after a lost answer: the server then answers what it stored.
export const READ_TIMEOUT_MS = 30_000
export const read = <T>(pending: { key: string; body: string }) => api<T>('/api/reads', { method: 'POST', timeout: READ_TIMEOUT_MS,
  headers: { 'Content-Type': 'application/json', 'Idempotency-Key': pending.key }, body: pending.body })

const uncertain = new Map<string, string>()
export async function mutation<T>(path: string, body: unknown, revision?: number, key?: string, method = 'POST', quiet = false) {
  const signature = JSON.stringify([path, body, revision, method])
  const operation = key ?? uncertain.get(signature) ?? crypto.randomUUID()
  if (!key) uncertain.set(signature, operation)
  const result = await api<T>(path, { method, quiet, headers: { 'Content-Type': 'application/json', 'Idempotency-Key': operation,
    ...(revision === undefined ? {} : { 'If-Match': `"${revision}"` }) }, body: JSON.stringify(body) })
  uncertain.delete(signature)
  return result
}

// Addresses of images made by the server, with its encoder's version: the browser keeps them a year (ADR-087). Keep in
// step with backend/src/affiche/api.py (THUMBNAIL_VERSION, DISPLAY_VERSION) and rendering.CANVAS_IMAGE_VERSION; an
// address at another version still works, it is only not kept.
const IMAGE_VERSIONS = { prepared: '1', display: '1', thumbnail: '1' }
export const preparedUrl = (url: string) => `${url}?prepared=true&v=${IMAGE_VERSIONS.prepared}`
export const displayUrl = (url: string) => `${url}?prepared=true&display=true&v=${IMAGE_VERSIONS.display}`
export const thumbnailUrl = (url: string) => `${url.replace('/api/assets/', '/api/thumbnails/')}?v=${IMAGE_VERSIONS.thumbnail}`

export async function upload(file: File, role: 'original' | 'logo' | 'style') {
  const body = new FormData(); body.set('file', file); body.set('role', role)
  return api<{ asset: string; width: number; height: number; warnings: string[] }>('/api/assets', { method: 'POST', body })
}
