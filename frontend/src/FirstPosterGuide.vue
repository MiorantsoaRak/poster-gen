<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

const props = defineProps<{ step: number }>()
const emit = defineEmits<{ step: [index: number]; close: []; finish: [] }>()
const titles = ['Présenter le produit', 'Préparer l’affiche', 'Vérifier l’affiche', 'Télécharger ou publier']
const panel = ref<HTMLDialogElement>(), heading = ref<HTMLElement>()

function focusStep() {
  heading.value?.focus({ preventScroll: true })
  heading.value?.scrollIntoView({ block: 'nearest', behavior: 'instant' })
}
onMounted(() => { panel.value!.showModal(); focusStep() })
watch(() => props.step, focusStep, { flush: 'post' })
</script>

<template>
  <dialog ref="panel" class="poster-guide" aria-labelledby="guide-name" @cancel.prevent="emit('close')">
    <header class="guide-head">
      <p id="guide-name">Ma première affiche</p>
      <button type="button" class="ghost" @click="emit('close')">Fermer</button>
    </header>
    <div :key="step" class="guide-body">
      <h2 ref="heading" tabindex="-1"><span>Étape {{ step + 1 }} sur {{ titles.length }}.&nbsp;</span>{{ titles[step] }}</h2>
      <div class="guide-copy">
        <template v-if="step === 0">
          <p>Dans « Message », ajoutez une photo nette du produit à vendre. Écrivez son nom, sa variante et son prix exact en ariary, puis touchez « Envoyer ».</p>
          <p>Vous préférez un formulaire ? Dans « Pas à pas », renseignez les caractéristiques que vous avez vérifiées, puis choisissez « Préparer mon affiche ».</p>
        </template>
        <template v-else-if="step === 1">
          <p>Relisez le produit, le prix et le style. Une nouvelle affiche commence au format <strong>Publication</strong>, qui convient à Facebook et au téléchargement. Dans « Pas à pas », vous pouvez choisir Carré ou Story avant de générer.</p>
          <p>La lecture d’un message coûte <strong>0 crédit</strong>, dans la limite quotidienne. Une nouvelle image coûte <strong>1 crédit</strong>. Vérifiez le solde indiqué avant de toucher « Créer l’affiche » dans « Message » ou « Générer l’affiche » dans « Pas à pas ».</p>
        </template>
        <template v-else-if="step === 2">
          <p>Comparez l’affiche terminée à la photo du produit. Vérifiez la forme, la couleur et les accessoires, puis relisez le prix en ariary et vos coordonnées. Ouvrez le PNG en grand pour lire les petits caractères.</p>
          <p>Une erreur ? Choisissez « Corriger l’affiche ». Quand tout est juste, choisissez « Confirmer pour plus tard » pour retrouver le fichier dans « Mes affiches », ou confirmez-le directement en le téléchargeant ou en préparant sa publication.</p>
        </template>
        <template v-else>
          <p><strong>Garder l’image.</strong> Choisissez « Confirmer et télécharger le PNG ». Pour un fichier déjà confirmé, choisissez « Télécharger le PNG ». Sur un téléphone compatible, « Partager dans une autre application » vous permet aussi de préparer la légende et de partager l’image.</p>
          <p><strong>Publier sur Facebook.</strong> Pour une affiche au format Publication, choisissez « Confirmer et préparer la publication ». Si le PNG est déjà validé, choisissez « Publier sur ma Page ». Pour plusieurs images, ouvrez « Publier ». Ajoutez une description si vous le souhaitez, puis choisissez les affiches confirmées dans l’ordre voulu.</p>
          <p>Vérifiez la description, touchez « Publier… », relisez le nom de la Page et l’ordre des images, puis confirmez avec « Publier ».</p>
        </template>
      </div>
      <details>
        <summary>Si vous êtes bloqué</summary>
        <template v-if="step === 0">
          <p>Marquez la photo de l’article comme « Produit » et une référence de style comme « Inspiration ». Pour remplacer la photo sur une affiche existante, « Copier avec cette photo » conserve l’original.</p>
        </template>
        <template v-else-if="step === 1">
          <p>Dans « Pas à pas », ouvrez « Textes » ou « Boutique » pour corriger l’offre. Un prix dessiné dans l’image demande une nouvelle génération pour le modifier. Si les conditions sont en attente, ouvrez « Lire les conditions » dans l’atelier.</p>
        </template>
        <template v-else-if="step === 2">
          <p>Si le produit lui-même est incorrect, signalez le problème et indiquez ce qui doit changer. Si vous modifiez le prix ou la composition, ouvrez le nouvel aperçu pour vérifier le résultat. Le PNG déjà téléchargé conserve son contenu.</p>
        </template>
        <template v-else>
          <p>Affiche absente de « Publier » ? Ouvrez son aperçu actuel au format Publication, puis choisissez « Confirmer et préparer la publication ». Si la connexion a expiré, ouvrez « Mon compte », puis « Page Facebook » pour reconnecter votre Page.</p>
          <p>Si le résultat de l’envoi est inconnu, regardez d’abord votre Page. Indiquez ce que vous y voyez dans « Publications » avant de réessayer. Si le partage du téléphone échoue, téléchargez le PNG.</p>
        </template>
      </details>
    </div>
    <footer class="guide-foot">
      <button type="button" class="secondary" :disabled="step === 0" @click="emit('step', step - 1)">Précédent</button>
      <button v-if="step < titles.length - 1" type="button" class="primary" @click="emit('step', step + 1)">Suivant</button>
      <button v-else type="button" class="primary" @click="emit('finish')">Terminer</button>
    </footer>
  </dialog>
</template>

<style scoped>
.poster-guide { width: min(36rem, calc(100% - 32px)); max-height: calc(min(100dvh, var(--guide-viewport, 100dvh)) - 32px); margin: auto; padding: 0; border: 1px solid var(--line); border-radius: var(--radius); color: var(--text); background: var(--surface); box-shadow: var(--lift); overflow: auto; overscroll-behavior: contain }
.poster-guide[open] { display: flex; flex-direction: column }
.poster-guide::backdrop { background: var(--scrim) }
.guide-head, .guide-foot { flex: none; display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 8px 24px }
.guide-head { border-bottom: 1px solid var(--line) }
.guide-head p { margin: 0; font-size: 15px; font-weight: 700 }
.guide-body { min-height: 5rem; padding: 24px 28px 16px; overflow: auto; overscroll-behavior: contain }
.guide-body h2 { margin: 0 0 16px; font-size: 28px; line-height: 1.16; letter-spacing: -.025em }
.guide-body h2 span { display: block; margin-bottom: 8px; font-size: 13px; line-height: 18px; font-weight: 650; letter-spacing: 0; color: var(--accent-ink) }
.guide-copy p, details p { margin: 0 0 .75em; font-size: 16px; line-height: 1.5 }
.guide-copy strong { font-weight: 700 }
.guide-body details { margin-top: 18px }
.guide-body details p { color: var(--muted); font-size: 15px }
.guide-foot { padding-block: 12px; border-top: 1px solid var(--line) }
@media (max-width: 600px) {
  .poster-guide { width: 100%; max-width: 100%; inset: 0 0 max(0px, calc(100dvh - var(--guide-viewport, 100dvh))); max-height: min(100dvh, var(--guide-viewport, 100dvh)); margin: auto 0 0; border-radius: 20px 20px 0 0 }
  .guide-head, .guide-foot { padding-inline: max(16px, env(safe-area-inset-left)) max(16px, env(safe-area-inset-right)) }
  .guide-body { padding: 20px max(16px, env(safe-area-inset-right)) 12px max(16px, env(safe-area-inset-left)) }
  .guide-foot { padding-bottom: max(12px, env(safe-area-inset-bottom)); flex-wrap: wrap }
  .guide-body h2 { font-size: 24px }
}
</style>
