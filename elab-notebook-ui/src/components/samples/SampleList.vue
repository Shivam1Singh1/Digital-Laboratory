<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useUserStore } from '../../stores/user'
import { formatDate } from '../../utils/dateFormatter'
import { readServerError } from '../../utils/serverError'
import PageHeader from '../layout/PageHeader.vue'
import './SampleList.css'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(true)
const error = ref('')
const samples = ref([])
const statusFilter = ref('')

const currentPage = ref(1)
const pageSize = 7


const totalPages = computed(() => Math.ceil(samples.value.length / pageSize) || 1)

const paginatedSamples = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return samples.value.slice(start, start + pageSize)
})

const fetchSamples = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await axios.get(
      '/api/method/elab_notebook.elab_notebook.api.sample.get_samples_list',
      {
        params: {
          project: userStore.currentProject,
          docstatus: statusFilter.value === '' ? undefined : statusFilter.value
        }
      }
    )
    samples.value = res.data.message || []
    currentPage.value = 1
  } catch (err) {
    console.error('Failed to load samples list:', err)
    error.value = readServerError(err, 'Could not load the samples list.')
    samples.value = []
  } finally {
    loading.value = false
  }
}

const openSample = (sample) => {
  router.push(`/samples/${encodeURIComponent(sample.name)}`)
}

const statusClass = (label) => {
  const s = (label || '').toLowerCase()
  if (s === 'submitted') return 'status-approved'
  if (s === 'cancelled') return 'status-rejected'
  return 'status-draft'
}

const runStateClass = (state) => {
  const s = (state || '').toLowerCase()
  if (s.includes('approved')) return 'status-approved'
  if (s.includes('rejected')) return 'status-rejected'
  if (s.includes('pending')) return 'status-pending'
  return 'status-draft'
}

watch(() => userStore.currentProject, fetchSamples)
watch(statusFilter, fetchSamples)

onMounted(fetchSamples)
</script>

<template>
  <div class="sample-list-container">
    <PageHeader
      :breadcrumbs="[{ label: 'Home', href: '/' }, { label: 'Samples' }]"
      title="Samples"
    />

    <div class="filters-row">
      <div class="filter-group">
        <label class="filter-label">Status:</label>
        <select v-model="statusFilter" class="filter-select">
          <option value="">All Statuses</option>
          <option value="0">Draft</option>
          <option value="1">Submitted</option>
          <option value="2">Cancelled</option>
        </select>
      </div>

    </div>

    <div v-if="error" class="sample-list-error">{{ error }}</div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Fetching registered samples...</p>
    </div>

    <!-- Same frame as the "Your Teams" card on /elab-notebook: .meta-card + a
         .table-actions header. -->
    <section v-else-if="samples.length > 0" class="meta-card">
      <div class="table-actions">
        <div>
          <h3 class="section-title no-margin">All Samples</h3>
        </div>
        <span class="selected-pill">{{ samples.length }} total</span>
      </div>

      <div class="table-container">
        <table class="list-table">
          <thead>
            <tr>
              <th>Sample ID</th>
              <th>Parent Run</th>
              <th>Item</th>
              <th>Name of Sample</th>
              <th>Qty</th>
              <th>Status</th>
              <th>Registered</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in paginatedSamples"
              :key="s.name"
              class="clickable-row"
              :title="`Open sample ${s.name}`"
              @click="openSample(s)"
            >
              <td class="font-mono text-accent"><strong>{{ s.name }}</strong></td>
              <td>
                <div class="sample-run-cell font-mono">{{ s.experiment }}</div>
                <div class="sample-run-sub" v-if="s.experiment_title">{{ s.experiment_title }}</div>
                <span
                  v-if="s.experiment_state"
                  class="status-pill status-pill-sm"
                  :class="runStateClass(s.experiment_state)"
                >
                  {{ s.experiment_state }}
                </span>
              </td>
              <td>{{ s.item }}</td>
              <td>{{ s.name_of_sample || '—' }}</td>
              <td class="font-mono">{{ s.qty }} <span class="text-muted">{{ s.uom || '' }}</span></td>
              <td>
                <span class="status-pill" :class="statusClass(s.status_label)">
                  {{ s.status_label }}
                </span>
              </td>
              <td class="text-muted">{{ formatDate(s.creation) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination Controls -->
        <div v-if="totalPages > 1" class="pagination-controls" style="display: flex; align-items: center; justify-content: center; gap: 1rem; margin-top: 1.5rem; padding-bottom: 0.5rem;">
          <button class="btn btn-secondary btn-sm" :disabled="currentPage === 1" @click="currentPage--">
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
        <path d="M9 2h6v6l4 9a3 3 0 0 1-2.7 4.3H7.7A3 3 0 0 1 5 17l4-9z" />
        <line x1="9" y1="2" x2="15" y2="2" />
        <line x1="7" y1="15" x2="17" y2="15" />
      </svg>
      <h3>No samples found</h3>
      <p>
        Samples are registered from a run's Samples tab once it is running.
        None exist yet for the selected project scope.
      </p>
      <router-link to="/experiments" class="btn btn-secondary mt-3">
        Go to Experiments
      </router-link>
    </div>
  </div>
</template>
