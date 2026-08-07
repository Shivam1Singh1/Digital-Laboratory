<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useUserStore } from '../../stores/user'
import './TemplatesList.css'

const userStore = useUserStore()
const router = useRouter()
const templates = ref([])
const loading = ref(true)

// Modal states
const showUseModal = ref(false)
const selectedTemplate = ref(null)
const experimentName = ref('')
const leadScientist = ref('')
const startDate = ref(new Date().toISOString().substr(0, 10))
const creatingRun = ref(false)

const fetchTemplates = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.template.get_experiment_templates')
    templates.value = res.data.message || []
  } catch (err) {
    console.error('Failed to fetch templates', err)
  } finally {
    loading.value = false
  }
}

const openUseModal = (temp) => {
  selectedTemplate.value = temp
  experimentName.value = `Run: ${temp.template_name}`
  leadScientist.value = userStore.user.email || userStore.user.name
  startDate.value = new Date().toISOString().substr(0, 10)
  showUseModal.value = true
}

const closeUseModal = () => {
  showUseModal.value = false
  selectedTemplate.value = null
}

const createRun = async () => {
  if (!experimentName.value.trim()) {
    alert('Please enter an experiment run name')
    return
  }
  
  creatingRun.value = true
  try {
    const res = await axios.post('/api/method/elab_notebook.elab_notebook.api.template.create_experiment_from_template', {
      template_name: selectedTemplate.value.name,
      overrides: {
        experiment_name: experimentName.value,
        lead_scientist: leadScientist.value,
        experiment_start_date: startDate.value
      }
    })
    
    const newExpId = res.data.message
    alert(`Successfully created experiment run: ${newExpId}!`)
    closeUseModal()
    fetchTemplates() // Refresh counts
  } catch (err) {
    console.error('Failed to create experiment run', err)
    alert('Failed to create run: ' + (err.response?.data?.message || err.message))
  } finally {
    creatingRun.value = false
  }
}

const formatDateTime = (val) => {
  if (!val) return ''
  const d = new Date(val)
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

onMounted(() => {
  fetchTemplates()
})
</script>

<template>
  <div class="templates-list-container">
    <div class="page-header">
      <div class="page-header-left">
        <nav class="breadcrumb-nav">
          <router-link to="/" class="breadcrumb-link">Home</router-link>
          <span class="breadcrumb-separator">&gt;</span>
          <span class="breadcrumb-current">Experiment Templates</span>
        </nav>
        <h1 class="page-title">Experiment Templates</h1>
        <p class="page-subtitle">Standardized procedures and default parameters for repeatable runs.</p>
      </div>

      <div class="page-header-right">
        <router-link to="/templates/new" class="btn btn-primary">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="btn-icon-svg"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Add Template
        </router-link>
      </div>
    </div>

    <!-- Loading Indicator -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading templates...</p>
    </div>

    <!-- Empty State -->
    <div v-else-if="templates.length === 0" class="empty-state">
      <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="12" y1="18" x2="12" y2="12" />
        <line x1="9" y1="15" x2="15" y2="15" />
      </svg>
      <h3>No templates found</h3>
      <p>Get started by creating your first reusable experiment template.</p>
      <router-link to="/templates/new" class="btn btn-primary mt-4">Create Template</router-link>
    </div>

    <!-- Table Grid -->
    <div v-else class="table-card">
      <table class="templates-table">
        <thead>
          <tr>
            <th>Template Name</th>
            <th>Category</th>
            <th>Version</th>
            <th>Status</th>
            <th>Last Updated</th>
            <th>Times Used</th>
            <th class="actions-col">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="temp in templates" :key="temp.name">
            <td>
              <div class="template-info">
                <span class="template-main-name">{{ temp.template_name }}</span>
                <span class="template-id">{{ temp.name }}</span>
              </div>
            </td>
            <td>
              <span class="category-tag">{{ temp.category || 'Unassigned' }}</span>
            </td>
            <td>v{{ temp.version || '1.0' }}</td>
            <td>
              <span class="status-badge" :class="temp.status?.toLowerCase() || 'draft'">
                {{ temp.status || 'Draft' }}
              </span>
            </td>
            <td>{{ formatDateTime(temp.modified) }}</td>
            <td class="count-col">
              <span class="use-count">{{ temp.times_used || 0 }}</span>
            </td>
            <td class="actions-col">
              <div class="actions-group">
                <button class="action-btn text-accent" @click="openUseModal(temp)" title="Use Template to start an experiment run">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="action-icon"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                  Use
                </button>
                <router-link :to="`/templates/${temp.name}`" class="action-btn text-muted" title="Edit Template">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="action-icon"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                  Edit
                </router-link>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Use Template Modal -->
    <div v-if="showUseModal" class="modal-overlay">
      <div class="modal-card">
        <div class="modal-header">
          <h3>Create Run from Template</h3>
          <button class="modal-close-btn" @click="closeUseModal">×</button>
        </div>
        
        <div class="modal-body">
          <div class="modal-template-summary">
            <span class="summary-label">Template:</span>
            <strong class="summary-value">{{ selectedTemplate?.template_name }}</strong>
            <span class="summary-version">(v{{ selectedTemplate?.version || '1.0' }})</span>
          </div>

          <div class="form-group">
            <label class="form-label">Experiment Run Name *</label>
            <input type="text" v-model="experimentName" class="form-control" placeholder="e.g. CRISPR cas9 run 1" />
          </div>

          <div class="form-row">
            <div class="form-group col">
              <label class="form-label">Lead Scientist</label>
              <input type="text" v-model="leadScientist" class="form-control" readonly />
            </div>
            
            <div class="form-group col">
              <label class="form-label">Start Date</label>
              <input type="date" v-model="startDate" class="form-control" />
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn btn-secondary" @click="closeUseModal">Cancel</button>
          <button class="btn btn-primary" @click="createRun" :disabled="creatingRun">
            <span v-if="creatingRun" class="spinner btn-spinner"></span>
            {{ creatingRun ? 'Creating Run...' : 'Create Experiment Run' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>


