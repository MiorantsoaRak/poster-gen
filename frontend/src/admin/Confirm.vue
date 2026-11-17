<script setup lang="ts">
// The one confirmation (D-ADMIN-005): the native modal <dialog>, so Esc and the inert page come from the browser. Written
// by hand: the alertdialog role, its name and description, Cancel focused first (a stray Enter cancels), and focus back
// on the control that opened it.
import { nextTick, ref } from 'vue'

export interface Question { title: string; text: string; action: string }
const dialog = ref<HTMLDialogElement>(), cancel = ref<HTMLButtonElement>(), question = ref<Question>({ title: '', text: '', action: '' })
let answer: ((yes: boolean) => void) | undefined, opener: Element | null = null

async function ask(asked: Question): Promise<boolean> {
  question.value = asked
  opener = document.activeElement
  await nextTick()
  dialog.value!.showModal()
  cancel.value!.focus()
  return new Promise(resolve => { answer = resolve })
}
// Answered at once by its buttons and by Esc (`cancel`). Not by the `close` event: it is queued, and one from a quick
// Cancel could arrive after the next question opened and answer that one.
function finish(yes: boolean) {
  const done = answer
  if (!done) return
  answer = undefined
  dialog.value!.close()
  question.value = { title: '', text: '', action: '' }  // a closed question keeps no shop's name in the page
  if (opener instanceof HTMLElement) opener.focus()
  opener = null
  done(yes)
}
// A close the browser made without `cancel` (its close-request rules may skip that event) is a no; a late one that
// arrives once the dialog is open again belongs to an earlier question, already answered.
function closed() { if (!dialog.value!.open) finish(false) }
// The session ended while a question was open: it is answered no, and nothing is sent.
const dismiss = () => finish(false)
defineExpose({ ask, dismiss })
</script>

<template>
  <dialog ref="dialog" role="alertdialog" aria-labelledby="confirm-title" aria-describedby="confirm-text" @cancel="finish(false)" @close="closed">
    <h2 id="confirm-title">{{ question.title }}</h2>
    <p id="confirm-text">{{ question.text }}</p>
    <div class="actions">
      <button ref="cancel" type="button" @click="finish(false)">Cancel</button>
      <button type="button" class="primary" @click="finish(true)">{{ question.action }}</button>
    </div>
  </dialog>
</template>
