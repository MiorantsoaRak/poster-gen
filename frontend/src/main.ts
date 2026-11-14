import { createApp } from 'vue'
import App from './App.vue'
import './style.css'

// The theme is set in index.html before the first paint, and kept in step with the device in App.vue.
// iOS Safari applies :active, the press answer (D-POSTER-EDITOR-007), only on a page that listens to touches.
document.addEventListener('touchstart', () => {}, { passive: true })
createApp(App).mount('#app')
