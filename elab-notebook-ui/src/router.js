import { createRouter, createWebHistory } from 'vue-router'
import ShellLayout from './components/layout/ShellLayout.vue'
import Dashboard from './components/dashboard/Dashboard.vue'
import TemplatesList from './components/templates/TemplatesList.vue'
import TemplateDetail from './components/templates/TemplateDetail.vue'
import TeamSetup from './components/team/TeamSetup.vue'
import TeamDetail from './components/team/TeamDetail.vue'
import ExperimentList from './components/experiments/ExperimentList.vue'
import ExperimentForm from './components/experiments/ExperimentForm.vue'
import ExperimentDetail from './components/experiments/ExperimentDetail.vue'
import SampleList from './components/samples/SampleList.vue'
import SampleDetail from './components/samples/SampleDetail.vue'
import Settings from './components/settings/Settings.vue'
import { useUserStore } from './stores/user'
import { loginUrl } from './utils/frappeUrl'

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
      },
      {
        path: 'elab-notebook',
        name: 'TeamSetup',
        component: TeamSetup
      },
      {
        path: 'elab-notebook/:id',
        name: 'TeamDetail',
        component: TeamDetail
      },
      {
        path: 'experiments',
        name: 'ExperimentList',
        component: ExperimentList
      },
      {
        path: 'experiments/new',
        name: 'ExperimentForm',
        component: ExperimentForm
      },
      {
        path: 'experiments/:id',
        name: 'ExperimentDetail',
        component: ExperimentDetail
      },
      {
        path: 'samples',
        name: 'SampleList',
        component: SampleList
      },
      {
        path: 'samples/:id',
        name: 'SampleDetail',
        component: SampleDetail
      },
      {
        path: 'settings',
        name: 'Settings',
        component: Settings
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, from) => {
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
    return true
  } else {
    // Frappe's own login page, on whichever origin is serving the desk - see
    // loginUrl(). Written inline here with a hardcoded localhost:8000 until now,
    // which sent every logged-out visitor in production to their own machine.
    window.location.href = loginUrl()
    return false
  }
})

export default router
