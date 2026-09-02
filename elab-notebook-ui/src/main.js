import { createApp } from 'vue'
import { createPinia } from 'pinia'
import axios from 'axios'


import '@fontsource/inter/latin-400.css'
import '@fontsource/inter/latin-500.css'
import '@fontsource/inter/latin-600.css'
import '@fontsource/inter/latin-700.css'
import './style.css'


import './styles/list-page.css'


import './styles/add-row.css'


import './styles/file-attachment.css'
import './styles/image-lightbox.css'

import './styles/rich-content.css'


import './styles/page-width.css'
import App from './App.vue'
import router from './router'

axios.defaults.withCredentials = true

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
