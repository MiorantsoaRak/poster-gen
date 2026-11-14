export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number, public currentRevision?: number, public field?: string) { super(message) }
}

// The server's clock minus this device's, from the last response's Date header (whole seconds); null until one is read.
export let clockSkew: number | null = null

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  try { response = await fetch(path, { ...options, credentials: 'same-origin' }) }
  catch { throw new ApiError('network', 'Connexion interrompue. Vos modifications restent dans cet onglet.', 0) }
  const date = Date.parse(response.headers.get('Date') ?? '')
  if (!Number.isNaN(date)) clockSkew = date - Date.now()
  let data: any
  try { data = await response.json() }
  catch { throw new ApiError('invalid_response', 'Réponse du serveur illisible. Réessayez.', response.status) }
  if (!response.ok) throw new ApiError(data.error?.code ?? 'server_error', data.error?.message_fr ?? 'La demande a échoué.', response.status, data.error?.current_revision, data.error?.field)
  return data as T
}

const uncertain = new Map<string, string>()
export async function mutation<T>(path: string, body: unknown, revision?: number, key?: string, method = 'POST') {
  const signature = JSON.stringify([path, body, revision, method])
  const operation = key ?? uncertain.get(signature) ?? crypto.randomUUID()
  if (!key) uncertain.set(signature, operation)
  const result = await api<T>(path, { method, headers: { 'Content-Type': 'application/json', 'Idempotency-Key': operation,
    ...(revision === undefined ? {} : { 'If-Match': `"${revision}"` }) }, body: JSON.stringify(body) })
  uncertain.delete(signature)
  return result
}

export async function upload(file: File, role: 'original' | 'logo' | 'style') {
  const body = new FormData(); body.set('file', file); body.set('role', role)
  return api<{ asset: string; warnings: string[] }>('/api/assets', { method: 'POST', body })
}
