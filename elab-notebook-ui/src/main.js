import { createApp } from 'vue'
import { createPinia } from 'pinia'
import axios from 'axios'
import './style.css'
// Shared list-page furniture (filter bar, table shell, status pills,
// pagination, loading/empty states). Imported once here rather than per page:
// .spinner alone is used by eleven components, so a per-page import would just
// recreate the cross-component borrowing this file exists to remove.
import './styles/list-page.css'
// The add-row control shared by every editable child table (components/common/
// AddRow.vue). Same reasoning: one declaration, bundled once.
import './styles/add-row.css'
import App from './App.vue'
import router from './router'

axios.defaults.withCredentials = true

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
