import { createRouter, createWebHistory } from 'vue-router'
import ShellLayout from './components/layout/ShellLayout.vue'
import Dashboard from './components/dashboard/Dashboard.vue'
import TemplatesList from './components/templates/TemplatesList.vue'
import TemplateDetail from './components/templates/TemplateDetail.vue'
import { useUserStore } from './stores/user'

const routes = [
  {
    path: '/',
    component: ShellLayout,
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: Dashboard
      },
      {
        path: 'templates',
        name: 'TemplatesList',
        component: TemplatesList
      },
      {
        path: 'templates/:id',
        name: 'TemplateDetail',
        component: TemplateDetail
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()

  // Load the user profile from Frappe session if not loaded
  if (!userStore.user.name) {
    await userStore.fetchUserProfile()
  }

  // Check state after fetch
  if (userStore.user.name && userStore.user.name !== 'Guest') {
    // Load employee scope if it's the initial load
    if (userStore.employeeScope.scope === 'all' && userStore.employeeScope.projects.length === 0) {
      await userStore.fetchEmployeeScope()
    }
    next()
  } else {
    // Redirect to Frappe built-in login via the secure redirect helper
    const redirectUrl = '/api/method/elab_notebook.elab_notebook.api.user.login_redirect'
    window.location.href = `http://localhost:8000/login?redirect-to=${encodeURIComponent(redirectUrl)}`
  }
})

export default router
