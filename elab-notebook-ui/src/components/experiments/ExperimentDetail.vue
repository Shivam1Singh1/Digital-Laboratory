<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { useUserStore } from '../../stores/user'
import LinkField from '../common/LinkField.vue'
import RichTextEditor from '../common/RichTextEditor.vue'
import './ExperimentDetail.css'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const successMessage = ref('')

const activeTab = ref('general')
const experiment = ref(null)

// The experiment's id is generated from its notebook, so the notebook is the natural
// parent to jump to. This app has no ELab Notebook page of its own - /elab-notebook/:id
// renders Experiment Team - so the link opens the Frappe desk form for the record.
const notebookUrl = computed(() =>
  experiment.value?.elab_notebook
    ? `/app/elab-notebook/${encodeURIComponent(experiment.value.elab_notebook)}`
    : ''
)
const historyList = ref([])
const completedSteps = ref({})

// Workflow state and actions
const workflowActions = ref([])
const loadingWorkflowActions = ref(false)
const runningWorkflowAction = ref(false)
const submittingSampleId = ref('')
const cancellingSampleId = ref('')

// Fetch experiment detail
const loadExperiment = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await axios.get(`/api/resource/Experiment/${encodeURIComponent(route.params.id)}`)
    experiment.value = res.data.data || null
    await fetchWorkflowActions()
    
    // Initialize completed steps checkboxes from local storage if any
    const saved = localStorage.getItem(`exp_steps_${route.params.id}`)
    if (saved) {
      completedSteps.value = JSON.parse(saved)
    } else {
      completedSteps.value = {}
    }
  } catch (err) {
    console.error('Failed to load experiment:', err)
    error.value = 'Failed to load experiment details. It may not exist or you lack permission.'
  } finally {
    loading.value = false
  }
}

const fetchWorkflowActions = async () => {
  if (!route.params.id) {
    workflowActions.value = []
    return
  }
  loadingWorkflowActions.value = true
  try {
    const res = await axios.get(
      '/api/method/elab_notebook.elab_notebook.api.workflow.get_workflow_actions',
      {
        params: {
          doctype: 'Experiment',
          docname: route.params.id
        }
      }
    )
    workflowActions.value = res.data.message || []
  } catch (err) {
    console.error('Failed to fetch workflow actions', err)
  } finally {
    loadingWorkflowActions.value = false
  }
}

const runWorkflowAction = async (action) => {
  if (!route.params.id) return
  runningWorkflowAction.value = true
  error.value = ''
  successMessage.value = ''
  try {
    const res = await axios.post(
      '/api/method/elab_notebook.elab_notebook.api.workflow.apply_workflow_action',
      {
        doctype: 'Experiment',
        docname: route.params.id,
        action: action
      }
    )
    if (experiment.value) {
      experiment.value.workflow_state = res.data.message || ''
    }
    successMessage.value = `Workflow transition "${action}" executed successfully.`
    setTimeout(() => {
      successMessage.value = ''
    }, 4000)
    await loadExperiment()
  } catch (err) {
    console.error('Failed to run workflow action', err)
    error.value = err.response?.data?._server_messages 
      ? JSON.parse(err.response.data._server_messages).join(', ') 
      : 'Error running workflow action.'
  } finally {
    runningWorkflowAction.value = false
  }
}

const getWorkflowStateClass = (state) => {
  if (!state) return 'state-draft'
  const s = state.toLowerCase()
  if (s.includes('approved')) return 'state-approved'
  if (s.includes('rejected')) return 'state-rejected'
  if (s.includes('pending')) return 'state-pending'
  if (s.includes('running')) return 'state-running'
  if (s.includes('completed')) return 'state-completed'
  if (s.includes('saved')) return 'state-saved'
  return 'state-draft'
}

const getWorkflowActionClass = (action) => {
  const act = action.toLowerCase()
  if (act.includes('approve')) return 'btn-success'
  if (act.includes('reject')) return 'btn-danger'
  if (act.includes('correction') || act.includes('back') || act.includes('resubmit')) return 'btn-warning'
  return 'btn-primary'
}

// Check if workflow state is locked (Approved or Rejected)
const isWorkflowLocked = () => {
  if (!experiment.value) return false
  const state = experiment.value.workflow_state || ''
  const s = state.toLowerCase()
  return s.includes('approved') || s.includes('rejected')
}

// Check if current user is System Manager
const isSystemManager = computed(() => {
  return userStore.user?.roles?.includes('System Manager') || false
})

// Check if user can edit locked fields
const canEditLockedFields = computed(() => {
  return !isWorkflowLocked() || isSystemManager.value
})

const submitSample = async (sample) => {
  submittingSampleId.value = sample.name
  error.value = ''
  successMessage.value = ''
  try {
    await axios.post('/api/method/frappe.client.submit', {
      doc: JSON.stringify(sample)
    })
    await loadSamples()
    successMessage.value = `Sample ${sample.name} submitted successfully.`
    setTimeout(() => {
      successMessage.value = ''
    }, 4000)
  } catch (err) {
    console.error('Failed to submit sample:', err)
    error.value = err.response?.data?._server_messages 
      ? JSON.parse(err.response.data._server_messages).join(', ') 
      : 'Failed to submit sample.'
  } finally {
    submittingSampleId.value = ''
  }
}

const cancelSample = async (sample) => {
  cancellingSampleId.value = sample.name
  error.value = ''
  successMessage.value = ''
  try {
    await axios.post('/api/method/frappe.client.cancel', {
      doctype: 'Sample',
      name: sample.name
    })
    await loadSamples()
    successMessage.value = `Sample ${sample.name} cancelled successfully.`
    setTimeout(() => {
      successMessage.value = ''
    }, 4000)
  } catch (err) {
    console.error('Failed to cancel sample:', err)
    error.value = err.response?.data?._server_messages 
      ? JSON.parse(err.response.data._server_messages).join(', ') 
      : 'Failed to cancel sample.'
  } finally {
    cancellingSampleId.value = ''
  }
}

// Fetch Version history
const loadHistory = async () => {
  try {
    const res = await axios.get('/api/method/frappe.client.get_list', {
      params: {
        doctype: 'Version',
        filters: JSON.stringify({
          ref_doctype: 'Experiment',
          docname: route.params.id
        }),
        fields: JSON.stringify(['name', 'owner', 'creation', 'data']),
        order_by: 'creation desc'
      }
    })
    historyList.value = (res.data.message || []).map(ver => {
      let parsedData = {}
      try {
        parsedData = JSON.parse(ver.data)
      } catch (e) {
        console.error('Failed to parse version data', e)
      }

      // Check if this is a workflow state change
      const isWorkflowChange = parsedData.changed && parsedData.changed.some(change => change[0] === 'workflow_state')

      return {
        ...ver,
        parsedData,
        isWorkflowChange,
        workflowStateChange: isWorkflowChange && parsedData.changed
          ? parsedData.changed.find(change => change[0] === 'workflow_state')
          : null
      }
    })
  } catch (err) {
    console.error('Failed to load version history:', err)
  }
}

// Toggle step completion checkbox
const toggleStep = (stepOrder) => {
  completedSteps.value[stepOrder] = !completedSteps.value[stepOrder]
  localStorage.setItem(`exp_steps_${route.params.id}`, JSON.stringify(completedSteps.value))
}

// Update experiment (PUT)
const updateExperiment = async () => {
  saving.value = true
  error.value = ''
  successMessage.value = ''
  try {
    const res = await axios.put(`/api/resource/Experiment/${encodeURIComponent(route.params.id)}`, experiment.value)
    if (res.data && res.data.data) {
      experiment.value = res.data.data
      successMessage.value = 'Experiment execution details updated successfully!'
      await fetchWorkflowActions()
      // Refresh history to capture edits
      await loadHistory()
      setTimeout(() => {
        successMessage.value = ''
      }, 4000)
    }
  } catch (err) {
    console.error('Failed to update experiment:', err)
    error.value = err.response?.data?._server_messages 
      ? JSON.parse(err.response.data._server_messages).join(', ') 
      : 'Error updating experiment records.'
  } finally {
    saving.value = false
  }
}

// Item edits
const addMethod = () => {
  experiment.value.methodology.push({
    method: '',
    time_to_complete: 0
  })
}

const removeMethod = (index) => {
  experiment.value.methodology.splice(index, 1)
}

const removeMaterial = (index) => {
  experiment.value.material_required.splice(index, 1)
}

const removeEquipment = (index) => {
  experiment.value.equipment_details.splice(index, 1)
}

// Format field names to readable strings
const formatFieldName = (name) => {
  return name
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
}

const formatTimestamp = (ts) => {
  if (!ts) return ''
  return ts.split('.')[0]
}

// --- Section: Samples
const showRegisterModal = ref(false)
const savingSample = ref(false)
const loadingSamples = ref(false)
const samplesList = ref([])
const newSample = ref({
  item: '',
  name_of_sample: '',
  qty: 0,
  uom: ''
})

const onItemSelect = (opt) => {
  newSample.value.uom = opt ? opt.stock_uom || '' : ''
  if (opt && !newSample.value.name_of_sample) {
    newSample.value.name_of_sample = opt.item_name || ''
  }
}

const loadSamples = async () => {
  if (!experiment.value) return
  loadingSamples.value = true
  try {
    const res = await axios.get('/api/resource/Sample', {
      params: {
        filters: JSON.stringify({ experiment: experiment.value.name }),
        fields: JSON.stringify(['name', 'elab_no', 'item', 'name_of_sample', 'qty', 'uom', 'docstatus']),
        limit: 100
      }
    })
    samplesList.value = res.data.data || []
  } catch (err) {
    console.error('Failed to load samples:', err)
  } finally {
    loadingSamples.value = false
  }
}

const getExperimentStatusClass = (status) => {
  if (!status) return 'state-draft'
  const s = status.toLowerCase()
  if (s.includes('completed')) return 'state-approved'
  if (s.includes('failed')) return 'state-rejected'
  return 'state-pending'
}

const handleSampleNotGenerated = async () => {
  if (!confirm('Are you sure you want to mark this experiment as Failed (No Sample generated)? This action is permanent.')) return
  saving.value = true
  try {
    await axios.put(`/api/resource/Experiment/${encodeURIComponent(experiment.value.name)}`, {
      sample_generated: 0,
      sample_not_generated: 1,
      experiment_status: 'Failed'
    })
    await loadExperiment()
  } catch (err) {
    console.error('Failed to update execution status:', err)
    alert('Error: Failed to mark experiment as failed.')
  } finally {
    saving.value = false
  }
}

const registerSample = async () => {
  if (!newSample.value.item || newSample.value.qty <= 0) {
    alert('Please select an item and enter a valid quantity.')
    return
  }
  savingSample.value = true
  try {
    const payload = {
      experiment: experiment.value.name,
      item: newSample.value.item,
      name_of_sample: newSample.value.name_of_sample,
      qty: newSample.value.qty
    }
    await axios.post('/api/resource/Sample', payload)
    
    // Auto-complete the experiment
    await axios.put(`/api/resource/Experiment/${encodeURIComponent(experiment.value.name)}`, {
      sample_generated: 1,
      sample_not_generated: 0,
      experiment_status: 'Completed'
    })
    
    // Reset and reload
    newSample.value = { item: '', name_of_sample: '', qty: 0, uom: '' }
    showRegisterModal.value = false
    await loadSamples()
    await loadExperiment()
  } catch (err) {
    console.error('Failed to register sample:', err)
    alert(err.response?.data?._server_messages 
      ? JSON.parse(err.response.data._server_messages).join(', ') 
      : 'Failed to register sample. Please verify the experiment is completed.')
  } finally {
    savingSample.value = false
  }
}

const getDocstatusLabel = (statusNum) => {
  if (statusNum === 0) return 'Draft'
  if (statusNum === 1) return 'Submitted'
  if (statusNum === 2) return 'Cancelled'
  return 'Unknown'
}

// Check if Sample can be created (only in Running state with no existing Sample)
const canCreateSample = () => {
  if (!experiment.value) return false
  const state = experiment.value.workflow_state || ''
  const isRunning = state.toLowerCase().includes('running')
  const sampleExists = samplesList.value && samplesList.value.length > 0
  return isRunning && !sampleExists
}

// Get tooltip for Create Sample button
const getCreateSampleTooltip = () => {
  if (!experiment.value) return 'Load experiment first'
  const state = experiment.value.workflow_state || 'Draft'
  const sampleExists = samplesList.value && samplesList.value.length > 0

  if (sampleExists) {
    return 'Sample already exists. One sample per experiment.'
  }
  if (!state.toLowerCase().includes('running')) {
    return `Sample creation available only in Running state. Current: ${state}`
  }
  return 'Create a new sample for this experiment'
}

// Check if Sample editing is allowed (Running or Completed only)
const canEditSample = () => {
  if (!experiment.value) return false
  const state = experiment.value.workflow_state || ''
  const s = state.toLowerCase()
  return s.includes('running') || s.includes('completed')
}

// Check if Sample is locked (Pending Approval, Approved, Rejected)
const isSampleLocked = () => {
  if (!experiment.value) return false
  const state = experiment.value.workflow_state || ''
  const s = state.toLowerCase()
  return s.includes('pending') || s.includes('approved') || s.includes('rejected')
}

watch(activeTab, (newTab) => {
  if (newTab === 'samples') {
    loadSamples()
  }
})

onMounted(() => {
  loadExperiment()
  loadHistory()
})
</script>

<template>
  <div class="experiment-detail-container">
    <!-- Header -->
    <div class="page-header" v-if="experiment">
      <div class="page-header-bg-icon">
        <svg class="header-lab-motif" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
          <path d="M6 3h12M9 3v4L4 18a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2L15 7V3" />
        </svg>
      </div>
      <div class="page-header-left">
        <nav class="breadcrumb-nav">
          <router-link to="/" class="breadcrumb-link">Home</router-link>
          <span class="breadcrumb-separator">&gt;</span>
          <router-link to="/experiments" class="breadcrumb-link">Experiments</router-link>
          <span class="breadcrumb-separator">&gt;</span>
          <span class="breadcrumb-current">{{ route.params.id }}</span>
        </nav>
        <h1 class="page-title">{{ experiment.title }}</h1>
        <p class="page-subtitle">
          Status: 
          <span 
            class="workflow-state-badge" 
            :class="getWorkflowStateClass(experiment.workflow_state)"
          >
            {{ experiment.workflow_state || 'Draft' }}
          </span>
          <span 
            v-if="experiment.experiment_status"
            class="workflow-state-badge" 
            :class="getExperimentStatusClass(experiment.experiment_status)"
            style="margin-left: 0.5rem;"
          >
            {{ experiment.experiment_status }}
          </span>
        </p>
      </div>

      <div class="page-header-right">
        <span v-if="loadingWorkflowActions" class="workflow-loading-spinner"></span>
        <template v-else>
          <button 
            v-for="act in workflowActions" 
            :key="act.action" 
            class="btn btn-workflow btn-sm" 
            :class="getWorkflowActionClass(act.action)"
            @click="runWorkflowAction(act.action)"
            :disabled="runningWorkflowAction"
          >
            {{ act.action }}
          </button>
        </template>
        <button class="btn btn-secondary" @click="router.push('/experiments')">Back to List</button>
        <button class="btn btn-primary" :disabled="saving" @click="updateExperiment">
          {{ saving ? 'Saving...' : 'Update Execution' }}
        </button>
      </div>
    </div>

    <!-- Feedback banners -->
    <div v-if="error" class="form-error-banner">
      <strong>Error:</strong> {{ error }}
      <button class="form-error-close" @click="error = ''">×</button>
    </div>
    
    <div v-if="successMessage" class="form-success-banner">
      <strong>Success:</strong> {{ successMessage }}
      <button class="form-error-close" @click="successMessage = ''">×</button>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading experiment execution logs...</p>
    </div>

    <div v-else-if="!experiment" class="empty-state">
      <h3>Experiment Not Found</h3>
      <p>The requested run ID does not exist or you lack sufficient access.</p>
    </div>

    <!-- Action Block: Sample Generated? -->
    <div v-if="experiment && experiment.experiment_status === 'In Progress'" class="sample-generated-bar card" style="background-image: var(--accent-gradient); display: flex; align-items: center; justify-content: space-between; padding: 1rem 1.5rem; margin-bottom: 1.5rem; border: 1px solid var(--border); border-radius: 12px; box-shadow: var(--shadow-sm); overflow: hidden; position: relative;">
      <!-- Subtle beaker motif positioned inside the bar -->
      <div style="position: absolute; right: 2rem; bottom: -0.5rem; opacity: 0.05; pointer-events: none; color: var(--accent);">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" style="width: 72px; height: 72px;">
          <path d="M6 3h12M9 3v4L4 18a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2L15 7V3" />
        </svg>
      </div>
      <div class="bar-left" style="display: flex; align-items: center; gap: 0.75rem;">
        <svg class="flask-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 24px; height: 24px; color: var(--accent); flex-shrink: 0;">
          <path d="M6 3h12M9 3v4L4 18a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2L15 7V3" />
        </svg>
        <div style="text-align: left;">
          <h4 style="margin: 0; font-size: 0.95rem; font-weight: 600; color: var(--text-primary);">Execution Outcome: Has a Sample been generated from this run?</h4>
          <p style="margin: 0.15rem 0 0 0; font-size: 0.8rem; color: var(--text-muted);">Please document whether this experiment succeeded in generating output samples.</p>
        </div>
      </div>
      <div class="bar-right" style="display: flex; gap: 0.75rem; position: relative; z-index: 1;">
        <button class="btn btn-sm btn-success" @click="showRegisterModal = true" style="padding: 0.5rem 1rem; border-radius: 6px; font-weight: 600;">
          Yes, Register Sample
        </button>
        <button class="btn btn-sm btn-danger" @click="handleSampleNotGenerated" style="padding: 0.5rem 1rem; border-radius: 6px; font-weight: 600;">
          No, Failed/No Output
        </button>
      </div>
    </div>

    <div v-else class="detail-layout card">
      <!-- Tabs -->
      <div class="form-tabs-row">
        <button 
          class="tab-btn" 
          :class="{ active: activeTab === 'general' }" 
          @click="activeTab = 'general'"
        >
          General/Template
        </button>
        <button 
          class="tab-btn" 
          :class="{ active: activeTab === 'materials' }" 
          @click="activeTab = 'materials'"
        >
          Material Required
        </button>
        <button 
          class="tab-btn" 
          :class="{ active: activeTab === 'equipment' }" 
          @click="activeTab = 'equipment'"
        >
          Equipment Details
        </button>
        <button 
          class="tab-btn" 
          :class="{ active: activeTab === 'methodology' }" 
          @click="activeTab = 'methodology'"
        >
          Methodology
        </button>
        <button 
          class="tab-btn" 
          :class="{ active: activeTab === 'procedure' }" 
          @click="activeTab = 'procedure'"
        >
          Protocol Steps
        </button>
        <button 
          class="tab-btn" 
          :class="{ active: activeTab === 'observations' }" 
          @click="activeTab = 'observations'"
        >
          Observation
        </button>
        <button 
          class="tab-btn" 
          :class="{ active: activeTab === 'history' }" 
          @click="activeTab = 'history'"
        >
          History/Audit Log
        </button>
        <button 
          class="tab-btn" 
          :class="{ active: activeTab === 'samples' }" 
          @click="activeTab = 'samples'"
        >
          Samples
        </button>
      </div>

      <!-- Tab Content panes -->
      <div class="tab-content">
        <!-- 1. GENERAL TAB -->
        <div v-if="activeTab === 'general'" class="tab-pane">
          <div class="pane-grid">
            <div class="form-group-row">
              <div class="form-group">
                <label class="form-label">ELab Notebook</label>
                <a
                  v-if="experiment.elab_notebook"
                  :href="notebookUrl"
                  target="_blank"
                  rel="noopener"
                  class="form-control link-value"
                  :title="`Open ${experiment.elab_notebook}`"
                >
                  <span class="link-value-text">{{ experiment.elab_notebook }}</span>
                  <svg class="link-value-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                    <polyline points="15 3 21 3 21 9" />
                    <line x1="10" y1="14" x2="21" y2="3" />
                  </svg>
                </a>
                <input v-else type="text" value="None" class="form-control readonly" readonly />
              </div>
              <div class="form-group">
                <label class="form-label">Project</label>
                <input type="text" :value="experiment.project" class="form-control readonly" readonly />
              </div>
            </div>

            <div class="form-group-row">
              <div class="form-group">
                <label class="form-label">Employee Function</label>
                <input type="text" :value="experiment.employee_function" class="form-control readonly" readonly />
              </div>
              <div class="form-group">
                <label class="form-label">Template</label>
                <input type="text" :value="experiment.template || 'None'" class="form-control readonly" readonly />
              </div>
            </div>

            <div class="form-group-row">
              <div class="form-group">
                <label class="form-label">Segment</label>
                <input type="text" :value="experiment.segment || 'None'" class="form-control readonly" readonly />
              </div>
              <div class="form-group">
                <label class="form-label">Cost Centre</label>
                <input type="text" :value="experiment.cost_center || 'None'" class="form-control readonly" readonly />
              </div>
            </div>

            <div class="form-group-row">
              <div class="form-group">
                <label class="form-label">Scientist (Lead)</label>
                <input type="text" :value="experiment.employee_name" class="form-control readonly" readonly />
              </div>
              <div class="form-group">
                <label class="form-label">Start Date</label>
                <input type="text" :value="experiment.experiment_start_date" class="form-control readonly" readonly />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Aim / Hypothesis</label>
              <input type="text" :value="experiment.aim" class="form-control readonly" readonly />
            </div>

            <div class="form-group">
              <label class="form-label">Sub Aim</label>
              <input type="text" :value="experiment.sub_aim" class="form-control readonly" readonly />
            </div>

            <div class="form-group">
              <label class="form-label">Rationale</label>
              <div class="readonly-textarea">{{ experiment.rationale || 'No rationale specified' }}</div>
            </div>
          </div>
        </div>

        <!-- 2. MATERIALS TAB (EDITABLE with delete) -->
        <div v-if="activeTab === 'materials'" class="tab-pane">
          <div v-if="isWorkflowLocked() && !isSystemManager" class="info-banner" style="background-color: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: 0.85rem; color: #F59E0B;">
            ⚠️ This experiment is locked. Only System Managers can edit materials in this state.
          </div>
          <h3 class="pane-subtitle">Formulation Ingredients</h3>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>Item Code</th>
                  <th>Item Name</th>
                  <th>UOM</th>
                  <th>Qty Required</th>
                  <th class="actions-col"></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(mat, idx) in experiment.material_required" :key="idx">
                  <td class="font-mono text-accent">{{ mat.item_code }}</td>
                  <td>{{ mat.item_name }}</td>
                  <td>{{ mat.uom }}</td>
                  <td><input type="number" v-model="mat.qty" class="form-control table-input" min="0" :disabled="isWorkflowLocked() && !isSystemManager" /></td>
                  <td><button class="delete-row-btn" @click="removeMaterial(idx)" :disabled="isWorkflowLocked() && !isSystemManager" :title="isWorkflowLocked() && !isSystemManager ? 'Locked in this workflow state' : 'Delete material'">×</button></td>
                </tr>
                <tr v-if="!experiment.material_required || experiment.material_required.length === 0">
                  <td colspan="5" class="empty-table-cell">No materials required for this run.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 3. EQUIPMENT TAB (EDITABLE with delete) -->
        <div v-if="activeTab === 'equipment'" class="tab-pane">
          <div v-if="isWorkflowLocked() && !isSystemManager" class="info-banner" style="background-color: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: 0.85rem; color: #F59E0B;">
            ⚠️ This experiment is locked. Only System Managers can edit equipment in this state.
          </div>
          <h3 class="pane-subtitle">Instruments & Tool Allocation</h3>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>Equipment Name</th>
                  <th>Equipment ID</th>
                  <th>Remarks / Allocation</th>
                  <th class="actions-col"></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(eq, idx) in experiment.equipment_details" :key="idx">
                  <td><input type="text" v-model="eq.equipment_name" class="form-control table-input" placeholder="e.g. HPLC Machine" :disabled="isWorkflowLocked() && !isSystemManager" /></td>
                  <td class="font-mono"><input type="text" v-model="eq.equipment_id" class="form-control table-input" placeholder="e.g. HPLC-001" :disabled="isWorkflowLocked() && !isSystemManager" /></td>
                  <td><input type="text" v-model="eq.remarks" class="form-control table-input" placeholder="e.g. Reserved for 9am session" :disabled="isWorkflowLocked() && !isSystemManager" /></td>
                  <td><button class="delete-row-btn" @click="removeEquipment(idx)" :disabled="isWorkflowLocked() && !isSystemManager" :title="isWorkflowLocked() && !isSystemManager ? 'Locked in this workflow state' : 'Delete equipment'">×</button></td>
                </tr>
                <tr v-if="!experiment.equipment_details || experiment.equipment_details.length === 0">
                  <td colspan="4" class="empty-table-cell">No equipment allocated.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 4. METHODOLOGY TAB (EDITABLE) -->
        <div v-if="activeTab === 'methodology'" class="tab-pane">
          <div v-if="isWorkflowLocked() && !isSystemManager" class="info-banner" style="background-color: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: 0.85rem; color: #F59E0B;">
            ⚠️ This experiment is locked. Only System Managers can edit fields in this state.
          </div>
          <div class="pane-header-row">
            <h3 class="pane-subtitle">Experimental Methodology (Execution Steps)</h3>
            <button class="btn btn-secondary btn-sm btn-add-row" @click="addMethod" :disabled="isWorkflowLocked() && !isSystemManager">+ Add Method</button>
          </div>

          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>Method Description</th>
                  <th>Expected Duration (mins)</th>
                  <th class="actions-col"></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(meth, idx) in experiment.methodology" :key="idx">
                  <td>
                    <input type="text" v-model="meth.method" class="form-control table-input" placeholder="e.g. HPLC separation" :disabled="isWorkflowLocked() && !isSystemManager" />
                  </td>
                  <td>
                    <input type="number" v-model="meth.time_to_complete" class="form-control table-input" min="0" :disabled="isWorkflowLocked() && !isSystemManager" />
                  </td>
                  <td>
                    <button class="delete-row-btn" @click="removeMethod(idx)" :disabled="isWorkflowLocked() && !isSystemManager">×</button>
                  </td>
                </tr>
                <tr v-if="experiment.methodology.length === 0">
                  <td colspan="3" class="empty-table-cell">No methodology steps. Click '+ Add Method' to insert.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 5. PROTOCOL STEPS TAB (CHECKLIST) -->
        <div v-if="activeTab === 'procedure'" class="tab-pane">
          <h3 class="pane-subtitle">Execution Checklist</h3>
          
          <div class="protocol-steps-list">
            <div 
              v-for="step in experiment.experiment_protocol_steps" 
              :key="step.step_order" 
              class="protocol-step-item execution-step"
              :class="{ completed: completedSteps[step.step_order] }"
              @click="toggleStep(step.step_order)"
            >
              <div class="step-checkbox-wrapper">
                <div class="step-checkbox" :class="{ checked: completedSteps[step.step_order] }">
                  <svg v-if="completedSteps[step.step_order]" class="check-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                </div>
              </div>
              <div class="step-num">{{ step.step_order }}.</div>
              <div class="step-details">
                <div class="step-title-row">
                  <strong class="step-heading" :class="{ 'line-through': completedSteps[step.step_order] }">
                    {{ step.title }}
                  </strong>
                  <span v-if="step.duration" class="step-duration">Duration: {{ step.duration }}</span>
                </div>
                <p class="step-desc">{{ step.description }}</p>
                <div class="step-meta" v-if="step.equipment || step.operator_role">
                  <span v-if="step.equipment">Equipment: <strong>{{ step.equipment }}</strong></span>
                  <span v-if="step.operator_role">Role: <strong>{{ step.operator_role }}</strong></span>
                </div>
              </div>
            </div>
            <div v-if="!experiment.experiment_protocol_steps || experiment.experiment_protocol_steps.length === 0" class="empty-list-pane">
              No checklist steps loaded.
            </div>
          </div>
        </div>

        <!-- 6. OBSERVATION TAB (EDITABLE) -->
        <div v-if="activeTab === 'observations'" class="tab-pane">
          <div v-if="isWorkflowLocked() && !isSystemManager" class="info-banner" style="background-color: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: 0.85rem; color: #F59E0B;">
            ⚠️ This experiment is locked. Only System Managers can edit observations in this state.
          </div>
          <section class="meta-card">
            <h3 class="pane-subtitle">Observation Comments</h3>
            <div class="form-group stacked-field">
              <RichTextEditor v-model="experiment.observation" placeholder="Enter observations…" :readonly="isWorkflowLocked() && !isSystemManager" />
            </div>
          </section>
        </div>

        <!-- 7. HISTORY / AUDIT LOG TAB -->
        <div v-if="activeTab === 'history'" class="tab-pane">
          <h3 class="pane-subtitle">Change History Audit Log</h3>
          
          <div class="history-timeline">
            <div v-for="ver in historyList" :key="ver.name" class="timeline-item" :class="{ 'workflow-change': ver.isWorkflowChange }">
              <div class="timeline-dot"></div>
              <div class="timeline-content" :style="ver.isWorkflowChange ? { borderLeft: '3px solid var(--accent)' } : {}">
                <div class="timeline-header">
                  <span class="timeline-author"><strong>{{ ver.owner }}</strong></span>
                  <span class="timeline-time">{{ formatTimestamp(ver.creation) }}</span>
                </div>

                <!-- Workflow state changes highlighted -->
                <div v-if="ver.isWorkflowChange" style="padding: 0.5rem 0.75rem; background-color: var(--bg-surface); border-radius: 4px; margin: 0.25rem 0;">
                  <span style="font-weight: 600; color: var(--accent);">⚡ Workflow State Changed:</span>
                  <br />
                  <span style="color: var(--text-muted);">{{ ver.workflowStateChange[1] || 'Draft' }}</span>
                  <span style="color: var(--text-muted);">→</span>
                  <span style="color: var(--success); font-weight: 600;">{{ ver.workflowStateChange[2] }}</span>
                </div>

                <!-- If fields changed (exclude workflow_state) -->
                <ul class="timeline-changes" v-if="ver.parsedData && ver.parsedData.changed && ver.parsedData.changed.length > 0">
                  <li v-for="(change, cIdx) in ver.parsedData.changed.filter(c => c[0] !== 'workflow_state')" :key="cIdx">
                    Field <strong>{{ formatFieldName(change[0]) }}</strong> updated:
                    <span class="old-val">"{{ change[1] || 'Empty' }}"</span> &rarr;
                    <span class="new-val">"{{ change[2] || 'Empty' }}"</span>
                  </li>
                </ul>

                <!-- If tables added/removed rows -->
                <ul class="timeline-changes" v-if="ver.parsedData && (ver.parsedData.added || ver.parsedData.removed)">
                  <li v-if="ver.parsedData.added && ver.parsedData.added.length > 0">
                    Added <strong>{{ ver.parsedData.added.length }}</strong> row(s) to child tables
                  </li>
                  <li v-if="ver.parsedData.removed && ver.parsedData.removed.length > 0">
                    Removed <strong>{{ ver.parsedData.removed.length }}</strong> row(s) from child tables
                  </li>
                </ul>

                <!-- Fallback description -->
                <p class="timeline-desc" v-if="!ver.parsedData || (!ver.parsedData.changed && !ver.parsedData.added && !ver.parsedData.removed)">
                  Updated record metadata.
                </p>
              </div>
            </div>

            <div v-if="historyList.length === 0" class="empty-list-pane">
              No edit history found for this run.
            </div>
          </div>
        </div>

        <!-- 7. SAMPLES TAB -->
        <div v-if="activeTab === 'samples'" class="tab-pane">
          <!-- Sample Status Indicators -->
          <div class="sample-status-indicators" style="margin-bottom: 1.5rem; display: flex; gap: 2rem;">
            <div class="status-indicator">
              <span class="status-label">Sample Generated:</span>
              <span class="status-value" :class="{ 'status-active': samplesList.length > 0 }">
                {{ samplesList.length > 0 ? '✓ Generated' : '○ Not Generated' }}
              </span>
            </div>
            <div class="status-indicator">
              <span class="status-label">Sample Submitted:</span>
              <span class="status-value" :class="{ 'status-active': samplesList.some(s => s.docstatus === 1) }">
                {{ samplesList.some(s => s.docstatus === 1) ? '✓ Submitted' : '○ Pending' }}
              </span>
            </div>
          </div>

          <div class="samples-section-header">
            <h3 class="pane-section-title">Result Output Samples</h3>
            <div class="header-action-wrapper" :title="getCreateSampleTooltip()">
              <button
                class="btn btn-primary"
                :disabled="!canCreateSample()"
                @click="showRegisterModal = true"
              >
                + Create Sample
              </button>
            </div>
          </div>

          <!-- Lock Warning -->
          <div v-if="isSampleLocked()" class="info-banner" style="background-color: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: 0.85rem; color: #F59E0B;">
            ⚠️ Sample is locked. Only System Managers can modify samples in {{ experiment.workflow_state }} state.
          </div>

          <div v-if="loadingSamples" class="loading-state inner-load">
            <div class="spinner"></div>
            <p>Loading registered samples...</p>
          </div>

          <div v-else class="samples-list-wrapper">
            <table class="samples-table" v-if="samplesList.length > 0">
              <thead>
                <tr>
                  <th>Elab No.</th>
                  <th>Item</th>
                  <th>Name of Sample</th>
                  <th>Qty</th>
                  <th>UOM</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="sample in samplesList" :key="sample.name">
                  <td><strong>{{ sample.elab_no }}</strong></td>
                  <td>{{ sample.item }}</td>
                  <td>{{ sample.name_of_sample || 'Unnamed' }}</td>
                  <td>{{ sample.qty }}</td>
                  <td><span class="uom-badge">{{ sample.uom || '-' }}</span></td>
                  <td>
                    <span 
                      class="status-badge"
                      :class="{ 
                        'status-draft': sample.docstatus === 0, 
                        'status-submitted': sample.docstatus === 1,
                        'status-cancelled': sample.docstatus === 2 
                      }"
                    >
                      {{ getDocstatusLabel(sample.docstatus) }}
                    </span>
                  </td>
                  <td>
                    <div class="row-actions" style="display: flex; gap: 0.5rem;">
                      <button
                        v-if="sample.docstatus === 0"
                        class="btn btn-sm btn-success"
                        :disabled="submittingSampleId === sample.name || (isSampleLocked() && !isSystemManager)"
                        :title="isSampleLocked() && !isSystemManager ? 'Sample is locked in this workflow state' : 'Submit sample'"
                        @click="submitSample(sample)"
                        style="padding: 0.25rem 0.5rem; font-size: 0.75rem;"
                      >
                        {{ submittingSampleId === sample.name ? 'Submitting...' : 'Submit' }}
                      </button>
                      <button
                        v-if="sample.docstatus === 1"
                        class="btn btn-sm btn-danger"
                        :disabled="cancellingSampleId === sample.name || (isSampleLocked() && !isSystemManager)"
                        :title="isSampleLocked() && !isSystemManager ? 'Sample is locked in this workflow state' : 'Cancel sample'"
                        @click="cancelSample(sample)"
                        style="padding: 0.25rem 0.5rem; font-size: 0.75rem;"
                      >
                        {{ cancellingSampleId === sample.name ? 'Cancelling...' : 'Cancel' }}
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
            
            <div v-else class="empty-list-pane">
              No samples have been registered for this experiment run yet.
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 8. Register Sample Modal Dialog -->
    <div v-if="showRegisterModal" class="modal-overlay">
      <div class="modal-container sample-register-modal">
        <div class="modal-header">
          <h3 class="modal-title">Register Output Sample</h3>
          <button class="modal-close-btn" @click="showRegisterModal = false">×</button>
        </div>
        
        <div class="modal-body">
          <div class="form-group-row">
            <div class="form-group">
              <label class="form-label">Parent Experiment ID</label>
              <input type="text" :value="experiment.name" class="form-control readonly" readonly />
            </div>
            <div class="form-group">
              <label class="form-label">Elab No.</label>
              <input type="text" :value="experiment.name" class="form-control readonly" readonly />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Select Output Item *</label>
            <LinkField
              v-model="newSample.item"
              doctype="Item"
              :fields="['item_name', 'stock_uom']"
              :search-fields="['name', 'item_name']"
              description-field="item_name"
              placeholder="Search item code or name..."
              @select="onItemSelect"
            />
          </div>

          <div class="form-group-row">
            <div class="form-group">
              <label class="form-label">Name of Sample</label>
              <input 
                type="text" 
                v-model="newSample.name_of_sample" 
                class="form-control" 
                placeholder="Enter sample descriptive name..." 
              />
            </div>
            <div class="form-group">
              <label class="form-label">Quantity *</label>
              <div class="qty-input-group">
                <input 
                  type="number" 
                  step="any" 
                  min="0" 
                  v-model.number="newSample.qty" 
                  class="form-control" 
                  placeholder="0.0"
                  required 
                />
                <span class="qty-uom-suffix" v-if="newSample.uom">{{ newSample.uom }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showRegisterModal = false" :disabled="savingSample">Cancel</button>
          <button class="btn btn-primary" @click="registerSample" :disabled="savingSample || !newSample.item || newSample.qty <= 0">
            {{ savingSample ? 'Saving...' : 'Register' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
