<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { formatDateTime } from '../../utils/dateFormatter'
import PageHeader from '../layout/PageHeader.vue'
import './TemplatesList.css'

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
// Sized for the taller rows: roughly a screenful, so the table paginates rather
// than running off the bottom of the page.
const pageSize = 7

const totalPages = computed(() => Math.max(Math.ceil(templates.value.length / pageSize), 1))

const paginatedTemplates = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  const end = start + pageSize
  return templates.value.slice(start, end)
})

// Deleting the last row of the final page would otherwise strand the view on a
// page that no longer exists.
watch(totalPages, (pages) => {
  if (currentPage.value > pages) currentPage.value = pages
})

// Deliberately not filtered by the Active Project selector: once a template is saved
// it must be findable here, and project-scoping this list silently hid drafts that
// belonged to a project other than the one selected in the top bar. Function-level
// scoping is still enforced server-side, so this only ever widens to the user's own
// Employee Function - never across functions.
const fetchTemplates = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.template.get_experiment_templates')
    templates.value = res.data.message || []
    currentPage.value = 1
    await fetchTemplateCounts()
  } catch (err) {
    console.error('Failed to fetch templates', err)
  } finally {
    loading.value = false
  }
}

// Mirrors isReadOnly in TemplateDetail.vue: once a template is sent for approval it
// stops being the author's to change, so the row offers View (which reviewers use to
// open it and run Approve/Reject) instead of Edit. Draft and Rejected stay editable.
const READ_ONLY_STATES = ['Pending from System Manager', 'Pending For Approval', 'Approved']

const isEditable = (state) => !READ_ONLY_STATES.includes(state)

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
    <PageHeader
      :breadcrumbs="[{ label: 'Home', href: '/' }, { label: 'Experiment Templates' }]"
      title="Experiment Templates"
      subtitle="Standardized procedures and default parameters for repeatable runs."
      :action="{ label: 'Add Template', onClick: () => router.push('/templates/new') }"
    />

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

    <!-- Table Grid. Same frame as the "Your Teams" card on /elab-notebook:
         .meta-card + a .table-actions header, then the table, then pagination. -->
    <section v-else class="meta-card">
      <div class="table-actions">
        <div>
          <h3 class="section-title no-margin">All Templates</h3>
          <p class="section-sub">Drafts you own, plus every template approved for your function.</p>
        </div>
        <span class="selected-pill">{{ templates.length }} total</span>
      </div>

      <div class="table-container">
      <table class="list-table templates-table">
        <thead>
          <tr>
            <th>Template ID</th>
            <th>Template Name</th>
            <th>Status</th>
            <th>Experiments</th>
            <th>Last Updated</th>
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
            <td class="actions-col">
              <div class="actions-group">
                <!-- Edit - only while the template is still the author's (Draft/Rejected) -->
                <router-link
                  v-if="isEditable(temp.workflow_state)"
                  :to="`/templates/${temp.name}`"
                  class="action-btn text-accent"
                  title="Edit Template"
                  @click.stop
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="action-icon"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                  Edit
                </router-link>

                <!-- View - once sent for approval the template is locked, but reviewers
                     still need to open it to approve or reject -->
                <router-link
                  v-else
                  :to="`/templates/${temp.name}`"
                  class="action-btn text-muted"
                  title="View Template (locked - awaiting approval or already approved)"
                  @click.stop
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="action-icon"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                  View
                </router-link>
              </div>
            </td>
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
  </div>
</template>
