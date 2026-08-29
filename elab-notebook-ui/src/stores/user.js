import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import axios from 'axios'

export const useUserStore = defineStore('user', () => {
  const user = ref({
    name: '',
    full_name: 'Guest User',
    first_name: 'Guest',
    initials: 'GU',
    user_image: null,
    // Employee id (not the User id) - required by Link fields such as
    // Experiment.employee_code, which point at Employee.
    employee: null,
    employee_name: null,
    role: 'Guest'
  })
  
  const loading = ref(true)
  const error = ref(null)

  // The project picker resets every session by design - most people work across
  // projects and a stale one silently filters the whole app. Settings lets an
  // individual opt out of that: with `rememberProject` on, the choice is also
  // written to localStorage and seeds the next session. fetchEmployeeScope still
  // validates whatever comes back, so a remembered project the user has since
  // lost access to falls back to 'all' like any other invalid value.
  const rememberProject = ref(localStorage.getItem('remember_project') === '1')

  const currentProject = ref(
    sessionStorage.getItem('active_project') ||
    (rememberProject.value ? localStorage.getItem('last_project') : null) ||
    'all'
  )
  const employeeScope = ref({ function_names: [], scope: 'all', projects: [] })

  const setRememberProject = (on) => {
    rememberProject.value = !!on
    localStorage.setItem('remember_project', on ? '1' : '0')
    if (on) {
      localStorage.setItem('last_project', currentProject.value)
    } else {
      localStorage.removeItem('last_project')
    }
  }

  const theme = ref(localStorage.getItem('theme') || 'dark')

  const createModalOpen = ref(false)
  const createModalProject = ref('')
  const createModalProjectName = ref('')
  const createModalEmployeeFunction = ref('')
  // Set only when the create flow starts from a team. Its presence is what marks
  // the run as team-originated, which in turn drives the read-only notebook rule.
  const createModalTeam = ref('')

  const openCreateExperimentModal = (proj = '', empFunc = '', projName = '', team = '') => {
    createModalProject.value = proj
    createModalEmployeeFunction.value = empFunc
    createModalProjectName.value = projName
    createModalTeam.value = team
    createModalOpen.value = true
  }

  const closeCreateExperimentModal = () => {
    createModalOpen.value = false
    createModalProject.value = ''
    createModalEmployeeFunction.value = ''
    createModalProjectName.value = ''
    createModalTeam.value = ''
  }

  const setTheme = (newTheme) => {
    theme.value = newTheme
    localStorage.setItem('theme', newTheme)
    if (newTheme === 'light') {
      document.documentElement.classList.add('light-theme')
    } else {
      document.documentElement.classList.remove('light-theme')
    }
  }

  // Apply initial theme status immediately
  if (theme.value === 'light') {
    document.documentElement.classList.add('light-theme')
  } else {
    document.documentElement.classList.remove('light-theme')
  }

  watch(currentProject, (newVal) => {
    sessionStorage.setItem('active_project', newVal)
    if (rememberProject.value) {
      localStorage.setItem('last_project', newVal)
    }
  })

  // Written straight into the profile the sidebar and top bar already render,
  // so a new photo appears everywhere the moment it is saved. Re-fetching the
  // whole profile would work too, but it would blank the avatar for a beat while
  // the request is in flight.
  const setUserImage = (url) => {
    user.value = { ...user.value, user_image: url || null }
  }

  const fetchUserProfile = async () => {
    loading.value = true
    try {
      const response = await axios.get('/api/method/elab_notebook.elab_notebook.api.user.get_current_user_profile')
      if (response.data && response.data.message) {
        user.value = response.data.message
      }
    } catch (err) {
      console.error('Failed to fetch user profile:', err)
      error.value = err
    } finally {
      loading.value = false
    }
  }

  const fetchEmployeeScope = async () => {
    try {
      const response = await axios.get('/api/method/elab_notebook.elab_notebook.api.user.get_employee_scope')
      if (response.data && response.data.message) {
        employeeScope.value = response.data.message
        
        // Reset currentProject to 'all' if the stored value is no longer valid or allowed
        const validProjects = employeeScope.value.projects.map(p => p.name)
        if (currentProject.value !== 'all' && !validProjects.includes(currentProject.value) && employeeScope.value.scope !== 'all') {
          currentProject.value = 'all'
          sessionStorage.setItem('active_project', 'all')
        }
      }
    } catch (err) {
      console.error('Failed to fetch employee scope:', err)
    }
  }

  const setProject = (proj) => {
    currentProject.value = proj
    sessionStorage.setItem('active_project', proj)
  }

  return {
    user,
    loading,
    error,
    currentProject,
    employeeScope,
    theme,
    setTheme,
    rememberProject,
    setRememberProject,
    setUserImage,
    createModalOpen,
    createModalProject,
    createModalProjectName,
    createModalEmployeeFunction,
    createModalTeam,
    openCreateExperimentModal,
    closeCreateExperimentModal,
    fetchUserProfile,
    fetchEmployeeScope,
    setProject
  }
})
