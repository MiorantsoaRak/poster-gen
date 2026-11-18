import { ref, shallowRef } from 'vue'
import { api, ApiError } from './api'

export interface LibraryItem { id: string; revision: number; state: 'draft' | 'to_review' | 'approved' | 'confirmed'; title: string; variant: string; price_ar: number; created_at: string; thumbnail_url: string | null }
export interface Listing { items: LibraryItem[]; total: number; next_cursor: string | null }
export const stateNames = { draft: 'Brouillon', to_review: 'À vérifier', approved: 'Approuvée', confirmed: 'Confirmée' }
interface Attention { total: number; first_creation_id: string | null }
export interface Summary {
  as_of: string; review: Attention; failed: Attention
  usage: { posters_created: number; images_generated: number; credits_spent: number }
}

export function sectionRead<T>(path: string) {
  const data = shallowRef<T | null>(null), loading = ref(false), error = ref(''), checked = ref('')
  let turn = 0
  async function read() {
    const current = ++turn
    error.value = ''; loading.value = true
    try {
      const result = await api<T>(path, { quiet: true, timeout: 20_000 })
      if (current === turn) {
        data.value = result
        checked.value = new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
      }
    } catch (reason) {
      if (current === turn) error.value = reason instanceof Error ? reason.message : 'Lecture impossible.'
    } finally { if (current === turn) loading.value = false }
  }
  function clear() { turn++; data.value = null; error.value = ''; loading.value = false; checked.value = '' }
  return { data, error, loading, checked, read, clear }
}

interface HistoryBase { at: string; kind: string; creation_id: string | null; title: string | null; removed: boolean | null }
export type HistoryEntry = HistoryBase & (
  { type: 'line'; id: number; origin: 'offered' | 'bought' | null; credits: number } |
  { type: 'job'; id: string; credit: 'pending' | 'spent' | 'given_back' }
)
interface HistoryPage { items: HistoryEntry[]; next_cursor: string | null }

export function historyEntry(row: HistoryEntry) {
  if (row.type === 'line') {
    const label = row.kind === 'grant' ? (row.origin === 'bought' ? 'Achat de crédits' : 'Crédits offerts')
      : row.creation_id && row.credits > 0 ? 'Remboursement' : 'Correction'
    return { label, amount: row.credits > 0 ? `+${row.credits}` : String(row.credits) }
  }
  if (row.credit === 'pending') return { label: 'Crédit réservé', amount: '1 en attente' }
  if (row.credit === 'given_back') return { label: 'Réservation libérée', amount: '1 rendu' }
  return { label: 'Crédit dépensé', amount: '−1' }
}

export function creditHistory() {
  const page = shallowRef<HistoryPage | null>(null), error = ref(''), loading = ref(false)
  const retryMore = ref(false), checked = ref('')
  let turn = 0
  async function read(more = false) {
    const before = more && page.value?.next_cursor
    if (more && (!before || loading.value)) return
    const current = ++turn
    error.value = ''; loading.value = true; retryMore.value = more
    try {
      const result = await api<HistoryPage>('/api/shop-credit-history?limit=20' + (before ? '&before=' + encodeURIComponent(before) : ''), { quiet: true, timeout: 20_000 })
      if (current !== turn) return
      const previous = before && page.value ? page.value.items : []
      const keys = new Set(previous.map(row => row.type + ':' + row.id))
      page.value = { items: previous.concat(result.items.filter(row => !keys.has(row.type + ':' + row.id))), next_cursor: result.next_cursor }
      if (!more) checked.value = new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
    } catch (reason) {
      if (current !== turn) return
      error.value = reason instanceof Error ? reason.message : 'Lecture impossible.'
      if (reason instanceof ApiError && reason.code === 'invalid_cursor') retryMore.value = false
    } finally { if (current === turn) loading.value = false }
  }
  function clear() { turn++; page.value = null; error.value = ''; loading.value = false; checked.value = '' }
  return { page, error, loading, retryMore, checked, read, clear }
}
