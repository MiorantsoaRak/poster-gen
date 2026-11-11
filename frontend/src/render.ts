import { createApp, h, nextTick, ref } from 'vue'
import PosterCanvas from './PosterCanvas.vue'
import type { Format, PosterDocument } from './document'

export async function render(document: PosterDocument, sources: Record<string, string>, format: Format = 'feed', fonts?: Record<string, string>) {
  const host = window.document.createElement('div'), canvas = ref<InstanceType<typeof PosterCanvas>>()
  window.document.body.append(host)
  let app: ReturnType<typeof createApp>
  try {
    return await new Promise<{ png: string; issues: unknown[] }>((resolve, reject) => {
      app = createApp({ render: () => h(PosterCanvas, { ref: canvas, document, sources, format, fonts, readonly: true, scale: 1,
        onError: message => reject(new Error(message)), onReady: async ready => {
          if (ready) { await nextTick(); resolve({ png: canvas.value!.exportPng(), issues: canvas.value!.issues() }) }
        } }) })
      app.mount(host)
    })
  } finally { app!?.unmount(); host.remove() }
}

declare global { interface Window { renderPoster: (payload: { document: PosterDocument; sources: Record<string, string>; format: Format; fonts: Record<string, string> }) => ReturnType<typeof render> } }
window.renderPoster = payload => render(payload.document, payload.sources, payload.format, payload.fonts)
