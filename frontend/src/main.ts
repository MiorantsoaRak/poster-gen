import { createApp } from 'vue'
import App from './App.vue'
import './style.css'

// Dark is the default (the poster is the only bright thing); the light variant is for bright daylight.
try { if (localStorage.getItem('affiche.theme') === 'clair') document.documentElement.dataset.theme = 'clair' } catch { /* default theme */ }

createApp(App).mount('#app')
