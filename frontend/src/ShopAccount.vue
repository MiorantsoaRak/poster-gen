<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, ApiError, changePassword, upload, writeProfile, type Profile, type Terms } from './api'
import { termsDate } from './generation'

defineProps<{ terms: Terms | null; termsUnavailable: boolean; support: string }>()
const emit = defineEmits<{ saved: [profile: Profile]; terms: []; signOut: [] }>()
const baseline = ref<Profile>(), draft = ref<Profile>(), conflict = ref(false), uncertain = ref(false)
const working = ref(false), profileError = ref(''), profileNotice = ref('')
const fieldNames = { name: 'Nom de la boutique', contact: 'Contact de la boutique', logo_asset: 'Logo' } as const
type ProfileField = keyof typeof fieldNames
const overlaps = ref<ProfileField[]>([])
function choose(field: ProfileField, saved: boolean) {
  if (saved && draft.value && baseline.value) draft.value[field] = baseline.value[field]
  overlaps.value = overlaps.value.filter(key => key !== field)
}
const fields = Object.keys(fieldNames) as ProfileField[]
const dirty = computed(() => fields.some(key => (draft.value?.[key] || '') !== (baseline.value?.[key] || '')))
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
  working.value = true; profileError.value = ''; profileNotice.value = ''
  try {
    const saved = await api<Profile>('/api/shop-profile', { timeout: 20_000 })
    const merged = { ...saved }
    if (conflict.value && baseline.value && draft.value) {
      for (const field of fields) {
        const local = draft.value[field]?.trim() || null
        if (local === baseline.value[field]) continue
        merged[field] = local
        if (saved[field] !== baseline.value[field] && saved[field] !== local) overlaps.value.push(field)
      }
      profileNotice.value = 'Version enregistrée relue. Vérifiez vos modifications avant de les enregistrer.'
    }
    baseline.value = saved; draft.value = merged; conflict.value = false
  } catch (reason) { profileError.value = message(reason) }
  finally { working.value = false }
}
async function save() {
  if (working.value || !draft.value || conflict.value || overlaps.value.length) return
  working.value = true; profileError.value = ''; profileNotice.value = ''
  try {
    const saved = await writeProfile(draft.value)
    baseline.value = saved; draft.value = { ...saved }; uncertain.value = false
    profileNotice.value = 'Profil enregistré.'; emit('saved', saved)
  } catch (reason) {
    conflict.value = reason instanceof ApiError && reason.code === 'revision_conflict'
    uncertain.value = !(reason instanceof ApiError && reason.status >= 400 && reason.status < 500)
    profileError.value = uncertain.value ? 'L’enregistrement n’a pas pu être confirmé. Réessayez la même demande.'
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
onMounted(readProfile)
</script>

<template>
  <section class="shop-account" aria-labelledby="titre-compte">
    <header><h1 id="titre-compte" class="page-title" tabindex="-1">Mon compte</h1><a href="#accueil">Retour à l’accueil</a></header>
    <form aria-labelledby="titre-profil" @input="rememberEdit" @submit.prevent="save">
      <h2 id="titre-profil" ref="profileHeading" tabindex="-1">Ma boutique</h2>
      <fieldset v-if="draft" :disabled="working || conflict || uncertain || !!overlaps.length">
        <label>Nom de la boutique<input v-model="draft.name" autocomplete="organization" maxlength="160" /></label>
        <label>{{ fieldNames.contact }}<textarea v-model="draft.contact" rows="2" maxlength="500" aria-describedby="aide-contact-boutique" /></label>
        <small id="aide-contact-boutique">Ces coordonnées peuvent apparaître sur vos affiches si vous choisissez de les inclure.</small>
        <label class="file-pick">Logo<input type="file" accept="image/jpeg,image/png,image/webp" @change="logo" /><span class="pick-button">{{ draft.logo_asset ? 'Changer le logo' : 'Choisir le logo' }}</span></label>
        <div v-if="draft.logo_asset" class="row"><img class="logo-preview" :src="'/api/assets/' + draft.logo_asset" width="100" height="64" alt="Logo de la boutique" />
          <button type="button" class="text-button" @click="rememberEdit($event); draft.logo_asset = null">Retirer le logo</button></div>
      </fieldset>
      <p v-else-if="working" role="status">Lecture du profil…</p>
      <template v-if="draft && baseline">
        <fieldset v-for="field in overlaps" :key="field" class="collision"><legend>{{ fieldNames[field] }} modifié sur les deux appareils</legend>
          <div v-for="source in (['draft', 'saved'] as const)" :key="source">
            <strong>{{ source === 'draft' ? 'Votre saisie' : 'Version enregistrée' }}</strong>
            <img v-if="field === 'logo_asset' && (source === 'draft' ? draft : baseline).logo_asset" class="logo-preview"
              :src="'/api/assets/' + (source === 'draft' ? draft : baseline).logo_asset" width="80" height="60" :alt="source === 'draft' ? 'Votre logo' : 'Logo enregistré'" />
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
    <section aria-labelledby="titre-assistance"><h2 id="titre-assistance">Assistance Doka Studio</h2><p>Contactez {{ support || 'l’opérateur qui vous a remis votre identifiant' }}.</p>
      <button class="secondary" @click="emit('signOut')">Se déconnecter</button></section>
  </section>
</template>

<style scoped>
.shop-account { width: min(100%, var(--page)); margin: auto; padding: 18px 0 30px; overflow-wrap: anywhere }
header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px }
h1, h2, p { margin: 0 }
form, section > section { display: grid; gap: 12px; margin-top: 20px; padding: 18px; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface) }
fieldset { display: grid; gap: 12px; border: 0; min-width: 0; margin: 0; padding: 0 }
input[type=file] { max-width: 100% }
.collision { padding: 12px; border: 1px solid var(--line); border-radius: var(--radius) }
.collision > div { display: grid; gap: 6px }
button, a { justify-self: start }
a, summary { min-height: 44px; align-content: center; color: var(--text) }
details p { margin: 8px 0 }
</style>
