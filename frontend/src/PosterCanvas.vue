<script setup lang="ts">
import { computed, nextTick, shallowRef, ref, watch } from 'vue'
import Konva from 'konva'
import { Stage as VStage, Layer as VLayer, Group as VGroup, Rect as VRect, Image as VImage, Text as VText, Transformer as VTransformer } from 'vue-konva'
import { FORMATS, type Format, type Layer, type PosterDocument } from './document'
import { loadFonts } from './fonts'
import { badgeConfig, inspectLayout, textRuns, type LayoutIssue } from './canvas'

const props = withDefaults(defineProps<{ document: PosterDocument; format: Format; sources: Record<string, string>;
  selected?: string | null; scale?: number; readonly?: boolean; dragEnabled?: boolean; fonts?: Record<string, string> }>(),
  { scale: 1, readonly: false, dragEnabled: true, selected: null })
const emit = defineEmits<{ select: [id: string | null]; change: [id: string, patch: Partial<Layer>];
  issues: [issues: LayoutIssue[]]; ready: [ready: boolean]; error: [message: string] }>()
const stage = ref<any>(), transformer = ref<any>()
const images = shallowRef<Record<string, HTMLImageElement>>({}), ready = ref(false)
const cache = new Map<string, Promise<HTMLImageElement>>()
let sequence = 0
const dimensions = computed(() => FORMATS[props.format])
const layout = computed(() => props.document.formats[props.format]!)
const layers = computed(() => [...layout.value.layers].filter(layer => layer.visible).sort((a, b) => a.z - b.z))
const sceneImage = computed(() => images.value[`scene:${layout.value.scene.visual_id}`])

async function imageFor(url: string) {
  if (!cache.has(url)) cache.set(url, (async () => {
    const response = await fetch(url, { credentials: 'same-origin' })
    if (!response.ok) throw new Error('Image introuvable. Restaurez le fichier source.')
    const objectUrl = URL.createObjectURL(await response.blob())
    try {
      const image = new Image(); image.src = objectUrl; await image.decode(); return image
    } finally { URL.revokeObjectURL(objectUrl) }
  })().catch(error => { cache.delete(url); throw error }))
  return cache.get(url)!
}

watch(() => [props.document, props.format, props.sources], async () => {
  const current = ++sequence
  ready.value = false; emit('ready', false)
  try {
    await loadFonts(props.fonts)
    const required = layers.value.filter(layer => layer.kind !== 'text').map(layer => (layer as any).asset as string)
    for (const layer of layers.value) if (layer.kind === 'text' && layer.texture_effect_id) required.push(`effect:${layer.texture_effect_id}`)
    if (layout.value.scene.visual_id) required.push(`scene:${layout.value.scene.visual_id}`)
    const entries = await Promise.all([...new Set(required)].map(async id => {
      const url = props.sources[id]
      if (!url) throw new Error('Une image requise est absente.')
      return [id, await imageFor(url)] as const
    }))
    if (current !== sequence) return
    images.value = Object.fromEntries(entries)
    emit('issues', inspectLayout(props.document, props.format))
    ready.value = true; await nextTick(); attach(); emit('ready', true)
  } catch (error) { if (current === sequence) emit('error', error instanceof Error ? error.message : 'Affichage impossible.') }
}, { deep: true, immediate: true })

function attach() {
  if (props.readonly || !transformer.value || !stage.value) return
  const node = stage.value.getNode().findOne((node: Konva.Node) => node.id() === props.selected)
  transformer.value.getNode().nodes(node ? [node] : [])
}
watch(() => [props.selected, props.scale, props.dragEnabled], () => nextTick(attach))

function select(event: Konva.KonvaEventObject<Event>, id: string) {
  if (!props.readonly) { event.cancelBubble = true; emit('select', id) }
}
function moved(event: Konva.KonvaEventObject<Event>, layer: Layer) {
  const node = event.target
  emit('change', layer.id, { x: node.x(), y: node.y() })
}
function transformed(event: Konva.KonvaEventObject<Event>, layer: Layer) {
  const node = event.target
  const patch = { x: node.x(), y: node.y(), width: Math.max(24, layer.width * node.scaleX()), height: Math.max(24, layer.height * node.scaleY()) }
  node.scaleX(1); node.scaleY(1)
  emit('change', layer.id, patch)
}
function fittedImage(layer: Layer) {
  if (layer.kind === 'text') return {}
  const image = images.value[layer.asset]
  if (!image) return {}
  const scale = Math.min(layer.width / image.naturalWidth, layer.height / image.naturalHeight)
  return { image, x: (layer.width - image.naturalWidth * scale) / 2, y: (layer.height - image.naturalHeight * scale) / 2,
    width: image.naturalWidth * scale, height: image.naturalHeight * scale }
}
function material(layer: Layer, run: Konva.TextConfig) {
  if (layer.kind !== 'text' || !layer.texture_effect_id) return {}
  const image = images.value[`effect:${layer.texture_effect_id}`]
  if (!image) return {}
  // Konva fills the exact font glyphs with CanvasPattern; no scene pixels enter the material layer.
  return { fillPriority: 'pattern', fillPatternImage: image, fillPatternScaleX: layer.width / image.naturalWidth,
    fillPatternScaleY: layer.height / image.naturalHeight, fillPatternRepeat: 'no-repeat',
    fillPatternX: -(run.x ?? 0), fillPatternY: -(run.y ?? 0) }
}
function keydown(event: KeyboardEvent) {
  if (props.readonly || !props.selected) return
  const delta: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }
  const move = delta[event.key], layer = layers.value.find(layer => layer.id === props.selected)
  if (move && layer) { event.preventDefault(); const step = event.shiftKey ? 10 : 1; emit('change', layer.id, { x: layer.x + move[0] * step, y: layer.y + move[1] * step }) }
}
function exportPng() {
  if (!props.readonly || props.scale !== 1 || !ready.value) throw new Error('Le rendu n’est pas prêt.')
  return stage.value.getNode().toDataURL({ pixelRatio: 1, mimeType: 'image/png' }) as string
}
defineExpose({ exportPng, issues: () => inspectLayout(props.document, props.format), isReady: () => ready.value })
</script>

<template>
  <div class="poster-canvas" :tabindex="readonly ? undefined : 0" role="img" aria-label="Aperçu de l’affiche. Utilisez aussi la liste des éléments pour modifier le contenu." @keydown="keydown">
    <VStage ref="stage" :config="{ width: dimensions[0] * scale, height: dimensions[1] * scale, scaleX: scale, scaleY: scale }">
      <VLayer>
        <VRect :config="{ width: dimensions[0], height: dimensions[1], fill: '#17324D' }" @click="emit('select', null)" @tap="emit('select', null)" />
        <VImage v-if="sceneImage && layout.scene.crop" :config="{ image: sceneImage, width: dimensions[0], height: dimensions[1], crop: { x: layout.scene.crop.x, y: layout.scene.crop.y, width: layout.scene.crop.w, height: layout.scene.crop.h }, listening: false }" />
        <template v-if="ready">
          <VGroup v-for="layer in layers" :key="layer.id" :config="{ id: layer.id, x: layer.x, y: layer.y, draggable: !readonly && dragEnabled && selected === layer.id, listening: !readonly }"
            @click="select($event, layer.id)" @tap="select($event, layer.id)" @dragend="moved($event, layer)" @transformend="transformed($event, layer)">
            <VRect :config="{ width: layer.width, height: layer.height, fill: 'rgba(0,0,0,0)' }" />
            <template v-if="layer.kind === 'text'">
              <VRect v-if="layer.price_badge" :config="{ ...badgeConfig(layer), listening: false }" />
              <VText v-for="(run, index) in textRuns(document, layer)" :key="index" :config="{ ...run, ...material(layer, run), listening: false }" />
            </template>
            <VImage v-else :config="{ ...fittedImage(layer), listening: false }" />
          </VGroup>
        </template>
        <VTransformer v-if="!readonly && dragEnabled" ref="transformer" :config="{ rotateEnabled: false, flipEnabled: false, keepRatio: layers.find(l => l.id === selected)?.kind !== 'text', enabledAnchors: ['top-left','top-right','bottom-left','bottom-right'], anchorSize: 14, borderStroke: '#39BBD3', anchorFill: '#FFFFFF', anchorStroke: '#186C80', boundBoxFunc: (old: any, box: any) => box.width < 24 * scale || box.height < 24 * scale ? old : box }" />
      </VLayer>
    </VStage>
  </div>
</template>
