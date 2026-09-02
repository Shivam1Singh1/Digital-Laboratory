<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useUserStore } from '../../stores/user'
import { formatDate } from '../../utils/dateFormatter'
import PageHeader from '../layout/PageHeader.vue'
import './ExperimentList.css'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(true)
const experiments = ref([])
const statusFilter = ref('')
const categoryFilter = ref('')

const currentPage = ref(1)
const pageSize = 7

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
        workflow_state: statusFilter.value || undefined,

        experiment_category: categoryFilter.value || undefined
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


const categoryOptions = ref([])

const loadCategoryOptions = async () => {
  try {
    const res = await axios.get(
      '/api/method/elab_notebook.elab_notebook.api.hierarchy.get_category_options'
    )
    categoryOptions.value = res.data.message || []
  } catch (err) {
    console.error('Failed to load experiment categories:', err)
    categoryOptions.value = []
  }
}


const startNewExperiment = () => {
  router.push('/experiments/new')
}


watch(() => userStore.currentProject, () => {
  currentPage.value = 1
  fetchExperiments()
})

watch([statusFilter, categoryFilter], () => {
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
  loadCategoryOptions()
})
</script>

<template>
  <div class="experiment-list-container">
    <!-- Header -->
    <!-- The action is the page header's, not a second button in the filter bar:
         Templates and Team Setup already put their create action there, and it
         is the one spot that stays put whether the table or the empty state is
         showing. -->
    <PageHeader
      :breadcrumbs="[{ label: 'Home', href: '/' }, { label: 'Experiments' }]"
      title="Experiment Runs"
      subtitle="Track, execute, and sign off ongoing laboratory runs"
      :action="{ label: 'New Experiment', onClick: startNewExperiment }"
    />

    <!-- Filters Row. No project scope here: the top bar's Active Project
         selector already sets it for the whole app. -->
    <div class="filters-row">
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

      <!-- The four levels, in hierarchy order, straight from the server. The
           first option is deliberately blank rather than labelled: it is the
           same empty leading choice the doctype's own experiment_category Select
           carries, and it means no filter at all. -->
      <div class="filter-group">
        <label class="filter-label">Experiment Type:</label>
        <select v-model="categoryFilter" class="filter-select">
          <option value=""></option>
          <option v-for="opt in categoryOptions" :key="opt.category" :value="opt.category">
            {{ opt.category }}
          </option>
        </select>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Fetching experiment run logs...</p>
    </div>

    <!-- Data Table / Empty State. Same frame as the "Your Teams" card on
         /elab-notebook: .meta-card + a .table-actions header. -->
    <section v-else-if="experiments.length > 0" class="meta-card">
      <div class="table-actions">
        <div>
          <h3 class="section-title no-margin">All Runs</h3>
          <p class="section-sub">Runs visible in the current project scope.</p>
        </div>
        <span class="selected-pill">{{ experiments.length }} total</span>
      </div>

      <div class="table-container">
        <table class="list-table">
          <thead>
            <tr>
              <th>Run ID</th>
              <th>Title / Aim</th>
              <th>Project</th>
              <th>Experiment Type</th>
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
              <!-- Older runs predate the four-level categories, so an em dash
                   rather than a blank cell: the level is unset, not missing. -->
              <td :class="{ 'text-muted': !exp.experiment_category }">
                {{ exp.experiment_category || '—' }}
              </td>
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
      </div>

      <!-- Pagination Controls -->
        <div v-if="totalPages > 1" class="pagination-controls" style="display: flex; align-items: center; justify-content: center; gap: 1rem; margin-top: 1.5rem; padding-bottom: 0.5rem;">
          <button
            class="btn btn-secondary btn-sm"
            :disabled="currentPage === 1"
            @click="currentPage--"
          >
            Previous
          </button>
          <span class="pagination-info" style="font-size: var(--fs-lg); color: var(--text-muted); font-weight: var(--fw-medium);">
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
    </section>

    <div v-else class="empty-state">
      <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="9" y1="15" x2="15" y2="15" />
        <line x1="9" y1="11" x2="15" y2="11" />
      </svg>
      <h3>No experiments found</h3>
      <p>No experiment runs match the selected project, status or experiment type filters.</p>
      <!-- The same entry point as the header action: one page, one way to start
           a run. -->
      <button class="btn btn-secondary mt-3" @click="startNewExperiment">
        Create Your First Run
      </button>
    </div>
  </div>
</template>
