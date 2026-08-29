<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { useUserStore } from '../../stores/user'
import { formatDate } from '../../utils/dateFormatter'
import EntityStatsBlock from './EntityStatsBlock.vue'
import './Dashboard.css'

const userStore = useUserStore()
const templatesData = ref([])
const teamsData = ref([])
const loading = ref(true)

// Pagination state
const templatesCurrentPage = ref(0)
const teamsCurrentPage = ref(0)
const itemsPerPage = 5

// Computed properties for pagination
const templatesPageCount = computed(() => Math.ceil(templatesData.value.length / itemsPerPage))
const teamsPageCount = computed(() => Math.ceil(teamsData.value.length / itemsPerPage))

const paginatedTemplates = computed(() => {
  const start = templatesCurrentPage.value * itemsPerPage
  const end = start + itemsPerPage
  return templatesData.value.slice(start, end)
})

const paginatedTeams = computed(() => {
  const start = teamsCurrentPage.value * itemsPerPage
  const end = start + itemsPerPage
  return teamsData.value.slice(start, end)
})

// Pagination handlers
const nextTemplatesPage = () => {
  if (templatesCurrentPage.value < templatesPageCount.value - 1) {
    templatesCurrentPage.value++
  }
}

const prevTemplatesPage = () => {
  if (templatesCurrentPage.value > 0) {
    templatesCurrentPage.value--
  }
}

const nextTeamsPage = () => {
  if (teamsCurrentPage.value < teamsPageCount.value - 1) {
    teamsCurrentPage.value++
  }
}

const prevTeamsPage = () => {
  if (teamsCurrentPage.value > 0) {
    teamsCurrentPage.value--
  }
}

const fetchAnalytics = async () => {
  loading.value = true
  try {
    const [resTemplates, resTeams] = await Promise.all([
      axios.get('/api/method/elab_notebook.elab_notebook.api.dashboard.get_template_experiment_counts'),
      axios.get('/api/method/elab_notebook.elab_notebook.api.dashboard.get_team_experiment_counts')
    ])
    templatesData.value = resTemplates.data.message || []
    teamsData.value = resTeams.data.message || []
  } catch (err) {
    console.error('Failed to fetch dashboard analytics', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchAnalytics()
})
</script>

<template>
  <div class="dashboard-scrollable-content">
    <!-- Page Header -->
    <div class="page-header dashboard-hero">
      <div class="page-header-bg-icon">
        <svg class="header-lab-motif" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
          <path d="M6 18h8M3 22h14M12 18a6 6 0 0 0-6-6h2v-2a4 4 0 0 1 8 0v8M9 3h4M11 3v3M10 6h2M7 10h4v2H7z" />
        </svg>
      </div>
      <div class="page-header-left">
        <!-- Breadcrumbs -->
        <nav class="breadcrumb-nav">
          <span class="breadcrumb-link">Home</span>
          <span class="breadcrumb-separator">&gt;</span>
          <span class="breadcrumb-current">Laboratory Dashboard</span>
        </nav>
        <h1 class="page-title">Good morning, {{ userStore.user.first_name || 'Scientist' }}</h1>
      </div>
    </div>

    <!-- Restructured Entity Blocks -->
    <div class="dashboard-blocks-container">
      <EntityStatsBlock 
        entityName="Experiment Templates" 
        doctype="Lab Experiment Template" 
        statusField="status" 
      />
      
      <!-- `status`, not `docstatus`: Experiment Team is not submittable, so the
           docstatus buckets read Draft / Submitted / Cancelled with every team
           filed under Draft forever. Active / Archived is the distinction this
           doctype actually has. get_entity_stats reads the buckets off the
           Select field's own options, so there is nothing to configure here
           beyond the field name. -->
      <EntityStatsBlock
        entityName="Team"
        doctype="Experiment Team"
        statusField="status"
      />
      
      <EntityStatsBlock 
        entityName="Experiments" 
        doctype="Lab Experiment" 
        statusField="workflow_state" 
      />
      
      <EntityStatsBlock 
        entityName="Instruments" 
        doctype="Workstation" 
        statusField="status" 
      />
    </div>

    <!-- Detailed Analytics Strip -->
    <div class="dashboard-details-grid">
      <!-- Templates Usage -->
      <div class="card analytics-card">
        <div class="analytics-head">
          <h2 class="card-title">Templates Usage</h2>
          <span class="analytics-sub">Runs per Template</span>
        </div>
        <div class="analytics-list">
          <div v-if="loading" class="analytics-placeholder">Loading&hellip;</div>
          <div v-else-if="!templatesData.length" class="analytics-placeholder">No template runs recorded.</div>
          <div v-for="t in paginatedTemplates" :key="t.template" class="analytics-row">
            <div class="analytics-info">
              <span class="analytics-name">{{ t.template_name }}</span>
              <span class="analytics-id">{{ t.template }}</span>
            </div>
            <span class="analytics-count">{{ t.count }} Run{{ t.count === 1 ? '' : 's' }}</span>
          </div>
        </div>
        <div v-if="templatesPageCount > 1" class="pagination-controls">
          <button
            class="pagination-btn"
            @click="prevTemplatesPage"
            :disabled="templatesCurrentPage === 0"
            title="Previous page"
          >
            ← Prev
          </button>
          <span class="pagination-info">{{ templatesCurrentPage + 1 }} / {{ templatesPageCount }}</span>
          <button
            class="pagination-btn"
            @click="nextTemplatesPage"
            :disabled="templatesCurrentPage === templatesPageCount - 1"
            title="Next page"
          >
            Next →
          </button>
        </div>
      </div>

      <!-- Teams Activity -->
      <div class="card analytics-card">
        <div class="analytics-head">
          <h2 class="card-title">Teams Activity</h2>
          <span class="analytics-sub">Runs per Team</span>
        </div>
        <div class="analytics-list">
          <div v-if="loading" class="analytics-placeholder">Loading&hellip;</div>
          <div v-else-if="!teamsData.length" class="analytics-placeholder">No teams created yet.</div>
          <div v-for="t in paginatedTeams" :key="t.team" class="analytics-row">
            <div class="analytics-info">
              <span class="analytics-name">{{ t.team_name }}</span>
              <span class="analytics-id">{{ t.team }} · {{ t.project }}</span>
            </div>
            <span class="analytics-count">{{ t.count }} Run{{ t.count === 1 ? '' : 's' }}</span>
          </div>
        </div>
        <div v-if="teamsPageCount > 1" class="pagination-controls">
          <button
            class="pagination-btn"
            @click="prevTeamsPage"
            :disabled="teamsCurrentPage === 0"
            title="Previous page"
          >
            ← Prev
          </button>
          <span class="pagination-info">{{ teamsCurrentPage + 1 }} / {{ teamsPageCount }}</span>
          <button
            class="pagination-btn"
            @click="nextTeamsPage"
            :disabled="teamsCurrentPage === teamsPageCount - 1"
            title="Next page"
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
