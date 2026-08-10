<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useUserStore } from '../../stores/user'
import './CreateExperimentModal.css'

const userStore = useUserStore()
const router = useRouter()

const projects = ref([])
const employeeFunctions = ref([])
const templates = ref([])

const selectedProject = ref('')
const selectedEmployeeFunction = ref('')
const selectedTemplate = ref(null)

const templateSearch = ref('')
const showDropdown = ref(false)

// Determine if context is pre-filled from team page
const isContextPrefilled = computed(() => {
  return !!userStore.createModalProject && !!userStore.createModalEmployeeFunction
})

// Current project to use
const currentProject = computed(() => {
  return isContextPrefilled.value ? userStore.createModalProject : selectedProject.value
})

const currentEmployeeFunction = computed(() => {
  return isContextPrefilled.value ? userStore.createModalEmployeeFunction : selectedEmployeeFunction.value
})

// Load projects (only if not pre-filled)
const loadProjects = async () => {
  if (isContextPrefilled.value) return
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.experiment_team.get_authorized_projects_for_user')
    projects.value = res.data.message || []
  } catch (err) {
    console.error('Failed to load authorized projects:', err)
  }
}

// Load employee functions when project changes
watch(selectedProject, async (newProj) => {
  if (isContextPrefilled.value || !newProj) {
    employeeFunctions.value = []
    selectedEmployeeFunction.value = ''
    return
  }
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.experiment_team.get_authorized_functions_for_project', {
      params: { project: newProj }
    })
    employeeFunctions.value = res.data.message || []
    if (employeeFunctions.value.length > 0) {
      selectedEmployeeFunction.value = employeeFunctions.value[0]
    } else {
      selectedEmployeeFunction.value = ''
    }
  } catch (err) {
    console.error('Failed to load functions for project:', err)
  }
})

// Load active templates
const loadTemplates = async () => {
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.template.get_experiment_templates', {
      params: {
        filters: JSON.stringify({ status: ['!=', 'Archived'] })
      }
    })
    templates.value = res.data.message || []
    console.log(`Loaded ${templates.value.length} active templates`, templates.value)
  } catch (err) {
    console.error('Failed to load active templates:', err)
    templates.value = []
  }
}

// Filter templates based on selected project, employee function, and search query
const filteredTemplates = computed(() => {
  const proj = currentProject.value
  const func = currentEmployeeFunction.value

  let filtered = templates.value.filter(t => {
    // If template has employee_function, it must match selected employee function
    if (func && t.employee_function && t.employee_function !== func) return false

    // If template is project-scoped, it must match selected project
    if (t.project && t.project !== proj) return false

    // Search filter
    if (templateSearch.value && selectedTemplate.value?.name !== t.name) {
      const q = templateSearch.value.toLowerCase()
      const name = (t.template_name || t.title || t.name).toLowerCase()
      return name.includes(q)
    }
    return true
  })

  console.log(`Filtered templates for project="${proj}" func="${func}" search="${templateSearch.value}":`, filtered)
  return filtered
})

const selectTemplate = (temp) => {
  console.log('Selected template:', temp)
  selectedTemplate.value = temp
  templateSearch.value = temp.template_name || temp.title || temp.name
  showDropdown.value = false
}

const clearTemplate = () => {
  console.log('Cleared template')
  selectedTemplate.value = null
  templateSearch.value = ''
}

// Watch dropdown state for debugging
watch(() => showDropdown.value, (isOpen) => {
  console.log(`Dropdown ${isOpen ? 'opened' : 'closed'}. filteredTemplates count: ${filteredTemplates.value.length}, currentProject: ${currentProject.value}`)
})

// Debug currentProject changes
watch(() => currentProject.value, (proj) => {
  console.log(`currentProject changed to: ${proj}. Total templates available: ${templates.value.length}. Filtered: ${filteredTemplates.value.length}`)
})

// Debug template loading
watch(() => templates.value, (tmpl) => {
  console.log(`templates.value updated. Count: ${tmpl.length}. Details:`, tmpl)
}, { deep: false })

const handleProceed = () => {
  if (!currentProject.value || !currentEmployeeFunction.value || !selectedTemplate.value) {
    return
  }
  
  const queryParams = new URLSearchParams({
    project: currentProject.value,
    employee_function: currentEmployeeFunction.value,
    template: selectedTemplate.value.name
  }).toString()
  
  // Close modal
  userStore.closeCreateExperimentModal()
  
  // Navigate to new experiment form route
  router.push(`/experiments/new?${queryParams}`)
}

const handleCancel = () => {
  userStore.closeCreateExperimentModal()
}

// Reset selections when modal is opened/closed
watch(() => userStore.createModalOpen, (isOpen) => {
  if (isOpen) {
    console.log('CreateExperimentModal opened')
    selectedProject.value = ''
    selectedEmployeeFunction.value = ''
    selectedTemplate.value = null
    templateSearch.value = ''
    loadProjects()
    loadTemplates()
  }
})
</script>

<template>
  <div v-if="userStore.createModalOpen" class="modal-overlay" @click.self="handleCancel">
    <div class="modal-content card">
      <div class="modal-header">
        <h3 class="modal-title">New Experiment Setup</h3>
        <button class="modal-close" @click="handleCancel">×</button>
      </div>

      <div class="modal-body">
        <!-- 1. Project Selector (Direct Sidebar Access Only) -->
        <div v-if="!isContextPrefilled" class="form-group">
          <label class="form-label">Project *</label>
          <select v-model="selectedProject" class="form-control select-input">
            <option value="">Select an Authorized Project...</option>
            <option v-for="proj in projects" :key="proj.name" :value="proj.name">
              {{ proj.project_name || proj.name }}
            </option>
          </select>
        </div>

        <!-- 2. Employee Function Selector (Direct Sidebar Access Only) -->
        <div v-if="!isContextPrefilled" class="form-group">
          <label class="form-label">Employee Function *</label>
          <select v-model="selectedEmployeeFunction" class="form-control select-input" :disabled="!selectedProject">
            <option value="">Select a Function...</option>
            <option v-for="func in employeeFunctions" :key="func" :value="func">
              {{ func }}
            </option>
          </select>
        </div>

        <!-- 3. Pre-filled Metadata Info (Team Access Flow) -->
        <div v-else class="context-pill-info">
          <div class="info-item">
            <span class="info-label">Project:</span>
            <span class="info-value">{{ userStore.createModalProjectName || userStore.createModalProject }}</span>
          </div>
        </div>

        <!-- 4. Template Selector (Searchable Dropdown) -->
        <div class="form-group relative">
          <label class="form-label">Experiment Template *</label>
          <div class="template-search-wrapper">
            <input
              type="text"
              v-model="templateSearch"
              class="form-control search-input"
              placeholder="Type to search active templates..."
              @focus="showDropdown = true"
              :disabled="!currentProject"
            />
            <button 
              v-if="selectedTemplate" 
              class="clear-btn" 
              @click="clearTemplate"
            >
              ×
            </button>
          </div>

          <!-- Dropdown options -->
          <div v-if="showDropdown && filteredTemplates.length > 0" class="dropdown-list">
            <div
              v-for="temp in filteredTemplates"
              :key="temp.name"
              class="dropdown-item"
              @click="selectTemplate(temp)"
            >
              <div class="item-title">{{ temp.template_name || temp.title || temp.name }}</div>
              <div class="item-meta">Version: {{ temp.version || '1.0' }} | {{ temp.category || 'Standard' }}</div>
            </div>
          </div>
          <div v-else-if="showDropdown && currentProject" class="dropdown-list empty-dropdown">
            No matching active templates found for this project scope.
          </div>
        </div>

        <!-- Template Details Card (shown when template is selected) -->
        <div v-if="selectedTemplate" class="template-details-card">
          <div class="details-header">
            <h4 class="details-title">{{ selectedTemplate.template_name || selectedTemplate.title || selectedTemplate.name }}</h4>
          </div>
          <div class="details-grid">
            <div class="detail-item">
              <span class="detail-label">Estimated Duration:</span>
              <span class="detail-value">
                <span v-if="selectedTemplate.total_duration">
                  {{ selectedTemplate.total_duration }} minutes
                </span>
                <span v-else class="detail-value-muted">
                  Not specified
                </span>
              </span>
            </div>
            <div v-if="selectedTemplate.category" class="detail-item">
              <span class="detail-label">Category:</span>
              <span class="detail-value">{{ selectedTemplate.category }}</span>
            </div>
            <div v-if="selectedTemplate.version" class="detail-item">
              <span class="detail-label">Version:</span>
              <span class="detail-value">{{ selectedTemplate.version }}</span>
            </div>
            <div v-if="selectedTemplate.description" class="detail-item full-width">
              <span class="detail-label">Description:</span>
              <span class="detail-value">{{ selectedTemplate.description }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="modal-footer">
        <button class="btn btn-secondary" @click="handleCancel">Cancel</button>
        <button
          class="btn btn-primary"
          :disabled="!currentProject || !currentEmployeeFunction || !selectedTemplate"
          @click="handleProceed"
        >
          OK
        </button>
      </div>
    </div>
  </div>
</template>
