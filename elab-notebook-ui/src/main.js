import { createApp } from 'vue'
import { createPinia } from 'pinia'
import axios from 'axios'
// Inter, self-hosted through @fontsource rather than the Google Fonts CDN: this
// app runs on an internal lab network, where an external font request either
// stalls first paint or fails outright and drops every screen to the fallback.
// Only the latin subset and the four weights the type scale actually uses are
// pulled in - importing the package root would ship nine weights across five
// subsets for no visible gain. Imported before style.css so the @font-face rules
// are registered by the time --font-sans is resolved.
import '@fontsource/inter/latin-400.css'
import '@fontsource/inter/latin-500.css'
import '@fontsource/inter/latin-600.css'
import '@fontsource/inter/latin-700.css'
import './style.css'
// Shared list-page furniture (filter bar, table shell, status pills,
// pagination, loading/empty states). Imported once here rather than per page:
// .spinner alone is used by eleven components, so a per-page import would just
// recreate the cross-component borrowing this file exists to remove.
import './styles/list-page.css'
// The add-row control shared by every editable child table (components/common/
// AddRow.vue). Same reasoning: one declaration, bundled once.
import './styles/add-row.css'
// Caps how wide page content grows on a large monitor. Imported last of the
// shared sheets so its ceiling wins over any page's own width rule.
import './styles/page-width.css'
import App from './App.vue'
import router from './router'

axios.defaults.withCredentials = true

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
