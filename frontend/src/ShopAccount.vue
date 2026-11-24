<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api, ApiError, bound, changePassword, shopLines, state, upload, writeProfile, type Profile, type Terms } from './api'
import { facebookCard, isPublishOrigin, manualReturnLine, startFacebook, type FacebookAnswer } from './facebook'
import { termsDate } from './generation'

const props = withDefaults(defineProps<{ terms: Terms | null; termsUnavailable: boolean; support: string; publishOrigin?: string | null; interactive?: boolean }>(), { interactive: true })
const emit = defineEmits<{ saved: [profile: Profile]; terms: []; signOut: [] }>()
const baseline = ref<Profile>(), draft = ref<Profile>(), conflict = ref(false), uncertain = ref(false)
const working = ref(false), profileError = ref(''), profileNotice = ref(''), linesError = ref('')
const fieldNames = { name: 'Nom de la boutique', contact: 'Contact de la boutique', logo_asset: 'Logo', lines: 'Lignes de la boutique' } as const
type ProfileField = keyof typeof fieldNames
// The draft holds three line fields, its own copy (D-KIT-005, r1 7): never the saved list itself, which v-model would edit.
const form = (profile: Profile): Profile => ({ ...profile, lines: [0, 1, 2].map(index => profile.lines?.[index] ?? '') })
// A field as it would be saved, compared by value: the lines as the list sent.
const value = (profile: Profile | undefined, field: ProfileField) =>
  JSON.stringify(field === 'lines' ? shopLines(profile?.lines) : profile?.[field]?.trim() || null)
const overlaps = ref<ProfileField[]>([])
function choose(field: ProfileField, saved: boolean) {
  if (saved && draft.value && baseline.value) draft.value = { ...draft.value, [field]: form(baseline.value)[field] }
  overlaps.value = overlaps.value.filter(key => key !== field)
}
const fields = Object.keys(fieldNames) as ProfileField[]
const dirty = computed(() => fields.some(key => value(draft.value, key) !== value(baseline.value, key)))
const pending = computed(() => working.value && !!draft.value)
const profileHeading = ref<HTMLElement>()
let lastEdit: HTMLElement | null = null
function rememberEdit(event: Event) {
  if (event.target instanceof HTMLElement) lastEdit = event.target
}
function focusEdit() {
  if (lastEdit?.isConnected && !lastEdit.matches(':disabled')) lastEdit.focus()
  else profileHeading.value?.focus()
}
defineExpose({ dirty, pending, focusEdit })
const current = ref(''), replacement = ref(''), changing = ref(false), passwordError = ref(''), passwordNotice = ref('')
const message = (reason: unknown) => reason instanceof Error ? reason.message : 'La demande a échoué.'

async function readProfile() {
  if (working.value) return
  working.value = true; profileError.value = ''; profileNotice.value = ''; linesError.value = ''
  try {
    const saved = await api<Profile>('/api/shop-profile', { timeout: 20_000 })
    let merged = form(saved)
    if (conflict.value && baseline.value && draft.value) {
      for (const field of fields) {
        const local = value(draft.value, field), before = value(baseline.value, field), now = value(saved, field)
        if (local === before) continue
        merged = { ...merged, [field]: form(draft.value)[field] }
        if (now !== before && now !== local) overlaps.value.push(field)
      }
      profileNotice.value = 'Version enregistrée relue. Vérifiez vos modifications avant de les enregistrer.'
    }
    baseline.value = saved; draft.value = merged; conflict.value = false
  } catch (reason) { profileError.value = message(reason) }
  finally { working.value = false }
}
async function save() {
  if (working.value || !draft.value || conflict.value || overlaps.value.length) return
  working.value = true; profileError.value = ''; profileNotice.value = ''; linesError.value = ''
  try {
    const saved = await writeProfile(draft.value, draft.value.lines)
    baseline.value = saved; draft.value = form(saved); uncertain.value = false
    profileNotice.value = 'Profil enregistré.'; emit('saved', saved)
  } catch (reason) {
    conflict.value = reason instanceof ApiError && reason.code === 'revision_conflict'
    uncertain.value = !(reason instanceof ApiError && reason.status >= 400 && reason.status < 500)
    // A refused line: the server's rule, said at the three fields.
    if (reason instanceof ApiError && reason.field === 'lines') linesError.value = reason.message
    else profileError.value = uncertain.value ? 'L’enregistrement n’a pas pu être confirmé. Réessayez la même demande.'
      : conflict.value ? 'Le profil a changé sur un autre appareil. Vos modifications sont conservées.' : message(reason)
  } finally { working.value = false }
}
async function logo(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]
  if (!file || !draft.value || working.value) return
  working.value = true; profileError.value = ''; profileNotice.value = ''
  try { draft.value.logo_asset = (await upload(file, 'logo', 20_000)).asset }
  catch (reason) { profileError.value = message(reason) }
  finally { working.value = false; input.value = '' }
}
async function password() {
  if (changing.value) return
  changing.value = true; passwordError.value = ''; passwordNotice.value = ''
  try {
    await changePassword(current.value, replacement.value)
    passwordNotice.value = 'Mot de passe modifié. Cet appareil reste connecté. Les autres appareils ont été déconnectés.'
  } catch (reason) {
    passwordError.value = reason instanceof ApiError && reason.status >= 400 && reason.status < 500 && reason.code !== 'invalid_response'
      ? reason.message : 'La modification du mot de passe n’a pas pu être confirmée. Vérifiez le nouveau mot de passe à votre prochaine connexion.'
  } finally { current.value = ''; replacement.value = ''; changing.value = false }
}

// The « Page Facebook » card (D-FB-PUBLISH-004), only when the service has the feature. A refusal answered to the return
// page comes back once in the answer's last_error: that page keeps nothing in the browser.
const facebookOn = ref<boolean | null>(null), facebook = ref<FacebookAnswer>(), facebookPick = ref(''), facebookBusy = ref(false), facebookError = ref('')
const facebookState = computed(() => facebook.value && facebookCard(facebook.value))
const origin = computed(() => isPublishOrigin(props.publishOrigin) ? props.publishOrigin : null)
const facebookHeading = ref<HTMLElement>(), manualReturn = ref(false)
let focusedFacebook = false
watch([origin, facebookHeading, () => props.interactive], ([from, heading, interactive]) => {
  if (from && heading && interactive && !focusedFacebook) {
    heading.focus()
    focusedFacebook = document.activeElement === heading
  }
}, { flush: 'post' })
function showFacebook(answer: FacebookAnswer) {
  facebook.value = answer; facebookPick.value = answer.choice?.length === 1 ? answer.choice[0].id : ''
}
async function readFacebook() {
  facebookError.value = ''
  try {
    // null while the service has not said: a failed read shows the card with its retry, a read `false` hides it.
    if (facebookOn.value !== true) facebookOn.value = null
    facebookOn.value = !!(await api<{ facebook?: boolean }>('/api/capabilities', { timeout: 20_000 })).facebook
    if (!facebookOn.value) return
    const answer = await api<FacebookAnswer>('/api/facebook', { timeout: 20_000 })
    showFacebook(answer); facebookError.value = answer.last_error?.message_fr ?? ''
  } catch (reason) { facebookError.value = message(reason) }
}
// A refusal of a choice or a disconnection: the card reads the state again, the refusal's sentence kept.
async function onFacebook(run: () => Promise<void>) {
  if (facebookBusy.value) return
  facebookBusy.value = true; facebookError.value = ''
  try { await run() }
  catch (reason) {
    facebookError.value = message(reason)
    await api<FacebookAnswer>('/api/facebook', { timeout: 20_000 }).then(showFacebook, () => undefined /* the sentence above stays */)
  } finally { facebookBusy.value = false }
}
const connectFacebook = () => onFacebook(async () => {
  const shop = bound.value
  if (typeof shop !== 'number' || state.value !== 'shown') return
  const still = () => bound.value === shop && state.value === 'shown' && location.hash === '#compte' && !!facebookHeading.value?.isConnected
  if (await startFacebook(shop, origin.value, { still, unkept: manualReturn.value }) === 'unkept') manualReturn.value = true
})
// Back from Facebook for a post (D-KIT-008): once the Page is connected, the same post by itself (the link stays). The
// address changes as a link's would: App.vue still asks about an unsaved profile.
const choosePage = () => onFacebook(async () => {
  showFacebook(await api<FacebookAnswer>('/api/facebook/page', { method: 'POST', timeout: 20_000,
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ page_id: facebookPick.value }) }))
  if (origin.value && facebookState.value === 'connected' && location.hash === '#compte') location.hash = origin.value
})
const disconnectFacebook = () => onFacebook(async () => showFacebook(await api<FacebookAnswer>('/api/facebook/page', { method: 'DELETE', timeout: 20_000 })))
onMounted(readProfile)
onMounted(readFacebook)
</script>

<template>
  <section class="shop-account" aria-labelledby="titre-compte">
    <header><h1 id="titre-compte" class="page-title" tabindex="-1">Mon compte</h1><a class="back" href="#accueil">Retour à l’accueil</a></header>
    <form aria-labelledby="titre-profil" @input="rememberEdit" @submit.prevent="save">
      <h2 id="titre-profil" ref="profileHeading" tabindex="-1">Ma boutique</h2>
      <fieldset v-if="draft" :disabled="working || conflict || uncertain || !!overlaps.length">
        <label>Nom de la boutique<input v-model="draft.name" autocomplete="organization" maxlength="160" /></label>
        <label>{{ fieldNames.contact }}<textarea v-model="draft.contact" rows="2" maxlength="500" aria-describedby="aide-contact-boutique" /></label>
        <small id="aide-contact-boutique">Ces coordonnées peuvent apparaître sur vos affiches si vous choisissez de les inclure.</small>
        <fieldset class="lines"><legend>{{ fieldNames.lines }}</legend>
          <small id="aide-lignes">Vos conditions de vente, écrites une fois : garantie, livraison, paiement. Sans montant, remise ni numéro. Elles peuvent être dessinées sur vos affiches si vous choisissez de les inclure.</small>
          <label v-for="index in 3" :key="index">Ligne {{ index }}<input v-model="draft.lines![index - 1]" autocomplete="off" maxlength="40"
            aria-describedby="aide-lignes erreur-lignes" :aria-invalid="!!linesError || undefined" @input="linesError = ''" /></label>
          <p v-if="linesError" id="erreur-lignes" role="alert" class="why">{{ linesError }}</p>
        </fieldset>
        <label class="file-pick">Logo<input type="file" accept="image/jpeg,image/png,image/webp" @change="logo" /><span class="pick-button">{{ draft.logo_asset ? 'Changer le logo' : 'Choisir le logo' }}</span></label>
        <div v-if="draft.logo_asset" class="row"><img class="logo-preview" :src="'/api/assets/' + draft.logo_asset" width="100" height="64" alt="Logo de la boutique" />
          <button type="button" class="text-button" @click="rememberEdit($event); draft.logo_asset = null">Retirer le logo</button></div>
      </fieldset>
      <p v-else-if="working" role="status">Lecture du profil…</p>
      <template v-if="draft && baseline">
        <fieldset v-for="field in overlaps" :key="field" class="collision"><legend>{{ fieldNames[field] }} {{ field === 'lines' ? 'modifiées' : 'modifié' }} sur les deux appareils</legend>
          <div v-for="source in (['draft', 'saved'] as const)" :key="source">
            <strong>{{ source === 'draft' ? 'Votre saisie' : 'Version enregistrée' }}</strong>
            <img v-if="field === 'logo_asset' && (source === 'draft' ? draft : baseline).logo_asset" class="logo-preview"
              :src="'/api/assets/' + (source === 'draft' ? draft : baseline).logo_asset" width="80" height="60" :alt="source === 'draft' ? 'Votre logo' : 'Logo enregistré'" />
            <p v-else-if="field === 'lines'">{{ shopLines((source === 'draft' ? draft : baseline).lines).join(' · ') || 'Aucune ligne' }}</p>
            <p v-else>{{ (source === 'draft' ? draft : baseline)[field] || (field === 'logo_asset' ? 'Aucun logo' : 'Non renseigné') }}</p>
            <button type="button" class="secondary" @click="choose(field, source === 'saved')">{{ source === 'draft' ? 'Garder ma saisie' : 'Garder la version enregistrée' }}</button>
          </div>
        </fieldset>
      </template>
      <p v-if="profileError" role="alert" class="why">{{ profileError }}</p>
      <p v-if="profileNotice" role="status">{{ profileNotice }}</p>
      <button v-if="conflict || (!draft && profileError)" type="button" class="secondary" :disabled="working" @click="readProfile">{{ conflict ? 'Relire le profil enregistré' : 'Réessayer la lecture' }}</button>
      <button v-else-if="draft" class="primary" :disabled="working || !dirty || !!overlaps.length">{{ uncertain ? 'Réessayer l’enregistrement' : 'Enregistrer le profil' }}</button>
    </form>
    <section v-if="facebookOn || (facebookOn === null && facebookError) || (origin && facebookOn === false)" class="facebook" aria-labelledby="titre-facebook"><h2 id="titre-facebook" ref="facebookHeading" tabindex="-1">Page Facebook</h2>
      <p v-if="facebookError" role="alert" class="why">{{ facebookError }}</p>
      <template v-if="facebookState === 'choose'">
        <fieldset :disabled="facebookBusy"><legend>Page à connecter</legend>
          <label v-for="item in facebook?.choice ?? []" :key="item.id" class="check"><input v-model="facebookPick" type="radio" name="facebook-page" :value="item.id" /><span translate="no">{{ item.name }}</span></label>
        </fieldset>
        <button class="secondary" :disabled="facebookBusy || !facebookPick" @click="choosePage">Connecter cette Page</button>
        <small>Votre Page manque ? Au-delà de cent Pages autorisées, seules les cent premières sont lues.</small>
      </template>
      <template v-else-if="facebook?.page">
        <p v-if="facebookState === 'connected'">Page connectée : <strong translate="no">{{ facebook.page.name }}</strong></p>
        <template v-else><p><strong translate="no">{{ facebook.page.name }}</strong></p><p class="why">Reconnectez votre Page.</p></template>
      </template>
      <template v-if="facebookState === 'connect' || facebookState === 'reconnect'">
        <p v-if="manualReturn" id="retour-manuel" role="status">{{ manualReturnLine(origin) }}</p>
        <button class="secondary" :disabled="facebookBusy" :aria-describedby="manualReturn ? 'retour-manuel aide-facebook' : 'aide-facebook'" @click="connectFacebook">{{ manualReturn ? 'Continuer vers Facebook' : facebookState === 'reconnect' ? 'Reconnecter ma Page' : 'Connecter ma Page Facebook' }}</button>
        <small id="aide-facebook">Facebook vous demandera quelles Pages autoriser.</small>
        <small>Si Facebook refuse l’accès, votre Page doit d’abord être autorisée par Doka Studio : demandez-le à l’opérateur.</small>
        <small>Au-delà de cent Pages autorisées, seules les cent premières sont lues.</small>
      </template>
      <button v-if="facebookState === 'connected' || facebookState === 'reconnect'" class="secondary" :disabled="facebookBusy" @click="disconnectFacebook">Déconnecter</button>
      <p v-if="facebookOn === false" role="status">La publication sur Facebook est indisponible.</p>
      <template v-else-if="!facebook"><button v-if="facebookError" class="secondary" @click="readFacebook">Réessayer la lecture</button><p v-else role="status">Lecture de la Page Facebook…</p></template>
      <a v-if="origin" :href="'#' + origin">Revenir à ma publication</a>
    </section>
    <form aria-labelledby="titre-password" @submit.prevent="password"><h2 id="titre-password">Changer le mot de passe</h2>
      <fieldset :disabled="changing"><label>Mot de passe actuel<input v-model="current" type="password" autocomplete="current-password" maxlength="1024" required /></label>
        <label>Nouveau mot de passe<input v-model="replacement" type="password" autocomplete="new-password" minlength="10" maxlength="1024" aria-describedby="aide-password" required /></label>
        <small id="aide-password">Au moins 10 caractères.</small></fieldset>
      <p v-if="passwordError" role="alert" class="why">{{ passwordError }}</p><p v-if="passwordNotice" role="status">{{ passwordNotice }}</p>
      <button class="secondary" :disabled="changing">Modifier le mot de passe</button>
    </form>
    <section><h2>Conditions et données</h2>
      <p v-if="termsUnavailable" role="alert">Les conditions n’ont pas pu être chargées.</p>
      <template v-else-if="terms?.accepted_at"><p>Conditions acceptées le <time :datetime="terms.accepted_at">{{ new Date(terms.accepted_at).toLocaleDateString('fr-FR', { dateStyle: 'long' }) }}</time>.</p>
        <details><summary>Lire les conditions</summary><p>Version du {{ termsDate(terms.version) }}</p><p v-for="line in terms.paragraphs_fr" :key="line">{{ line }}</p></details></template>
      <p v-else-if="terms">Conditions à accepter.</p><p v-else role="status">Lecture des conditions…</p>
      <button v-if="termsUnavailable || (terms && !terms.accepted_at)" class="secondary" @click="emit('terms')">{{ termsUnavailable ? 'Réessayer la lecture des conditions' : 'Lire les conditions' }}</button>
      <a href="/donnees.html">Vos données</a>
    </section>
    <section aria-labelledby="titre-assistance"><h2 id="titre-assistance">Assistance Doka Studio</h2><p>Contactez {{ support || 'l’opérateur qui vous a remis votre identifiant' }}.</p></section>
    <p class="leave"><button class="secondary" @click="emit('signOut')">Se déconnecter</button></p>
  </section>
</template>

<style scoped>
.shop-account { width: min(100%, var(--page)); margin: auto; padding: 18px 0 30px; overflow-wrap: anywhere }
header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px }
h1, h2, p { margin: 0 }
form, section > section { display: grid; gap: 12px; margin-top: 20px; padding: 20px; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface) }
fieldset { display: grid; gap: 12px; border: 0; min-width: 0; margin: 0; padding: 0 }
input[type=file] { max-width: 100% }
/* The Pages to choose from (« Page Facebook »): native radios, sized as the application's checkboxes. */
input[type=radio] { width: 22px; height: 22px; min-height: 22px; flex: none; margin: -1px 0 0; padding: 0; accent-color: var(--text); cursor: pointer }
.facebook legend, .lines legend { padding: 0; font-size: 13px; font-weight: 650; color: var(--muted) }
/* The three lines' title reads above their own labels: the text colour, a step apart. */
.lines legend { margin-bottom: 6px; font-size: 14px; color: var(--text) }
#titre-facebook { scroll-margin-block-start: 5rem }
.collision { padding: 12px; border: 1px solid var(--line); border-radius: var(--radius) }
.collision > div { display: grid; gap: 6px }
button, a { justify-self: start }
/* The way back is shown before the title, on its own line (GOV.UK's back link; the console's « ← Shops »). It stays
   after the title for the keyboard: the title has the focus on arrival, and the first Tab is the way back. */
a.back { order: -1; flex-basis: 100%; display: inline-flex; align-items: center; gap: 8px; margin-bottom: -8px; color: var(--muted) }
a.back::before { content: ''; flex: none; width: 7px; height: 7px; border: solid currentColor; border-width: 0 0 1.6px 1.6px; rotate: 45deg }
/* Leaving is the last thing on the page, on its own: it is not part of the assistance. */
.leave { margin-top: 24px }
a, summary { min-height: 44px; align-content: center; color: var(--text) }
details p { margin: 8px 0 }
</style>
