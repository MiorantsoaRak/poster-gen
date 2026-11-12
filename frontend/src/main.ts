import { createApp } from 'vue'
import App from './App.vue'
import './style.css'

// Dark is the default (the poster is the only bright thing); the light variant is for bright daylight.
try { if (localStorage.getItem('affiche.theme') === 'clair') document.documentElement.dataset.theme = 'clair'; document.querySelector('meta[name=theme-color]')?.setAttribute('content', '#f4f2ef') } catch { /* default theme */ }

createApp(App).mount('#app')
