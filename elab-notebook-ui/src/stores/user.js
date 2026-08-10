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
    role: 'Guest'
  })
  
  const loading = ref(true)
  const error = ref(null)

  const currentProject = ref(sessionStorage.getItem('active_project') || 'all')
  const employeeScope = ref({ function_names: [], scope: 'all', projects: [] })

  const theme = ref(localStorage.getItem('theme') || 'dark')

  const createModalOpen = ref(false)
  const createModalProject = ref('')
  const createModalProjectName = ref('')
  const createModalEmployeeFunction = ref('')

  const openCreateExperimentModal = (proj = '', empFunc = '', projName = '') => {
    createModalProject.value = proj
    createModalEmployeeFunction.value = empFunc
    createModalProjectName.value = projName
    createModalOpen.value = true
  }

  const closeCreateExperimentModal = () => {
    createModalOpen.value = false
    createModalProject.value = ''
    createModalEmployeeFunction.value = ''
    createModalProjectName.value = ''
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
  })

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
    createModalOpen,
    createModalProject,
    createModalProjectName,
    createModalEmployeeFunction,
    openCreateExperimentModal,
    closeCreateExperimentModal,
    fetchUserProfile,
    fetchEmployeeScope,
    setProject
  }
})
