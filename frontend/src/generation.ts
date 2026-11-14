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
