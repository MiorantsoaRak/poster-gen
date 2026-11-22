// Local design sample. The offer shown in the PNG belongs to the archived style study.
const get = id => document.getElementById(id)
const products = {
  live: { name: 'JBL Live 770NC', art: '../doka-console/assets/clair.jpg' },
  sony: { name: 'Sony WH-1000XM6', art: '../doka-console/assets/sombre.jpg' },
  tune: { name: 'JBL Tune 770NC lilas', art: 'jbl-tune-770nc.png' }
}
const order = ['live', 'sony']
const standalone = location.hash === '#fichier'
let confirmed = standalone
let single = false
let guideStep = 0
const icons = {
  remove: '<svg aria-hidden="true" viewBox="0 0 20 20"><path d="M4 5h12M7 5V3h6v2M5 5l1 12h8l1-12M9 8v6m3-6v6"/></svg>',
  move: '<svg aria-hidden="true" viewBox="0 0 20 20"><path d="M4 6h12M4 10h12M4 14h12"/></svg>'
}
function img(id) {
  const image = document.createElement('img')
  image.src = products[id].art
  image.alt = products[id].name
  return image
}
function button(text, run, className = '') {
  const b = document.createElement('button')
  b.textContent = text
  b.className = className
  b.onclick = run
  return b
}
function move(id, target) {
  const index = order.indexOf(id)
  if (index < 0 || target < 0 || target >= order.length || target === index) return
  order.splice(index, 1)
  order.splice(target, 0, id)
  render()
  get('move-' + id)?.focus()
  get('feedback').textContent = products[id].name + ' en position ' + (target + 1) + '.'
}
function add(id) {
  if (!order.includes(id)) order.push(id)
  render()
  get('feedback').textContent = products[id].name + ' ajoutée à la publication.'
  get('check-post').focus()
}
function render() {
  const available = get('available')
  const selection = get('selection')
  available.replaceChildren()
  get('pending').replaceChildren()
  selection.replaceChildren()
  for (const id of [...order, ...Object.keys(products).filter(id => !order.includes(id))]) {
    const index = order.indexOf(id)
    const pending = id === 'tune' && !confirmed
    const row = document.createElement('li')
    row.className = index < 0 ? 'item other' : 'item'
    if (index >= 0) {
      const position = document.createElement('span')
      position.className = 'ordinal'
      position.textContent = String(index + 1)
      row.append(position)
    }
    const words = document.createElement('span')
    const title = document.createElement('strong')
    title.textContent = products[id].name
    const status = document.createElement('small')
    status.textContent = pending ? 'Version approuvée · fichier à confirmer' : (index === 0 ? 'En tête' : 'Fichier confirmé')
    words.append(title, status)
    row.append(img(id), words)
    if (index >= 0) {
      const controls = document.createElement('span')
      controls.className = 'controls'
      const remove = button('', () => {
        order.splice(order.indexOf(id), 1)
        render()
        get('pick-' + id).focus()
      }, 'move')
      remove.innerHTML = icons.remove
      remove.setAttribute('aria-label', 'Retirer ' + products[id].name)
      controls.append(remove)
      if (order.length > 1) {
        const handle = button('', () => {}, 'move')
        handle.innerHTML = icons.move
        handle.id = 'move-' + id
        handle.setAttribute('aria-label', 'Déplacer ' + products[id].name + ' avec la poignée ou les flèches haut et bas')
        handle.style.touchAction = 'none'
        handle.onkeydown = event => {
          if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return
          event.preventDefault()
          move(id, index + (event.key === 'ArrowUp' ? -1 : 1))
        }
        handle.onpointerdown = event => handle.setPointerCapture(event.pointerId)
        handle.onpointerup = event => {
          const at = Array.from(selection.children).findIndex(element => {
            const bounds = element.getBoundingClientRect()
            return event.clientY >= bounds.top && event.clientY <= bounds.bottom
          })
          move(id, at)
        }
        controls.append(handle)
      }
      row.append(controls)
      selection.append(row)
    } else {
      const pick = button(pending ? 'Vérifier le fichier final' : 'Ajouter', () => pending ? showFile() : add(id), 'text')
      pick.id = 'pick-' + id
      row.append(pick)
      if (pending) get('pending').append(row)
      else available.append(row)
    }
  }
  get('available-title').hidden = available.hidden = !available.children.length
  get('prepare').hidden = confirmed
  get('photos').replaceChildren(...order.map(img))
  get('total').textContent = order.length + (order.length > 1 ? ' images' : ' image')
  const caption = get('description').value
  get('preview-caption').textContent = caption
  const tooLong = [...caption].length > 2000
  get('description-error').hidden = !tooLong
  get('description').setAttribute('aria-invalid', String(tooLong))
  get('check-post').disabled = !order.length || tooLong
}
function showFile() {
  get('batch').hidden = true
  get('file').hidden = false
  get('file').classList.toggle('confirmed', confirmed)
  get('file-title').textContent = confirmed ? 'Votre affiche est prête' : 'Vérifier le fichier final'
  get('file-state').textContent = confirmed ? 'Fichier confirmé' : 'Fichier à confirmer'
  get('inspect').hidden = confirmed
  get('ready').hidden = !confirmed
  get('return-add').hidden = standalone
  get('single').classList.toggle('primary', standalone)
  window.scrollTo(0, 0)
  get('file-title').focus()
}
function batch() {
  get('batch').hidden = false
  get('file').hidden = true
  render()
  window.scrollTo(0, 0)
  get('batch-title').focus()
}
function check(isSingle) {
  single = isSingle
  get('single-label').hidden = get('single-description').hidden = !single
  get('post-caption').hidden = single
  get('post-caption').textContent = get('description').value
  get('post-images').replaceChildren(...(single ? ['tune'] : order).map(img))
  get('review-post').showModal()
}
function guide() {
  const steps = [...document.querySelectorAll('.steps li')]
  steps.forEach((step, index) => { step.hidden = index !== guideStep })
  get('guide-progress').textContent = 'Étape ' + (guideStep + 1) + ' sur ' + steps.length
  if (get('help').open) get('guide-progress').focus()
  get('previous').disabled = guideStep === 0
  get('next').textContent = guideStep === steps.length - 1 ? 'Terminer' : 'Suivant'
}
get('description').oninput = render
get('back').onclick = batch
get('confirm-file').onclick = () => { confirmed = true; showFile() }
get('return-add').onclick = () => { batch(); add('tune') }
get('single').onclick = () => check(true)
get('check-post').onclick = () => check(false)
get('send').onclick = () => {
  get('review-post').close()
  batch()
  get('feedback').textContent = 'Simulation terminée. Votre publication en préparation est conservée.'
  get('feedback').scrollIntoView({ block: 'nearest' })
}
get('help-open').onclick = () => { guide(); get('help').showModal() }
get('previous').onclick = () => { guideStep--; guide() }
get('next').onclick = () => {
  if (guideStep === 4) { guideStep = 0; get('help').close(); return }
  guideStep++
  guide()
}
render()
if (standalone) showFile()
