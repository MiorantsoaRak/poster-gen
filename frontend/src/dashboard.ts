import { ref, shallowRef } from 'vue'
import { api } from './api'

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
