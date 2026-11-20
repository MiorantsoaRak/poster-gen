// Doka Studio mockup: the icon set and the few behaviours both pages share. No data leaves the page.
// State in the address, so a state can be linked: ?theme=dark&primary=ink&rail=1&view=chat
const ICONS = {
  home: 'M3 10.5 12 3l9 7.5M5 9.5V20h5v-6h4v6h5V9.5',
  grid: 'M4 4h7v7H4zM13 4h7v4h-7zM13 11h7v9h-7zM4 14h7v6H4z',
  palette: 'M12 3a9 9 0 1 0 0 18c1.2 0 2-.8 2-1.8 0-1.4 1-2.2 2.4-2.2H18a3 3 0 0 0 3-3c0-6-4-11-9-11ZM7.5 12h.01M9.5 8h.01M14.5 8h.01',
  plus: 'M12 5v14M5 12h14',
  coins: 'M9 14a6 6 0 1 0 0-12 6 6 0 0 0 0 12ZM15.5 9.2a6 6 0 1 1-6.3 6.3',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4.5 20a7.5 7.5 0 0 1 15 0',
  menu: 'M4 7h16M4 12h16M4 17h16',
  panel: 'M4 5h16v14H4zM9.5 5v14',
  sun: 'M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4',
  moon: 'M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z',
  up: 'M12 19V5M6 11l6-6 6 6',
  clip: 'M20 11.5 12.3 19a5 5 0 0 1-7-7l8-8a3.4 3.4 0 0 1 4.8 4.8l-8 8a1.8 1.8 0 0 1-2.5-2.5l7.3-7.3',
  down: 'M6 9l6 6 6-6',
  right: 'M9 6l6 6-6 6',
  left: 'M15 6l-6 6 6 6',
  check: 'M5 12.5 10 17l9-10',
  search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14ZM20 20l-3.8-3.8',
  store: 'M4 9.5 5.5 4h13L20 9.5M4 9.5h16M4 9.5V20h16V9.5M9 20v-5h6v5',
  wallet: 'M4 7.5V18a2 2 0 0 0 2 2h14v-4M4 7.5A2.5 2.5 0 0 1 6.5 5H18v3M4 7.5A2.5 2.5 0 0 0 6.5 10H20v6h-4a3 3 0 0 1 0-6',
  pulse: 'M3 12h4l2.5-7 5 14 2.5-7h4',
  out: 'M10 5H5v14h5M15 8l4 4-4 4M19 12H9',
  x: 'M6 6l12 12M18 6 6 18',
  download: 'M12 4v11M7 11l5 5 5-5M5 20h14',
  share: 'M12 15V4M8 8l4-4 4 4M5 13v6h14v-6',
  pencil: 'M4 20l1-4L16.5 4.5a2.1 2.1 0 0 1 3 3L8 19l-4 1Z',
  image: 'M4 5h16v14H4zM4 16l4.5-4.5 4 4L15 13l5 5M9 9.5h.01',
  eye: 'M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12ZM12 14.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z',
  ratio: 'M6 3h12v18H6zM9 7h3M9 7v3',
  shield: 'M12 3 5 6v5.5c0 4.3 2.9 8 7 9.5 4.1-1.5 7-5.200 7-9.500V6l-7-3Z',
  sparkle: 'M12 4l1.8 5.200L19 11l-5.200 1.8L12 18l-1.800-5.200L5 11l5.200-1.800L12 4Z',
  dots: 'M6 12h.01M12 12h.01M18 12h.01',
}
const sprite = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
sprite.setAttribute('aria-hidden', 'true'); sprite.style.display = 'none'
sprite.innerHTML = Object.entries(ICONS).map(([name, d]) => `<symbol id="i-${name}" viewBox="0 0 24 24"><path d="${d}"/></symbol>`).join('')
document.body.prepend(sprite)

const root = document.documentElement, query = new URLSearchParams(location.search)
const stored = key => { try { return localStorage.getItem('doka.mock.' + key) } catch { return null } }
const store = (key, value) => { try { value == null ? localStorage.removeItem('doka.mock.' + key) : localStorage.setItem('doka.mock.' + key, value) } catch { /* a private window: the choice lasts the page */ } }

function theme(next) {
  root.dataset.theme = next
  for (const button of document.querySelectorAll('[data-theme-toggle]')) {
    button.setAttribute('aria-label', root.lang === 'fr' ? (next === 'dark' ? 'Passer au thème clair' : 'Passer au thème sombre') : (next === 'dark' ? 'Switch to the light theme' : 'Switch to the dark theme'))
    button.querySelector('use').setAttribute('href', next === 'dark' ? '#i-sun' : '#i-moon')
  }
}
theme(query.get('theme') || stored('theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'))
if (query.get('primary') === 'ink' || (!query.has('primary') && stored('primary') === 'ink')) root.dataset.primary = 'ink'
if (query.get('rail') === '1' || (!query.has('rail') && stored('rail') === '1')) root.dataset.rail = ''

const flag = (name, on) => on ? root.dataset[name] = '' : delete root.dataset[name]
document.addEventListener('click', event => {
  const hit = selector => event.target.closest(selector)
  if (hit('[data-theme-toggle]')) { const next = root.dataset.theme === 'dark' ? 'light' : 'dark'; theme(next); store('theme', next) }
  else if (hit('[data-rail-toggle]')) { const on = !('rail' in root.dataset); flag('rail', on); store('rail', on ? '1' : null); hit('[data-rail-toggle]').setAttribute('aria-expanded', String(!on)) }
  else if (hit('[data-drawer-open]')) flag('drawer', true)
  else if (hit('.scrim') || hit('[data-drawer-close]') || (hit('.side a') && 'drawer' in root.dataset)) flag('drawer', false)
  else if (hit('[data-primary-toggle]')) { const ink = !('primary' in root.dataset); ink ? root.dataset.primary = 'ink' : delete root.dataset.primary; store('primary', ink ? 'ink' : null) }
})
document.addEventListener('keydown', event => { if (event.key === 'Escape') flag('drawer', false) })

// Views of one page (the client's screens; the console's sections): a link with data-view shows the matching [data-screen].
function show(view) {
  const screens = [...document.querySelectorAll('[data-screen]')]
  if (!screens.some(screen => screen.dataset.screen === view)) return
  for (const screen of screens) screen.hidden = screen.dataset.screen !== view
  for (const link of document.querySelectorAll('[data-view]')) link.dataset.view === view ? link.setAttribute('aria-current', 'page') : link.removeAttribute('aria-current')
  document.body.dataset.view = view
  const title = document.querySelector(`[data-screen="${view}"]`).dataset.title
  for (const slot of document.querySelectorAll('[data-title-slot]')) slot.textContent = title
  window.scrollTo(0, 0)
  for (const thread of document.querySelectorAll('.thread')) thread.scrollTop = thread.scrollHeight  // a conversation opens on its last message
}
document.addEventListener('click', event => {
  const link = event.target.closest('[data-view]')
  if (link) { event.preventDefault(); show(link.dataset.view); history.replaceState(null, '', '#' + link.dataset.view) }
})
show(query.get('view') || location.hash.slice(1) || document.body.dataset.view || '')
