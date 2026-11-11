import { ApiError } from './api'
import { copy, type PosterDocument } from './document'

type Pending = { document: PosterDocument; revision: number; key: string }
export type SaveState = 'saved' | 'dirty' | 'saving' | 'failed' | 'conflict'

export class DraftSaver {
  state: SaveState = 'saved'
  error = ''
  private pending: PosterDocument | null = null
  private failed: Pending | null = null
  private timer?: ReturnType<typeof setTimeout>
  private flight: Promise<void> | null = null
  constructor(public revision: number, private send: (request: Pending) => Promise<{ revision: number }>, private changed: () => void = () => {}) {}
  get unsaved() { return this.pending !== null || this.failed !== null || this.flight !== null }

  queue(document: PosterDocument) {
    this.pending = copy(document)
    clearTimeout(this.timer)
    if (this.state !== 'failed' && this.state !== 'conflict') {
      this.state = 'dirty'
      this.timer = setTimeout(() => { void this.flush().catch(() => { /* The retained error is displayed by the editor. */ }) }, 750)
    }
    this.changed()
  }

  async flush(): Promise<void> {
    clearTimeout(this.timer)
    if (this.state === 'conflict') throw new Error(this.error)
    if (this.flight) { await this.flight; if (this.pending || this.failed) return this.flush(); return }
    this.flight = this.drain()
    try { await this.flight }
    finally { this.flight = null; this.changed() }
  }

  private async drain() {
    while (this.failed || this.pending) {
      const request = this.failed ?? { document: this.pending!, revision: this.revision, key: crypto.randomUUID() }
      if (!this.failed) this.pending = null
      this.state = 'saving'; this.error = ''; this.changed()
      try {
        const result = await this.send(request)
        this.revision = result.revision; this.failed = null
      } catch (error) {
        this.failed = request
        this.state = error instanceof ApiError && error.code === 'revision_conflict' ? 'conflict' : 'failed'
        this.error = error instanceof Error ? error.message : 'Enregistrement impossible.'
        this.changed(); throw error
      }
    }
    this.state = 'saved'; this.changed()
  }
  dispose() { clearTimeout(this.timer) }
}
