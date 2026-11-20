import { createApp } from 'vue'
import App from './App.vue'
import './style.css'

// The theme is set in index.html before the first paint, and kept in step with the device in App.vue.
// iOS Safari applies :active, the press answer (D-POSTER-EDITOR-007), only on a page that listens to touches.
document.addEventListener('touchstart', () => {}, { passive: true })
// A page title underlines its focus only for someone using the keys (style.css, .page-title). Until the first tap a
// browser counts a script's focus as the keyboard's, and would underline the title of every page opened (D-POLISH-003).
window.addEventListener('keydown', () => { document.documentElement.dataset.keys = '' }, true)
window.addEventListener('pointerdown', () => { delete document.documentElement.dataset.keys }, true)
createApp(App).mount('#app')
