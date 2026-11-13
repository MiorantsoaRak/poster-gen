import { createApp } from 'vue'
import App from './App.vue'
import './style.css'

// The theme is set in index.html before the first paint, and kept in step with the device in App.vue.
createApp(App).mount('#app')
