<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { useUserStore } from '../../stores/user'
import EntityStatsBlock from './EntityStatsBlock.vue'
import './Dashboard.css'

const userStore = useUserStore()
const templatesData = ref([])
const teamsData = ref([])
const loading = ref(true)

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
      <div class="page-header-right">
        <p class="page-subtitle">Unified research statistics</p>
      </div>
    </div>

    <!-- Restructured Entity Blocks -->
    <div class="dashboard-blocks-container">
      <EntityStatsBlock 
        entityName="Experiment Templates" 
        doctype="Experiment Template" 
        statusField="status" 
      />
      
      <EntityStatsBlock 
        entityName="Team" 
        doctype="Experiment Team" 
        statusField="docstatus" 
      />
      
      <EntityStatsBlock 
        entityName="Experiments" 
        doctype="Experiment" 
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
          <div v-for="t in templatesData" :key="t.template" class="analytics-row">
            <div class="analytics-info">
              <span class="analytics-name">{{ t.template_name }}</span>
              <span class="analytics-id">{{ t.template }}</span>
            </div>
            <span class="analytics-count">{{ t.count }} Run{{ t.count === 1 ? '' : 's' }}</span>
          </div>
        </div>
      </div>

      <!-- Teams Usage -->
      <div class="card analytics-card">
        <div class="analytics-head">
          <h2 class="card-title">Teams Activity</h2>
          <span class="analytics-sub">Runs per Team</span>
        </div>
        <div class="analytics-list">
          <div v-if="loading" class="analytics-placeholder">Loading&hellip;</div>
          <div v-else-if="!teamsData.length" class="analytics-placeholder">No teams created yet.</div>
          <div v-for="t in teamsData" :key="t.team" class="analytics-row">
            <div class="analytics-info">
              <span class="analytics-name">{{ t.team_name }}</span>
              <span class="analytics-id">{{ t.team }} · {{ t.project }}</span>
            </div>
            <span class="analytics-count">{{ t.count }} Run{{ t.count === 1 ? '' : 's' }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
