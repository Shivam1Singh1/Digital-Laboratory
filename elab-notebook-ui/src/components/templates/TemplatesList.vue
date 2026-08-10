<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useUserStore } from '../../stores/user'
import './TemplatesList.css'

const userStore = useUserStore()
const router = useRouter()
const templates = ref([])
const loading = ref(true)


const templateCounts = ref({})

const fetchTemplateCounts = async () => {
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.dashboard.get_template_experiment_counts')
    const counts = res.data.message || []
    const map = {}
    for (const item of counts) {
      map[item.template] = item.count
    }
    templateCounts.value = map
  } catch (err) {
    console.error('Failed to fetch template counts', err)
  }
}

const getExperimentCount = (name) => {
  return templateCounts.value[name] || 0
}

const currentPage = ref(1)
const pageSize = 10

const totalPages = computed(() => Math.ceil(templates.value.length / pageSize))

const paginatedTemplates = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  const end = start + pageSize
  return templates.value.slice(start, end)
})

const fetchTemplates = async () => {
  loading.value = true
  try {
    const params = {}
    if (userStore.currentProject && userStore.currentProject !== 'all') {
      params.filters = JSON.stringify({ project: userStore.currentProject })
    }
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.template.get_experiment_templates', { params })
    templates.value = res.data.message || []
    currentPage.value = 1
    await fetchTemplateCounts()
  } catch (err) {
    console.error('Failed to fetch templates', err)
  } finally {
    loading.value = false
  }
}

watch(() => userStore.currentProject, () => {
  currentPage.value = 1
  fetchTemplates()
})


const formatDateTime = (val) => {
  if (!val) return ''
  const d = new Date(val)
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const getWorkflowStateClass = (state) => {
  if (!state) return 'state-draft'
  const s = state.toLowerCase()
  if (s.includes('approved')) return 'state-approved'
  if (s.includes('rejected')) return 'state-rejected'
  if (s.includes('pending')) return 'state-pending'
  return 'state-draft'
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
            <th>Template ID</th>
            <th>Template Name</th>
            <th>Status</th>
            <th>Experiments</th>
            <th>Last Updated</th>
            <th>Times Used</th>
            <th class="actions-col">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="temp in paginatedTemplates" :key="temp.name" class="clickable-row" @click="router.push(`/templates/${temp.name}`)">
            <td class="font-mono text-accent"><strong>{{ temp.name }}</strong></td>
            <td>{{ temp.template_name }}</td>
            <td>
              <span class="workflow-state-badge" :class="getWorkflowStateClass(temp.workflow_state)">
                {{ temp.workflow_state || 'Draft' }}
              </span>
            </td>
            <td class="count-col">
              <span class="experiment-count">{{ getExperimentCount(temp.name) }}</span>
            </td>
            <td>{{ formatDateTime(temp.modified) }}</td>
            <td class="count-col">
              <span class="use-count">{{ temp.times_used || 0 }}</span>
            </td>
            <td class="actions-col">
              <div class="actions-group">
                <!-- Edit button - only for Draft/Pending/Rejected templates -->
                <router-link
                  v-if="temp.workflow_state !== 'Approved'"
                  :to="`/templates/${temp.name}`"
                  class="action-btn text-accent"
                  title="Edit Template"
                  @click.stop
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="action-icon"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                  Edit
                </router-link>
              </div>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Pagination Controls -->
      <div v-if="totalPages > 1" class="pagination-controls" style="display: flex; align-items: center; justify-content: center; gap: 1rem; margin-top: 1.5rem; padding-bottom: 1rem;">
        <button 
          class="btn btn-secondary btn-sm" 
          :disabled="currentPage === 1" 
          @click="currentPage--"
        >
          Previous
        </button>
        <span class="pagination-info" style="font-size: 0.875rem; color: var(--text-muted); font-weight: 500;">
          Page {{ currentPage }} of {{ totalPages }}
        </span>
        <button 
          class="btn btn-secondary btn-sm" 
          :disabled="currentPage === totalPages" 
          @click="currentPage++"
        >
          Next
        </button>
      </div>
    </div>
  </div>
</template>
