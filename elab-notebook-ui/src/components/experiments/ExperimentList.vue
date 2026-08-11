<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useUserStore } from '../../stores/user'
import { formatDate } from '../../utils/dateFormatter'
import './ExperimentList.css'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(true)
const experiments = ref([])
const statusFilter = ref('')

const currentPage = ref(1)
const pageSize = 10

const totalPages = computed(() => Math.ceil(experiments.value.length / pageSize))

const paginatedExperiments = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  const end = start + pageSize
  return experiments.value.slice(start, end)
})

const fetchExperiments = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.dashboard.get_experiments_list', {
      params: {
        project: userStore.currentProject,
        workflow_state: statusFilter.value || undefined
      }
    })
    experiments.value = res.data.message || []
    currentPage.value = 1
  } catch (err) {
    console.error('Failed to load experiments list:', err)
  } finally {
    loading.value = false
  }
}

const navigateToDetail = (id) => {
  router.push(`/experiments/${encodeURIComponent(id)}`)
}

// Watchers
watch(() => userStore.currentProject, () => {
  currentPage.value = 1
  fetchExperiments()
})

watch(statusFilter, () => {
  currentPage.value = 1
  fetchExperiments()
})

const getWorkflowStateClass = (state) => {
  if (!state) return 'status-draft'
  const s = state.toLowerCase()
  if (s.includes('approved')) return 'status-approved'
  if (s.includes('rejected')) return 'status-rejected'
  if (s.includes('pending')) return 'status-pending'
  return 'status-draft'
}

const getExperimentStatusClass = (status) => {
  if (!status) return 'status-draft'
  const s = status.toLowerCase()
  if (s.includes('completed')) return 'status-approved'
  if (s.includes('failed')) return 'status-rejected'
  return 'status-pending'
}

onMounted(() => {
  fetchExperiments()
})
</script>

<template>
  <div class="experiment-list-container">
    <!-- Header -->
    <div class="page-header">
      <div class="page-header-left">
        <nav class="breadcrumb-nav">
          <router-link to="/" class="breadcrumb-link">Home</router-link>
          <span class="breadcrumb-separator">&gt;</span>
          <span class="breadcrumb-current">Experiments</span>
        </nav>
        <h1 class="page-title">Experiment Runs</h1>
        <p class="page-subtitle">Track, execute, and sign off ongoing laboratory runs</p>
      </div>

      <div class="page-header-right">
        <button class="btn btn-primary" @click="userStore.openCreateExperimentModal()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="btn-icon-svg"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          New Experiment
        </button>
      </div>
    </div>

    <!-- Filters Row -->
    <div class="filters-row card">
      <div class="filter-group">
        <label class="filter-label">Project Scope:</label>
        <span class="active-scope-pill">{{ userStore.currentProject === 'all' ? 'All Allowed Projects' : userStore.currentProject }}</span>
      </div>

      <div class="filter-group">
        <label class="filter-label">Filter Status:</label>
        <select v-model="statusFilter" class="filter-select">
          <option value="">All Statuses</option>
          <option value="Draft">Draft</option>
          <option value="Running">Running</option>
          <option value="Active">Active</option>
          <option value="Completed">Completed</option>
          <option value="Pending Approval">Pending Approval</option>
          <option value="In Review">In Review</option>
          <option value="Approved">Approved</option>
        </select>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Fetching experiment run logs...</p>
    </div>

    <!-- Data Table / Empty State -->
    <div v-else class="list-layout card">
      <div class="table-container" v-if="experiments.length > 0">
        <table>
          <thead>
            <tr>
              <th>Run ID</th>
              <th>Title / Aim</th>
              <th>Project</th>
              <th>Lead Scientist</th>
              <th>Status</th>
              <th>Start Date</th>
            </tr>
          </thead>
          <tbody>
            <tr 
              v-for="exp in paginatedExperiments" 
              :key="exp.name" 
              class="clickable-row"
              @click="navigateToDetail(exp.name)"
            >
              <td class="font-mono text-accent"><strong>{{ exp.name }}</strong></td>
              <td>
                <div class="exp-title-cell">{{ exp.title }}</div>
                <div class="exp-aim-cell" v-if="exp.aim">{{ exp.aim }}</div>
              </td>
              <td>{{ exp.project }}</td>
              <td>{{ exp.employee_name }}</td>
              <td>
                <span 
                  class="status-pill"
                  :class="getWorkflowStateClass(exp.workflow_state)"
                >
                  {{ exp.workflow_state || 'Draft' }}
                </span>
                <span 
                  v-if="exp.experiment_status"
                  class="status-pill"
                  :class="getExperimentStatusClass(exp.experiment_status)"
                  style="margin-left: 0.5rem;"
                >
                  {{ exp.experiment_status }}
                </span>
              </td>
              <td class="text-muted">{{ formatDate(exp.experiment_start_date) }}</td>
            </tr>
          </tbody>
        </table>

        <!-- Pagination Controls -->
        <div v-if="totalPages > 1" class="pagination-controls" style="display: flex; align-items: center; justify-content: center; gap: 1rem; margin-top: 1.5rem; padding-bottom: 0.5rem;">
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

      <div v-else class="empty-state">
        <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="9" y1="15" x2="15" y2="15" />
          <line x1="9" y1="11" x2="15" y2="11" />
        </svg>
        <h3>No experiments found</h3>
        <p>No experiment runs match the selected project or status filters.</p>
        <button class="btn btn-secondary mt-3" @click="userStore.openCreateExperimentModal()">
          Create Your First Run
        </button>
      </div>
    </div>
  </div>
</template>
