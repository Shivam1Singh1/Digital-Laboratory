<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { useUserStore } from '../../stores/user'
import LinkField from '../common/LinkField.vue'
import RichTextEditor from '../common/RichTextEditor.vue'
import ExperimentTree from './ExperimentTree.vue'
import ExperimentReport from './ExperimentReport.vue'
import RawDataTab from './RawDataTab.vue'
import { showsRawDataTab } from '../../utils/rawData'
import { showsReportTab } from '../../utils/reportTab'
import AddRow from '../common/AddRow.vue'
import FileAttachment from '../common/FileAttachment.vue'
import { readServerError } from '../../utils/serverError'
import { formatAuditDate } from '../../utils/dateFormatter'
import { deskUrl } from '../../utils/frappeUrl'
import './ExperimentDetail.css'


const route = useRoute()
const router = useRouter()
const userStore = useUserStore()


const loading = ref(true)
const saving = ref(false)
const error = ref('')
const successMessage = ref('')


const TAB_KEYS = [
  'general',
  'details',
  'rawdata',
  'result',
  'materials',
  'equipment',
  'methodology',
  'tree',
  'report',
  'samples',
  'history',
]

const activeTab = ref('general')
const experiment = ref(null)


const TEMPLATE_TABS = ['materials', 'equipment', 'methodology', 'procedure']

const usesTemplate = computed(
  () => experiment.value?.experiment_category === 'Sub Sub Experiment'
)


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


const isRootExperiment = computed(() => {
  const category = experiment.value?.experiment_category
  if (!category || !categoryOptions.value.length) return false
  return !categoryOptions.value.some((o) => o.child_category === category)
})

const childCategory = computed(
  () =>
    categoryOptions.value.find((o) => o.category === experiment.value?.experiment_category)
      ?.child_category || ''
)


const canStartChildRun = computed(() => isRootExperiment.value && Boolean(childCategory.value))


const showsCuratedChildren = computed(() => Boolean(childCategory.value))


const curatedChildFilters = computed(() => {
  const taken = (experiment.value?.successful_children || [])
    .map((r) => r.linked_experiment)
    .filter(Boolean)
  const filters = [
    ['experiment_category', '=', childCategory.value],
    ['name', '!=', String(route.params.id)],
  ]
  if (taken.length) filters.push(['name', 'not in', taken])
  return filters
})

const addCuratedChild = () => {
  if (!experiment.value.successful_children) experiment.value.successful_children = []
  experiment.value.successful_children.push({
    linked_experiment: '',
    linked_experiment_title: '',
  })
}

const removeCuratedChild = (idx) => {
  experiment.value.successful_children.splice(idx, 1)
}


const onCuratedChildSelect = (row, opt) => {
  row.linked_experiment_title = opt ? opt.title || '' : ''
}


const startChildRun = () => {
  if (!canStartChildRun.value) return
  const query = {
    experiment_category: childCategory.value,


    parent_experiment: experiment.value.name,
    project: experiment.value.project,
    employee_function: experiment.value.employee_function,
    experiment_team: experiment.value.experiment_team,
  }


  for (const key of Object.keys(query)) {
    if (!query[key]) delete query[key]
  }
  router.push({ path: '/experiments/new', query })
}


const visibleTabs = computed(() => [
  { key: 'general', label: 'Template' },
  { key: 'details', label: 'Details' },


  ...(showsRawDataTab(experiment.value?.experiment_category)
    ? [{ key: 'rawdata', label: 'Raw Data' }]
    : []),


  { key: 'result', label: 'Result' },
  ...(usesTemplate.value
    ? [


        { key: 'materials', label: 'Material & Equipment' },


      ]
    : []),
  { key: 'tree', label: 'Experiment Hierarchy' },


  ...(showsReportTab(experiment.value?.experiment_category)
    ? [{ key: 'report', label: 'Report' }]
    : []),
  { key: 'samples', label: 'Samples' },


])


const teamRoute = computed(() =>
  experiment.value?.experiment_team
    ? `/elab-notebook/${encodeURIComponent(experiment.value.experiment_team)}`
    : ''
)


const teamName = ref('')

const loadTeamName = async () => {
  teamName.value = ''
  const team = experiment.value?.experiment_team
  if (!team) return
  try {
    const res = await axios.get('/api/method/frappe.client.get_value', {
      params: {
        doctype: 'Experiment Team',
        filters: JSON.stringify({ name: team }),
        fieldname: JSON.stringify(['team_name']),
      },
    })
    teamName.value = res.data.message?.team_name || ''
  } catch (err) {
    console.error('Failed to read the team name:', err)
  }
}


const openDatePicker = (event) => {
  const input = event.currentTarget
  if (!input || input.readOnly || input.disabled) return
  try {
    input.showPicker?.()
  } catch {

  }
}

const teamLabel = computed(() => {
  const team = experiment.value?.experiment_team || ''
  return teamName.value ? `${teamName.value} — ${team}` : team
})


const notebookUrl = computed(() =>
  experiment.value?.elab_notebook
    ? `/app/elab-notebook/${encodeURIComponent(experiment.value.elab_notebook)}`
    : ''
)
const historyList = ref([])


const workflowActions = ref([])
const loadingWorkflowActions = ref(false)
const runningWorkflowAction = ref(false)
const submittingSampleId = ref('')
const cancellingSampleId = ref('')


const loadExperiment = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await axios.get(`/api/resource/Lab%20Experiment/${encodeURIComponent(route.params.id)}`)
    experiment.value = res.data.data || null
    await fetchWorkflowActions()
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
          doctype: 'Lab Experiment',
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
        doctype: 'Lab Experiment',
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


const STATE_CLASSES = {
  Start: 'state-draft',
  'In Progress': 'state-running',
  Completed: 'state-completed',
  'Sent for Approval': 'state-pending',
  'Edit Completed': 'state-saved',
  Approved: 'state-approved',
  Rejected: 'state-rejected'
}

const getWorkflowStateClass = (state) => {
  if (!state) return 'state-draft'
  if (STATE_CLASSES[state]) return STATE_CLASSES[state]
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


const runState = computed(() => experiment.value?.workflow_state || 'Start')
const isDraft = computed(() => runState.value === 'Start')
const isRunning = computed(() => runState.value === 'In Progress')


const DRIVEN_ACTIONS = ['Start Experiment', 'Complete Experiment', 'Send For Approval']
const headerWorkflowActions = computed(() =>
  workflowActions.value.filter((a) => !DRIVEN_ACTIONS.includes(a.action))
)


const applyWorkflowChain = async (actions, message) => {
  runningWorkflowAction.value = true
  error.value = ''
  successMessage.value = ''
  try {
    for (const action of actions) {
      await axios.post(
        '/api/method/elab_notebook.elab_notebook.api.workflow.apply_workflow_action',
        { doctype: 'Lab Experiment', docname: route.params.id, action }
      )
    }
    successMessage.value = message
    setTimeout(() => {
      successMessage.value = ''
    }, 4000)
  } catch (err) {
    console.error('Workflow transition failed', err)
    error.value = readServerError(err, 'Could not move this run to its next state.')
  } finally {
    await loadExperiment()
    await loadHistory()


    runningWorkflowAction.value = false
  }
}


const startRun = () =>
  applyWorkflowChain(['Start Experiment'], 'Run started - every tab is editable from here on.')

const completeAndSendForApproval = () => {
  if (
    !confirm(
      'Send this run for approval? It stays editable until a System Manager approves it.'
    )
  ) {
    return
  }
  return applyWorkflowChain(
    ['Complete Experiment', 'Send For Approval'],
    'Sent for approval.'
  )
}


const LOCKED_STATES = ['Start', 'Sent for Approval', 'Approved', 'Rejected']

const isWorkflowLocked = () => {
  if (!experiment.value) return false
  const state = experiment.value.workflow_state || ''
  if (LOCKED_STATES.includes(state)) return true


  const s = state.toLowerCase()
  return s.includes('approved') || s.includes('rejected') || s.includes('pending')
}


const isSystemManager = computed(() => {
  return userStore.user?.roles?.includes('System Manager') || false
})


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


const loadHistory = async () => {
  try {
    const res = await axios.get('/api/method/frappe.client.get_list', {
      params: {
        doctype: 'Version',
        filters: JSON.stringify({
          ref_doctype: 'Lab Experiment',
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


const updateExperiment = async () => {
  saving.value = true
  error.value = ''
  successMessage.value = ''


  renumberProtocolSteps()
  try {
    const res = await axios.put(`/api/resource/Lab%20Experiment/${encodeURIComponent(route.params.id)}`, experiment.value)
    if (res.data && res.data.data) {
      experiment.value = res.data.data
      successMessage.value = 'Experiment execution details updated successfully!'
      await fetchWorkflowActions()

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


const addMaterial = () => {
  experiment.value.material_required.push({ item_code: '', item_name: '', uom: '', qty: 1 })
}

const addEquipment = () => {
  experiment.value.equipment_details.push({ equipment_name: '', equipment_id: '', remarks: '' })
}


const renumberProtocolSteps = () => {
  const rows = experiment.value.protocol_steps || []
  rows.forEach((row, idx) => {
    row.step_no = idx + 1
  })
}

const addProtocolStep = () => {
  const rows = experiment.value.protocol_steps
  rows.push({
    step_no: rows.length + 1,
    instruction: '',
    expected_duration: 0,
    is_critical: 0,
    attachment: ''
  })
  renumberProtocolSteps()
}

const addObservationRow = () => {
  experiment.value.observations.push({
    parameter: '',
    unit: '',
    expected_range: '',
    remarks: '',
    observation: ''
  })
}

const addMethod = () => {
  experiment.value.methodology.push({
    method: '',
    time_to_complete: 0
  })
}


const onMaterialItemSelect = (mat, item) => {
  if (!item) return
  mat.item_name = item.item_name || item.name
  mat.uom = item.stock_uom || item.uom || ''
}


const isImportedRow = (row) => Boolean(row?.from_template)

const removeChildRow = (fieldname, index) => {
  const rows = experiment.value?.[fieldname]
  if (!rows || isImportedRow(rows[index])) return
  rows.splice(index, 1)
}

const removeMethod = (index) => removeChildRow('methodology', index)
const removeMaterial = (index) => removeChildRow('material_required', index)
const removeEquipment = (index) => removeChildRow('equipment_details', index)
const removeProtocolStep = (index) => {
  removeChildRow('protocol_steps', index)


  renumberProtocolSteps()
}
const removeObservationRow = (index) => removeChildRow('observations', index)


const formatFieldName = (name) => {
  return name
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
}

const formatTimestamp = (ts) => {
  if (!ts) return ''
  return ts.split('.')[0]
}


const loadingSamples = ref(false)
const samplesList = ref([])


const commentDrafts = ref({})
const savingCommentsFor = ref('')
const commentsNotice = ref('')

const commentDraft = (sample) =>
  commentDrafts.value[sample.name] ?? (sample.comments || '')

const setCommentDraft = (sample, value) => {
  commentDrafts.value = { ...commentDrafts.value, [sample.name]: value }
}

const commentsDirty = (sample) => commentDraft(sample).trim() !== (sample.comments || '').trim()


const isCommentsLocked = () => isSampleLocked()

const saveSampleComments = async (sample) => {
  savingCommentsFor.value = sample.name
  sampleError.value = ''
  commentsNotice.value = ''
  try {
    await axios.put(`/api/resource/Sample/${encodeURIComponent(sample.name)}`, {
      comments: commentDraft(sample)
    })
    commentsNotice.value = `Comments saved for ${sample.elab_no || sample.name}.`
    setTimeout(() => { commentsNotice.value = '' }, 4000)

    const { [sample.name]: _dropped, ...rest } = commentDrafts.value
    commentDrafts.value = rest
    await loadSamples()
  } catch (err) {
    console.error('Failed to save sample comments:', err)
    sampleError.value = readServerError(err, 'Could not save the comments for this sample.')
  } finally {
    savingCommentsFor.value = ''
  }
}

const loadSamples = async () => {
  if (!experiment.value) return
  loadingSamples.value = true
  try {
    const res = await axios.get('/api/resource/Sample', {
      params: {
        filters: JSON.stringify({ experiment: experiment.value.name }),
        fields: JSON.stringify(['name', 'elab_no', 'item', 'name_of_sample', 'qty', 'uom', 'docstatus', 'comments']),
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


const markFailedNoSample = async () => {
  if (
    !confirm(
      'Mark this run as Failed with no sample?\n\n'
        + 'The Failed outcome is permanent and the run is then sent for approval. '
        + 'Its data stays editable until a System Manager approves it.'
    )
  ) {
    return
  }
  saving.value = true
  error.value = ''
  try {
    await axios.put(`/api/resource/Lab%20Experiment/${encodeURIComponent(experiment.value.name)}`, {
      sample_generated: 0,
      sample_not_generated: 1,
      experiment_status: 'Failed'
    })
  } catch (err) {
    console.error('Failed to update execution status:', err)
    error.value = readServerError(err, 'Could not mark this run as Failed.')
    return
  } finally {
    saving.value = false
  }
  await applyWorkflowChain(
    ['Complete Experiment', 'Send For Approval'],
    'Marked as Failed (no sample) and sent for approval.'
  )
}


const sampleError = ref('')

const getDocstatusLabel = (statusNum) => {
  if (statusNum === 0) return 'Draft'
  if (statusNum === 1) return 'Submitted'
  if (statusNum === 2) return 'Cancelled'
  return 'Unknown'
}


const GENERATION_API = 'elab_notebook.elab_notebook.api.generation'

const generationCtx = ref(null)
const loadingGeneration = ref(false)

const loadGenerationContext = async () => {
  if (!route.params.id) return
  loadingGeneration.value = true
  try {
    const res = await axios.get(`/api/method/${GENERATION_API}.get_generation_context`, {
      params: { experiment_name: route.params.id }
    })
    generationCtx.value = res.data.message || null
  } catch (err) {
    console.error('Failed to load generation context', err)
    generationCtx.value = null
  } finally {
    loadingGeneration.value = false
  }
}


const SAMPLE_ALLOWED_RUN_STATES = ['In Progress', 'Completed', 'Edit Completed']

const runAcceptsSamples = () =>
  SAMPLE_ALLOWED_RUN_STATES.includes(experiment.value?.workflow_state || '')


const showSampleModal = ref(false)
const savingSample = ref(false)
const sampleFormError = ref('')
const newSample = ref({ item: '', qty: 1, name_of_sample: '', comments: '', uom: '' })
const SAMPLE_EXTRA_FIELDS = [
  'sample',
  'batch_no',
  'sample_detailsstage',
  'test_to_be_performed',
  'sample_vol',
  'warehouse',
  'location',
  'sampling_date',
  'date_of_analysis',
  'results',
  'remarks'
]


const canAddSample = () => {
  const c = generationCtx.value
  return Boolean(c && c.can_create_sample && runAcceptsSamples())
}

const addSampleReason = () => {
  const c = generationCtx.value
  if (!c) return 'Loading…'
  if (!runAcceptsSamples()) {
    const state = experiment.value?.workflow_state || 'Start'


    if (state === 'Start') {
      return 'This run has not started. Start the run first — samples can be added from In Progress onwards.'
    }
    return `This run is ${state}, and samples can no longer be written against it. `
      + 'Samples must be added before it is approved.'
  }
  if (!c.can_create_sample) return 'You do not have permission to create Samples.'
  return 'Add as many samples as this run produced — there is no limit.'
}


const emptySample = () => ({
  item: '',
  qty: 1,
  uom: '',
  name_of_sample: '',
  comments: '',
  sample: '',
  batch_no: '',
  sample_detailsstage: '',
  test_to_be_performed: '',
  sample_vol: '',
  warehouse: '',
  location: '',
  sampling_date: '',
  date_of_analysis: '',
  results: '',
  remarks: ''
})

const openSampleModal = () => {
  sampleFormError.value = ''
  newSample.value = emptySample()
  sampleItemSearch.value = ''
  sampleNameMirrored.value = false
  showSampleModal.value = true
}


const onSampleItem = (opt) => {
  newSample.value.uom = opt ? opt.stock_uom || '' : ''
  if (opt && !newSample.value.name_of_sample) newSample.value.name_of_sample = opt.item_name || ''
}


const sampleItemSearch = ref('')


const sampleNameMirrored = ref(false)

const onSampleItemSearch = (text) => {
  const typed = (text || '').trim()
  sampleItemSearch.value = text || ''


  if (newSample.value.item) return
  if (!newSample.value.name_of_sample || sampleNameMirrored.value) {
    newSample.value.name_of_sample = typed
    sampleNameMirrored.value = Boolean(typed)
  }
}


const onSampleNameInput = () => {
  sampleNameMirrored.value = false
}


const effectiveSampleName = computed(
  () => (newSample.value.name_of_sample || '').trim() || sampleItemSearch.value.trim()
)


const canSubmitSample = computed(
  () => Boolean(newSample.value.item || effectiveSampleName.value) && newSample.value.qty > 0
)

const submitSampleForm = async () => {
  if (!newSample.value.item) {
    sampleFormError.value = 'Pick the item this sample is of.'
    return
  }
  if (!(newSample.value.qty > 0)) {
    sampleFormError.value = 'Quantity must be greater than zero.'
    return
  }
  savingSample.value = true
  sampleFormError.value = ''
  try {
    await axios.post(`/api/method/${GENERATION_API}.add_sample`, {
      experiment_name: route.params.id,


      item: newSample.value.item || null,
      qty: newSample.value.qty,
      name_of_sample: effectiveSampleName.value || null,
      uom: newSample.value.uom || null,
      comments: newSample.value.comments || null,


      extra: JSON.stringify(
        Object.fromEntries(
          SAMPLE_EXTRA_FIELDS.map((f) => [f, newSample.value[f] || null]).filter(([, v]) => v)
        )
      )
    })
    showSampleModal.value = false
    await Promise.all([loadSamples(), loadGenerationContext()])
  } catch (err) {
    console.error('Failed to add sample', err)
    sampleFormError.value = readServerError(err, 'Could not add this sample.')
  } finally {
    savingSample.value = false
  }
}


const canCreateStockEntry = () => {
  const c = generationCtx.value
  return Boolean(
    c && !c.stock_entry && c.material_row_count > 0 && c.can_create_stock_entry
  )
}

const stockEntryReason = () => {
  const c = generationCtx.value
  if (!c) return 'Loading…'
  if (c.stock_entry) return ''
  if (!c.material_row_count) {
    return 'No Material Required rows on this run, so there is no stock to issue.'
  }
  if (!c.can_create_stock_entry) return 'You do not have permission to create Stock Entries.'
  return `Opens a Stock Entry prefilled with ${c.material_row_count} material `
    + `line${c.material_row_count === 1 ? '' : 's'} — pick the warehouse there and save.`
}


const openStockEntryForm = () => {
  const url = deskUrl('/app/stock-entry/new', { elab_experiment: route.params.id })
  window.open(url, '_blank', 'noopener')
}


const deskStockEntryUrl = (name) => deskUrl(`/app/stock-entry/${encodeURIComponent(name)}`)


const openSample = (sample) => {
  router.push(`/samples/${encodeURIComponent(sample.name)}`)
}


const canEditSample = () => {
  if (!experiment.value) return false
  const state = experiment.value.workflow_state || ''
  const s = state.toLowerCase()
  return s.includes('running') || s.includes('completed')
}


const SAMPLE_LOCKED_PARENT_STATES = ['Sent for Approval', 'Approved', 'Rejected']

const isSampleLocked = () => {
  if (!experiment.value) return false
  const state = (experiment.value.workflow_state || '').trim().toLowerCase()
  return SAMPLE_LOCKED_PARENT_STATES.some((s) => s.toLowerCase() === state)
}

watch(activeTab, (newTab) => {
  if (newTab === 'samples') {
    loadSamples()
  }


  if (newTab !== (route.query.tab || 'general')) {
    router.replace({ query: { ...route.query, tab: newTab === 'general' ? undefined : newTab } })
  }
})


const MERGED_TABS = { equipment: 'materials', methodology: 'details' }

const applyTabFromRoute = () => {
  const wanted = String(route.query.tab || '')
  const resolved = MERGED_TABS[wanted] || wanted
  activeTab.value = TAB_KEYS.includes(resolved) ? resolved : 'general'
}


watch([usesTemplate, activeTab], ([leaf, tab]) => {
  if (!leaf && TEMPLATE_TABS.includes(tab)) activeTab.value = 'general'
})


watch([() => experiment.value?.experiment_category, activeTab], ([category, tab]) => {
  if (tab === 'rawdata' && !showsRawDataTab(category)) activeTab.value = 'general'
  if (tab === 'report' && !showsReportTab(category)) activeTab.value = 'general'
})


const loadEverything = async () => {


  await loadExperiment()


  loadGenerationContext()


  loadTeamName()
  loadHistory()
  loadSamples()
}


watch(
  () => route.params.id,
  (next, previous) => {
    if (!next || next === previous) return


    experiment.value = null
    samplesList.value = []
    historyList.value = []
    commentDrafts.value = {}
    commentsNotice.value = ''
    error.value = ''
    successMessage.value = ''
    applyTabFromRoute()
    loadEverything()
  }
)

onMounted(() => {
  applyTabFromRoute()
  loadCategoryOptions()
  loadEverything()
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
        <!-- Runs made before the title was asked for carry none, and an empty
             h1 reads as a broken page - the Aim says what the run is about, and
             the id is always there. -->
        <h1 class="page-title">{{ experiment.title || experiment.aim || route.params.id }}</h1>
        <p class="page-subtitle">
          Status:
          <span
            class="workflow-state-badge"
            :class="getWorkflowStateClass(experiment.workflow_state)"
          >
            {{ experiment.workflow_state || 'Start' }}
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
          <!-- Only the transitions the run action bar does not drive itself, so
               Start / Complete & Send for Approval never appear twice and the
               workflow's own "Save" action cannot be mistaken for saving edits. -->
          <button
            v-for="act in headerWorkflowActions"
            :key="act.action"
            class="btn btn-workflow btn-sm"
            :class="getWorkflowActionClass(act.action)"
            @click="runWorkflowAction(act.action)"
            :disabled="runningWorkflowAction"
          >
            {{ act.action }}
          </button>
        </template>
        <!-- Root level only, and only here rather than on the create form: the
             run this starts names the record on screen as its parent, which
             needs a saved name to point at. The label is the level below rather
             than a fixed string, so it stays right if the levels are renamed. -->
        <button
          v-if="canStartChildRun"
          class="btn btn-primary"
          @click="startChildRun"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="btn-icon-svg"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Create {{ childCategory }}
        </button>
        <button class="btn btn-secondary" @click="router.push('/experiments')">Back to List</button>
      </div>

      <!-- Run actions live in the header card rather than a second card below it:
           the status badges above already say which state the run is in, so a
           separate bar repeated that and cost a whole card of vertical space. -->
      <div class="run-actions-row">
        <p class="run-actions-hint">
          <template v-if="isDraft">Every tab is readable now — start the run to edit them. The hierarchy stays editable until this run is Approved.</template>
          <template v-else-if="isRunning">Edit any tab and Save as often as you like — come back over as many days as the work takes.</template>
          <template v-else-if="isWorkflowLocked()">This run is {{ experiment.workflow_state }} and is no longer editable.</template>
          <template v-else>Awaiting approval. The run stays editable until a System Manager approves it.</template>
        </p>
        <div class="run-actions">
          <button
            class="btn btn-sm btn-secondary"
            :disabled="saving || (isWorkflowLocked() && !isSystemManager)"
            @click="updateExperiment"
          >
            {{ saving ? 'Saving...' : 'Save' }}
          </button>

          <button v-if="isDraft" class="btn btn-sm btn-primary" :disabled="runningWorkflowAction" @click="startRun">
            {{ runningWorkflowAction ? 'Starting...' : 'Start' }}
          </button>

          <!-- The only Create Stock Entry control on the page. Not inside the
               isRunning block below: the status gate is off, so the run's stage
               is not what decides whether this shows.

               One per run, so once `stock_entry` is set this disappears outright
               rather than turning into a link - the entry is reachable from the
               Material Consumption card, and a header control that cannot do
               anything is just something else to read. `generationCtx` being
               null means the answer has not arrived; the button stays visible
               but canCreateStockEntry() holds it disabled until it does. -->
          <span
            v-if="!(generationCtx && generationCtx.stock_entry)"
            :title="stockEntryReason()"
          >
            <button
              class="btn btn-sm btn-secondary"
              :disabled="!canCreateStockEntry()"
              @click="openStockEntryForm"
            >
              + Create Stock Entry
            </button>
          </span>

          <!-- The only Add Sample control on the page. Outside the isRunning
               block on purpose: Sample accepts Completed and Pending Approval
               too, and leaving it in there meant a run in either of those states
               offered no way to add one. canAddSample() carries the real rule
               and disables it with a reason everywhere else. -->
          <span :title="addSampleReason()">
            <button class="btn btn-sm btn-success" :disabled="!canAddSample()" @click="openSampleModal">
              Add Sample
            </button>
          </span>

          <template v-if="isRunning">
            <button
              class="btn btn-sm btn-danger"
              :disabled="saving || runningWorkflowAction"
              @click="markFailedNoSample"
            >
              Mark as Failed - No Sample
            </button>
            <button class="btn btn-sm btn-primary" :disabled="runningWorkflowAction" @click="completeAndSendForApproval">
              Complete &amp; Send for Approval
            </button>
          </template>
        </div>
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

    <!-- Run action bar. It sits ABOVE the tabs rather than replacing them: the
         old Yes/No outcome gate was the tabs' v-if counterpart, so an in-progress
         run had nothing on screen to edit and the only ways out both ended the
         run. Lab work spans days, so the run stays open and editable and only an
         explicit action closes it. -->
    <!-- Tabs render in every state, Draft included. Draft used to swap the whole
         row out for a standalone Experiment Tree card, which left a freshly
         created run with no way to reach its own Template, Details or Report.
         The panes are views bound to `experiment`; what Draft gates is editing,
         and that is the Save button's business, not the tab row's.

         The `experiment` guard stays: the panes below dereference it directly,
         and one TypeError there takes down the whole app render. -->
    <div v-if="experiment" class="detail-layout card">
      <!-- Tabs. Material Required, Equipment Details, Methodology and Protocol
           Steps appear only on a Sub Sub Experiment - see visibleTabs. -->
      <div class="form-tabs-row">
        <button
          v-for="tab in visibleTabs"
          :key="tab.key"
          class="tab-btn"
          :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Tab Content panes -->
      <div class="tab-content">
        <!-- 1. GENERAL TAB -->
        <div v-if="activeTab === 'general'" class="tab-pane">
          <div class="pane-grid">
            <!-- First, because it is the most identifying thing about a run and
                 was missing entirely: the level decides which tabs exist, whether
                 a template applies and what may sit under it. Paired with the
                 parent, since "which level" and "under what" are one question -
                 a Master Experiment is the only level with no answer to the
                 second half. -->
            <div class="form-group-row">
              <div class="form-group">
                <label class="form-label">Experiment Category</label>
                <input
                  type="text"
                  :value="experiment.experiment_category || '—'"
                  class="form-control readonly"
                  readonly
                />
                <span class="field-hint">Fixed when the run was created.</span>
              </div>
              <div class="form-group">
                <label class="form-label">Parent Experiment</label>
                <RouterLink
                  v-if="experiment.parent_experiment"
                  :to="`/experiments/${encodeURIComponent(experiment.parent_experiment)}`"
                  class="form-control link-value"
                  :title="`Open ${experiment.parent_experiment}`"
                >
                  <span class="link-value-text">{{ experiment.parent_experiment }}</span>
                  <svg class="link-value-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                </RouterLink>
                <input
                  v-else
                  type="text"
                  value="None — this is a top-level run"
                  class="form-control readonly"
                  readonly
                />
              </div>
            </div>

            <div class="form-group-row">
              <div class="form-group">
                <label class="form-label">Experiment Team</label>
                <!-- RouterLink, not an <a href> to the desk: this is an in-app
                     route now, and a plain href would tear the whole SPA down
                     and reload it. Still renders a real href, so middle-click
                     and open-in-new-tab keep working. The external-link icon is
                     gone with the external link. -->
                <RouterLink
                  v-if="experiment.experiment_team"
                  :to="teamRoute"
                  class="form-control link-value"
                  :title="`Open ${experiment.experiment_team}`"
                >
                  <!-- Name first, id second - the same label the create form's
                       picker uses. Teams made before team_name existed have
                       none, and then the id stands on its own. -->
                  <span class="link-value-text">{{ teamLabel }}</span>
                  <svg class="link-value-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                </RouterLink>
                <input v-else type="text" value="None" class="form-control readonly" readonly />
              </div>
              <div class="form-group">
                <label class="form-label">Project</label>
                <input type="text" :value="experiment.project" class="form-control readonly" readonly />
              </div>
            </div>

            <!-- Legacy runs only: their id was built from a notebook, so the
                 link is still meaningful. Hidden entirely on newer runs. -->
            <div v-if="experiment.elab_notebook" class="form-group-row">
              <div class="form-group">
                <label class="form-label">ELab Notebook</label>
                <a
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

            <div class="form-group-row">
              <!-- Editable here rather than only on the create form: a run almost
                   never knows its last day on its first, so this is where the end
                   date actually gets set. Saved by the Save button above. -->
              <div class="form-group">
                <label class="form-label">End Date</label>
                <input
                  type="date"
                  v-model="experiment.experiment_end_date"
                  :min="experiment.experiment_start_date || undefined"
                  class="form-control"
                  :disabled="isWorkflowLocked() && !isSystemManager"
                  @click="openDatePicker"
                  @focus="openDatePicker"
                />
                <span class="field-hint">Click the field to pick a date, then Save.</span>
              </div>
              <!-- The account this run is filed under, written by Frappe on
                   insert and never by the client. -->
              <div class="form-group">
                <label class="form-label">Created By</label>
                <input type="text" :value="experiment.owner || '—'" class="form-control readonly" readonly />
              </div>
            </div>

          </div>
        </div>

        <!-- DETAILS TAB -->
        <!-- The run's write-up, split out of Template so that tab carries the
             run's setup alone. Observation lives here now rather than in a tab of
             its own - it is the other half of what Aim asked. -->
        <div v-if="activeTab === 'details'" class="tab-pane">
          <div v-if="isWorkflowLocked() && !isSystemManager" class="info-banner" style="background-color: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: var(--fs-md); color: #F59E0B;">
            ⚠️ This experiment is locked. Only System Managers can edit observations in this state.
          </div>
          <div class="pane-grid">
            <!-- The run's own title, editable here because it is the one part of
                 the write-up that is a label rather than a finding - it is what
                 the record header prints. Saved by the Save button above. -->
            <div class="form-group-row">
              <div class="form-group">
                <label class="form-label">Experiment Title</label>
                <input
                  type="text"
                  v-model="experiment.title"
                  class="form-control"
                  placeholder="What this run is called…"
                  :disabled="isWorkflowLocked() && !isSystemManager"
                />
              </div>
              <!-- Stamped from the creator's Employee record at insert and fixed
                   afterwards (LabExperiment.validate_creator_identity_locked). -->
              <div class="form-group">
                <label class="form-label">Employee ID (Creator)</label>
                <input
                  type="text"
                  :value="experiment.employee_code || '—'"
                  class="form-control readonly"
                  readonly
                />
                <span class="field-hint">{{ experiment.employee_name || '—' }}</span>
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

            <!-- The run's own step list, bound to `protocol_steps`. Not the same
                 table as the Procedure tab's Execution Checklist, which reads
                 `experiment_protocol_steps` - that one is the template's planned
                 protocol, cloned in and never edited here. Both stay optional:
                 nothing on the server reads either of these tables. -->
            <section class="meta-card">
              <h3 class="pane-subtitle">Protocol Steps</h3>
              <div class="table-container">
                <table>
                  <thead>
                    <tr>
                      <th style="width: 4rem">No.</th>
                      <th>Instructions</th>
                      <th style="width: 9rem">Expected Duration</th>
                      <th style="width: 6rem">Critical</th>
                      <th>Attachment</th>
                      <th class="actions-col"></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(step, idx) in experiment.protocol_steps" :key="idx">
                      <!-- Positional, like the Observation table below it. The
                           typed step_no had nothing keeping it honest: an old row
                           with no value read as blank, and deleting row 2 of four
                           left 1, 3, 4. renumberProtocolSteps keeps the stored
                           step_no equal to what is shown here. -->
                      <td class="text-center">{{ idx + 1 }}</td>
                      <td>
                        <input
                          type="text"
                          v-model="step.instruction"
                          class="form-control table-input"
                          placeholder="What to do at this step…"
                          :disabled="isWorkflowLocked() && !isSystemManager"
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          v-model="step.expected_duration"
                          class="form-control table-input"
                          min="0"
                          placeholder="seconds"
                          :disabled="isWorkflowLocked() && !isSystemManager"
                        />
                      </td>
                      <td class="text-center">
                        <input
                          type="checkbox"
                          v-model="step.is_critical"
                          :true-value="1"
                          :false-value="0"
                          :disabled="isWorkflowLocked() && !isSystemManager"
                        />
                      </td>
                      <!-- Same shape as the Raw Data tab's attachment rows: this
                           SPA uploads through Frappe's own upload_file, the same
                           call the rich-text editor's attach button makes. The
                           bound value is still the stored file_url, so a path
                           entered before this control existed still renders. -->
                      <td>
                        <FileAttachment
                          v-model="step.attachment"
                          :disabled="isWorkflowLocked() && !isSystemManager"
                        />
                      </td>
                      <td>
                        <button
                          class="delete-row-btn"
                          @click="removeProtocolStep(idx)"
                          :disabled="isWorkflowLocked() && !isSystemManager"
                          :title="isWorkflowLocked() && !isSystemManager ? 'Locked in this workflow state' : 'Delete step'"
                        >×</button>
                      </td>
                    </tr>
                    <tr v-if="!experiment.protocol_steps || experiment.protocol_steps.length === 0">
                      <td colspan="6" class="empty-table-cell">No Data</td>
                    </tr>
                    <tr class="add-row-tr">
                      <td colspan="6">
                        <AddRow
                          label="Add Step"
                          :disabled="isWorkflowLocked() && !isSystemManager"
                          @add="addProtocolStep"
                        />
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            <!-- Parameters measured during or after the run, bound to
                 `observations`. Description is the child's `observation` field -
                 a Text Editor on the doctype, kept as a plain textarea here so a
                 grid row does not sprout a toolbar. -->
            <section class="meta-card">
              <h3 class="pane-subtitle">Observation Table</h3>
              <div class="table-container">
                <table>
                  <thead>
                    <tr>
                      <th style="width: 4rem">No.</th>
                      <th>Parameter</th>
                      <th style="width: 7rem">Unit</th>
                      <th style="width: 10rem">Expected Range</th>
                      <th>Remarks</th>
                      <th class="actions-col"></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(obs, idx) in experiment.observations" :key="idx">
                      <!-- Row number is positional, like the doctype grid's own
                           idx - there is no No. column on this child table. -->
                      <td class="text-center">{{ idx + 1 }}</td>
                      <td>
                        <input
                          type="text"
                          v-model="obs.parameter"
                          class="form-control table-input"
                          placeholder="e.g. Temperature"
                          :disabled="isWorkflowLocked() && !isSystemManager"
                        />
                      </td>
                      <td>
                        <input
                          type="text"
                          v-model="obs.unit"
                          class="form-control table-input"
                          placeholder="e.g. °C"
                          :disabled="isWorkflowLocked() && !isSystemManager"
                        />
                      </td>
                      <td>
                        <input
                          type="text"
                          v-model="obs.expected_range"
                          class="form-control table-input"
                          placeholder="e.g. 20–25"
                          :disabled="isWorkflowLocked() && !isSystemManager"
                        />
                      </td>
                      <td>
                        <input
                          type="text"
                          v-model="obs.remarks"
                          class="form-control table-input"
                          placeholder="Short note…"
                          :disabled="isWorkflowLocked() && !isSystemManager"
                        />
                      </td>
                      <td>
                        <button
                          class="delete-row-btn"
                          @click="removeObservationRow(idx)"
                          :disabled="isWorkflowLocked() && !isSystemManager"
                          :title="isWorkflowLocked() && !isSystemManager ? 'Locked in this workflow state' : 'Delete observation'"
                        >×</button>
                      </td>
                    </tr>
                    <tr v-if="!experiment.observations || experiment.observations.length === 0">
                      <td colspan="6" class="empty-table-cell">No Data</td>
                    </tr>
                    <tr class="add-row-tr">
                      <td colspan="6">
                        <AddRow
                          label="Add Observation"
                          :disabled="isWorkflowLocked() && !isSystemManager"
                          @add="addObservationRow"
                        />
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            <!-- Overall written observation for the whole run, kept apart from
                 the per-row notes above. Bound to Lab Experiment's own
                 `observation` Text Editor, which already existed and is already
                 fetched from the template - so no observation_summary field was
                 added; a second top-level field would have meant two places to
                 write the same thing. -->
            <section class="meta-card">
              <h3 class="pane-subtitle">Observation</h3>
              <div class="form-group stacked-field">
                <RichTextEditor v-model="experiment.observation" placeholder="Enter observations…" tables :readonly="isWorkflowLocked() && !isSystemManager" />
              </div>
            </section>

          </div>
        </div>

        <!-- MATERIALS TAB (EDITABLE with delete) -->
        <div v-if="activeTab === 'materials'" class="tab-pane">
          <div v-if="isWorkflowLocked() && !isSystemManager" class="info-banner" style="background-color: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: var(--fs-md); color: #F59E0B;">
            ⚠️ This experiment is locked. Only System Managers can edit materials in this state.
          </div>
          <div class="pane-header-row">
            <h3 class="pane-subtitle">Formulation Ingredients</h3>
          </div>
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
                  <!-- Imported rows stay read-only text; a row the user added gets
                       a real Item picker, otherwise it could never be filled in. -->
                  <td v-if="isImportedRow(mat)" class="font-mono text-accent">{{ mat.item_code }}</td>
                  <td v-else>
                    <LinkField
                      v-model="mat.item_code"
                      doctype="Item"
                      :fields="['item_name', 'stock_uom']"
                      :search-fields="['name', 'item_name']"
                      description-field="item_name"
                      placeholder="Search item..."
                      input-class="form-control table-input"
                      :disabled="isWorkflowLocked() && !isSystemManager"
                      @select="(item) => onMaterialItemSelect(mat, item)"
                    />
                  </td>
                  <td v-if="isImportedRow(mat)">{{ mat.item_name }}</td>
                  <td v-else><input type="text" v-model="mat.item_name" class="form-control table-input" placeholder="Item description" :disabled="isWorkflowLocked() && !isSystemManager" /></td>
                  <td v-if="isImportedRow(mat)">{{ mat.uom }}</td>
                  <td v-else><input type="text" v-model="mat.uom" class="form-control table-input" placeholder="e.g. Nos" :disabled="isWorkflowLocked() && !isSystemManager" /></td>
                  <td><input type="number" v-model="mat.qty" class="form-control table-input" min="0" :disabled="isImportedRow(mat) || (isWorkflowLocked() && !isSystemManager)" :class="{ readonly: isImportedRow(mat) }" /></td>
                  <td>
                    <button v-if="!isImportedRow(mat)" class="delete-row-btn" @click="removeMaterial(idx)" :disabled="isWorkflowLocked() && !isSystemManager" :title="isWorkflowLocked() && !isSystemManager ? 'Locked in this workflow state' : 'Delete material'">×</button>
                    <span v-else class="imported-row-lock" title="Imported from the Experiment Template - read-only and cannot be deleted">&#128274;</span>
                  </td>
                </tr>
                <tr v-if="!experiment.material_required || experiment.material_required.length === 0">
                  <td colspan="5" class="empty-table-cell">No materials required for this run.</td>
                </tr>
                <tr class="add-row-tr">
                  <td colspan="5"><AddRow label="Add Material" :disabled="isWorkflowLocked() && !isSystemManager" @add="addMaterial" /></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 3. EQUIPMENT — the second half of the Material & Equipment tab.
             Shares the tab key with the materials pane above so the two stack,
             rather than being folded into that pane's markup: the banner and
             table below are untouched, only what reveals them changed. -->
        <div v-if="activeTab === 'materials'" class="tab-pane">
          <div v-if="isWorkflowLocked() && !isSystemManager" class="info-banner" style="background-color: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: var(--fs-md); color: #F59E0B;">
            ⚠️ This experiment is locked. Only System Managers can edit equipment in this state.
          </div>
          <div class="pane-header-row">
            <h3 class="pane-subtitle">Instruments & Tool Allocation</h3>
          </div>
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
                  <td><input type="text" v-model="eq.equipment_name" class="form-control table-input" placeholder="e.g. HPLC Machine" :disabled="isImportedRow(eq) || (isWorkflowLocked() && !isSystemManager)" :class="{ readonly: isImportedRow(eq) }" /></td>
                  <td class="font-mono"><input type="text" v-model="eq.equipment_id" class="form-control table-input" placeholder="e.g. HPLC-001" :disabled="isImportedRow(eq) || (isWorkflowLocked() && !isSystemManager)" :class="{ readonly: isImportedRow(eq) }" /></td>
                  <td><input type="text" v-model="eq.remarks" class="form-control table-input" placeholder="e.g. Reserved for 9am session" :disabled="isImportedRow(eq) || (isWorkflowLocked() && !isSystemManager)" :class="{ readonly: isImportedRow(eq) }" /></td>
                  <td>
                    <button v-if="!isImportedRow(eq)" class="delete-row-btn" @click="removeEquipment(idx)" :disabled="isWorkflowLocked() && !isSystemManager" :title="isWorkflowLocked() && !isSystemManager ? 'Locked in this workflow state' : 'Delete equipment'">×</button>
                    <span v-else class="imported-row-lock" title="Imported from the Experiment Template - read-only and cannot be deleted">&#128274;</span>
                  </td>
                </tr>
                <tr v-if="!experiment.equipment_details || experiment.equipment_details.length === 0">
                  <td colspan="4" class="empty-table-cell">No equipment allocated.</td>
                </tr>
                <tr class="add-row-tr">
                  <td colspan="4"><AddRow label="Add Equipment" :disabled="isWorkflowLocked() && !isSystemManager" @add="addEquipment" /></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 4. METHODOLOGY TAB (EDITABLE) -->
        <!-- Methodology — now the last section of the Details tab. Same key as
             the Details panes above so it stacks under them; the pane's own
             contents are unchanged.
             `usesTemplate` is kept from when this was its own tab: Details shows
             at every level, and without it a Master Experiment would start
             carrying a Methodology table it has no use for. -->
        <div v-if="activeTab === 'details' && usesTemplate" class="tab-pane">
          <div v-if="isWorkflowLocked() && !isSystemManager" class="info-banner" style="background-color: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: var(--fs-md); color: #F59E0B;">
            ⚠️ This experiment is locked. Only System Managers can edit fields in this state.
          </div>
          <div class="pane-header-row">
            <h3 class="pane-subtitle">Experimental Methodology (Execution Steps)</h3>
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
                    <input type="text" v-model="meth.method" class="form-control table-input" placeholder="e.g. HPLC separation" :disabled="isImportedRow(meth) || (isWorkflowLocked() && !isSystemManager)" :class="{ readonly: isImportedRow(meth) }" />
                  </td>
                  <td>
                    <input type="number" v-model="meth.time_to_complete" class="form-control table-input" min="0" :disabled="isImportedRow(meth) || (isWorkflowLocked() && !isSystemManager)" :class="{ readonly: isImportedRow(meth) }" />
                  </td>
                  <td>
                    <button v-if="!isImportedRow(meth)" class="delete-row-btn" @click="removeMethod(idx)" :disabled="isWorkflowLocked() && !isSystemManager">×</button>
                    <span v-else class="imported-row-lock" title="Imported from the Experiment Template - read-only and cannot be deleted">&#128274;</span>
                  </td>
                </tr>
                <tr v-if="experiment.methodology.length === 0">
                  <td colspan="3" class="empty-table-cell">No methodology steps yet.</td>
                </tr>
                <tr class="add-row-tr">
                  <td colspan="3"><AddRow label="Add Method" :disabled="isWorkflowLocked() && !isSystemManager" @add="addMethod" /></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- HISTORY / AUDIT LOG TAB -->
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
                  <span style="font-weight: var(--fw-semibold); color: var(--accent);">⚡ Workflow State Changed:</span>
                  <br />
                  <span style="color: var(--text-muted);">{{ ver.workflowStateChange[1] || 'Draft' }}</span>
                  <span style="color: var(--text-muted);">→</span>
                  <span style="color: var(--success); font-weight: var(--fw-semibold);">{{ ver.workflowStateChange[2] }}</span>
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
          <!-- No Add Sample button here: there is one, in the header. The reason
               text stays, though - a header button that is greyed out says
               nothing about why, and the approved case in particular needs
               saying out loud rather than living only in a tooltip. -->
          <div class="samples-section-header">
            <h3 class="pane-section-title">Result Output Samples</h3>
          </div>
          <p v-if="generationCtx" class="field-hint" style="margin: -0.5rem 0 1.25rem">
            {{ addSampleReason() }}
          </p>

          <!-- Lock Warning -->
          <div v-if="isSampleLocked()" class="info-banner" style="background-color: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: var(--fs-md); color: #F59E0B;">
            ⚠️ Sample is locked. Only System Managers can modify samples in {{ experiment.workflow_state }} state.
          </div>

          <div v-if="loadingSamples" class="loading-state inner-load">
            <div class="spinner"></div>
            <p>Loading registered samples...</p>
          </div>

          <div v-else class="samples-list-wrapper">
            <!-- No empty state: a run with no samples yet shows the Add Sample
                 button and nothing else, rather than a card explaining that
                 nothing is there. -->
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
                <!-- Whole row opens the sample. The two action buttons in the
                     last cell stop the click themselves rather than being
                     excluded here: Submit and Cancel act on the row in place,
                     and navigating away from a row you just submitted would
                     hide the result of pressing it. -->
                <tr
                  v-for="sample in samplesList"
                  :key="sample.name"
                  class="sample-row-link"
                  :title="`Open ${sample.elab_no || sample.name}`"
                  @click="openSample(sample)"
                >
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
                  <td @click.stop>
                    <div class="row-actions" style="display: flex; gap: 0.5rem;">
                      <button
                        v-if="sample.docstatus === 0"
                        class="btn btn-sm btn-success"
                        :disabled="submittingSampleId === sample.name || (isSampleLocked() && !isSystemManager)"
                        :title="isSampleLocked() && !isSystemManager ? 'Sample is locked in this workflow state' : 'Submit sample'"
                        @click.stop="submitSample(sample)"
                        style="padding: 0.25rem 0.5rem; font-size: var(--fs-xs);"
                      >
                        {{ submittingSampleId === sample.name ? 'Submitting...' : 'Submit' }}
                      </button>
                      <button
                        v-if="sample.docstatus === 1"
                        class="btn btn-sm btn-danger"
                        :disabled="cancellingSampleId === sample.name || (isSampleLocked() && !isSystemManager)"
                        :title="isSampleLocked() && !isSystemManager ? 'Sample is locked in this workflow state' : 'Cancel sample'"
                        @click.stop="cancelSample(sample)"
                        style="padding: 0.25rem 0.5rem; font-size: var(--fs-xs);"
                      >
                        {{ cancellingSampleId === sample.name ? 'Cancelling...' : 'Cancel' }}
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>

            <!-- Comments sit below the table rather than in a column: a textarea
                 in a table cell is unusable. One block per sample, since a run
                 can now carry any number of them. -->
            <div v-if="samplesList.length > 0" class="sample-comments-wrapper">
              <div v-if="commentsNotice" class="sample-comments-notice">{{ commentsNotice }}</div>

              <section
                v-for="sample in samplesList"
                :key="`comments-${sample.name}`"
                class="sample-comments-card"
              >
                <div class="sample-comments-head">
                  <h4 class="sample-comments-title">
                    Comments
                    <span class="sample-comments-for font-mono">{{ sample.elab_no || sample.name }}</span>
                  </h4>
                  <span v-if="isCommentsLocked()" class="sample-comments-lock">Locked</span>
                </div>

                <textarea
                  class="form-control textarea"
                  :class="{ readonly: isCommentsLocked() }"
                  :value="commentDraft(sample)"
                  :readonly="isCommentsLocked()"
                  rows="3"
                  :placeholder="isCommentsLocked()
                    ? 'Comments are locked in this state.'
                    : 'Notes on this sample…'"
                  @input="setCommentDraft(sample, $event.target.value)"
                ></textarea>

                <div class="sample-comments-foot">
                  <span class="field-hint">
                    <template v-if="isCommentsLocked()">
                      Frozen because this run is {{ experiment.workflow_state }}. Comments lock
                      when the run is sent for approval — for everyone, System Managers included.
                    </template>
                    <template v-else>
                      Editable until this run is sent for approval.
                    </template>
                  </span>
                  <button
                    v-if="!isCommentsLocked()"
                    class="btn btn-secondary btn-sm"
                    :disabled="savingCommentsFor === sample.name || !commentsDirty(sample)"
                    @click="saveSampleComments(sample)"
                  >
                    {{ savingCommentsFor === sample.name ? 'Saving…' : 'Save Comments' }}
                  </button>
                </div>
              </section>
            </div>
          </div>

          <!-- Only once the entry exists. Before that this card said nothing the
               header button was not already saying, which is what it was removed
               for; after it, this is the only way back to the entry, because the
               header control hides itself once the run has one. -->
          <section
            v-if="generationCtx && generationCtx.stock_entry"
            class="meta-card"
            style="margin-bottom: 1.25rem"
          >
            <div class="samples-section-header" style="margin-bottom: 0.5rem">
              <h3 class="pane-subtitle">Material Consumption</h3>
              <a
                :href="deskStockEntryUrl(generationCtx.stock_entry)"
                target="_blank"
                rel="noopener"
                class="btn btn-secondary"
              >
                {{ generationCtx.stock_entry }}
              </a>
            </div>
            <p class="field-hint" style="margin: 0">
              Raised as a draft — submit it from the desk to move stock. One per run,
              so this cannot be raised again.
            </p>
          </section>
        </div>

        <!-- EXPERIMENT HIERARCHY TAB -->
        <div v-if="activeTab === 'tree'" class="tab-pane">
          <ExperimentTree :experiment-id="String(route.params.id)" />

          <!-- Below the real tree, not inside it: the tree above shows the
               hierarchy as it is, this picks which parts of it to present.
               Absent at Sub Sub Experiment - the leaf has no children to pick.
               Heading only, no explanatory paragraph: the column header names
               the level, and the empty row says what an empty table means. -->
          <section v-if="showsCuratedChildren" class="meta-card" style="margin-top: 1.25rem">
            <h3 class="pane-subtitle" style="margin-bottom: 0.75rem">Experiment Table</h3>

            <div v-if="isWorkflowLocked() && !isSystemManager" class="info-banner" style="background-color: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: var(--fs-md); color: #F59E0B;">
              ⚠️ This experiment is locked. Only System Managers can change this list.
            </div>

            <div class="table-container">
              <table class="samples-table">
                <thead>
                  <tr>
                    <th style="width: 45%">{{ childCategory }}</th>
                    <th>Title</th>
                    <th style="width: 60px"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(row, idx) in (experiment.successful_children || [])"
                    :key="`curated-${idx}`"
                  >
                    <td>
                      <LinkField
                        v-model="row.linked_experiment"
                        doctype="Lab Experiment"
                        :fields="['title', 'experiment_category']"
                        :search-fields="['name', 'title']"
                        description-field="title"
                        :filters="curatedChildFilters"
                        :disabled="isWorkflowLocked() && !isSystemManager"
                        :placeholder="`Search ${childCategory} runs…`"
                        input-class="form-control table-input"
                        @select="onCuratedChildSelect(row, $event)"
                      />
                    </td>
                    <td>
                      <!-- Read-only: it mirrors the linked run's own title, and a
                           second editable copy would be a second place to change
                           a name that lives somewhere else. -->
                      <input
                        type="text"
                        :value="row.linked_experiment_title || '—'"
                        class="form-control table-input readonly"
                        readonly
                      />
                    </td>
                    <td>
                      <button
                        class="delete-row-btn"
                        title="Remove from the list"
                        :disabled="isWorkflowLocked() && !isSystemManager"
                        @click="removeCuratedChild(idx)"
                      >×</button>
                    </td>
                  </tr>
                  <tr v-if="!(experiment.successful_children || []).length">
                    <td colspan="3" class="empty-table-cell">
                      Nothing picked — the report uses the full hierarchy.
                    </td>
                  </tr>
                  <tr class="add-row-tr">
                    <td colspan="3">
                      <AddRow
                        :label="`Add ${childCategory}`"
                        :disabled="isWorkflowLocked() && !isSystemManager"
                        @add="addCuratedChild"
                      />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <!-- REPORT TAB -->
        <!-- Editable while the run is; the same lock the Save button obeys. -->
        <div v-if="activeTab === 'rawdata'" class="tab-pane">
          <RawDataTab
            :experiment="experiment"
            :readonly="isWorkflowLocked() && !isSystemManager"
          />
        </div>

        <!-- RESULT TAB -->
        <!-- Editable under the same lock as the rest of the run, and saved by
             the page's own Save button: the PUT sends `experiment` whole, so
             these four need no wiring of their own. The three write-ups are
             descriptive prose, empty until someone fills them in. -->
        <div v-if="activeTab === 'result'" class="tab-pane result-pane">
          <div v-if="isWorkflowLocked() && !isSystemManager" class="info-banner" style="background-color: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 6px; padding: 0.75rem 1rem; font-size: var(--fs-md); color: #F59E0B;">
            ⚠️ This experiment is locked. Only System Managers can edit the result in this state.
          </div>

          <!-- The only three editors in the app with `tables` on. They are also
               the only three fields marked read_only on the doctype, and the two
               go together: quill-better-table's markup does not survive a plain
               Quill 2, which is what the desk Text Editor is, so a field edited
               here must not be re-savable from the desk. Turning `tables` on for
               a fourth field means marking that field read_only too. -->
          <section class="meta-card">
            <h3 class="pane-subtitle">Results</h3>
            <div class="form-group stacked-field">
              <RichTextEditor
                v-model="experiment.results"
                placeholder="Describe what the run produced…"
                min-height="200px"
                tables
                :readonly="isWorkflowLocked() && !isSystemManager"
              />
            </div>
          </section>

          <section class="meta-card">
            <h3 class="pane-subtitle">Observation</h3>
            <div class="form-group stacked-field">
              <RichTextEditor
                v-model="experiment.observation_and_conclusion"
                placeholder="Describe what was observed…"
                tables
                :readonly="isWorkflowLocked() && !isSystemManager"
              />
            </div>
          </section>

          <section class="meta-card">
            <h3 class="pane-subtitle">Conclusion</h3>
            <div class="form-group stacked-field">
              <RichTextEditor
                v-model="experiment.conclusion"
                placeholder="What the run concludes…"
                tables
                :readonly="isWorkflowLocked() && !isSystemManager"
              />
            </div>
          </section>

          <section class="meta-card">
            <div class="form-group">
              <label class="form-label">Result</label>
              <select
                v-model="experiment.result"
                class="form-control"
                :disabled="isWorkflowLocked() && !isSystemManager"
              >
                <option value="">Not decided yet</option>
                <option value="Pass">Pass</option>
                <option value="Fail">Fail</option>
              </select>
            </div>
          </section>
        </div>

        <div v-if="activeTab === 'report'" class="tab-pane">
          <ExperimentReport :experiment-id="String(route.params.id)" />
        </div>
      </div>
    </div>

    <!-- 8. Register Sample Modal Dialog -->
    <!-- Generate Samples + Stock Entry. Replaces the old one-at-a-time Register
         Sample modal: samples now come from the run's own Sample rows, so there
    <!-- Add Sample. Repeatable: opens empty every time and closes on success, so
         pressing it again is the whole "add another" flow. Sample's mandatory
         fields are item and qty; name and comments are optional and uom is
         read_only, fetched from the item server-side. -->
    <div v-if="showSampleModal && experiment" class="modal-overlay" @click.self="showSampleModal = false">
      <div class="modal-content sample-modal">
        <div class="modal-header">
          <h3>Add Sample</h3>
          <button class="modal-close-btn" @click="showSampleModal = false">×</button>
        </div>

        <div class="modal-body">
          <div v-if="sampleFormError" class="form-error-banner" style="margin-bottom: 1rem;">
            <strong>Error:</strong> {{ sampleFormError }}
            <button class="form-error-close" @click="sampleFormError = ''">×</button>
          </div>

          <div class="form-group">
            <label class="form-label">Item</label>
            <LinkField
              v-model="newSample.item"
              doctype="Item"
              :fields="['item_name', 'stock_uom']"
              :search-fields="['name', 'item_name']"
              description-field="item_name"
              placeholder="Search items, or type a new name…"
              input-class="form-control"
              keep-typed-text
              @select="onSampleItem"
              @search="onSampleItemSearch"
            />
            <!-- No "create the Item" route on purpose: a substance this run just
                 made is not an item master record, and forcing one would mean
                 inventing an HSN/SAC code and four Item Group classifications
                 from a sample dialog. -->
            <span class="field-hint">
              <template v-if="!newSample.item && sampleItemSearch.trim()">
                No Item matches “{{ sampleItemSearch.trim() }}” — it will be kept as
                the sample's name. Nothing is added to the item master.
              </template>
              <template v-else>
                Pick an Item if this substance has one. If it does not, just type the
                name — no Item is created.
              </template>
            </span>
          </div>

          <div class="form-group-row two-columns">
            <div class="form-group">
              <label class="form-label">Quantity *</label>
              <input v-model.number="newSample.qty" type="number" min="0" step="any" class="form-control" />
            </div>
            <!-- Read-only only while an Item is picked, since the Item's stock
                 UOM is the right answer and typing over it would disagree with
                 the master. With no Item there is nothing to read it from, so it
                 becomes an ordinary field. -->
            <div class="form-group">
              <label class="form-label">UOM</label>
              <input
                v-model="newSample.uom"
                type="text"
                class="form-control"
                :class="{ readonly: !!newSample.item }"
                :readonly="!!newSample.item"
                placeholder="e.g. Nos, ml"
              />
              <span class="field-hint">
                {{ newSample.item ? 'Comes from the item.' : 'No item picked — type the unit.' }}
              </span>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Sample Name{{ newSample.item ? '' : ' *' }}</label>
            <input
              v-model="newSample.name_of_sample"
              type="text"
              class="form-control"
              placeholder="e.g. Aliquot 1"
              @input="onSampleNameInput"
            />
            <span v-if="!newSample.item" class="field-hint">
              Required when no Item is linked — this is what identifies the substance.
            </span>
          </div>

          <!-- The rest of the Sample record. Present here rather than left to a
               second trip through the desk form: everything below is known at the
               moment the sample is taken, and a dialog that captures four fields
               out of fifteen only moves the work. -->
          <h4 class="modal-subheading">Sample Details</h4>

          <div class="form-group-row two-columns">
            <div class="form-group">
              <label class="form-label">Sample ID</label>
              <input v-model="newSample.sample" type="text" class="form-control" placeholder="Lab's own identifier" />
            </div>
            <div class="form-group">
              <label class="form-label">Batch No.</label>
              <input v-model="newSample.batch_no" type="text" class="form-control" />
            </div>
          </div>

          <div class="form-group-row two-columns">
            <div class="form-group">
              <label class="form-label">Sample Details / Stage</label>
              <input v-model="newSample.sample_detailsstage" type="text" class="form-control" />
            </div>
            <div class="form-group">
              <label class="form-label">Sample Vol.</label>
              <input v-model="newSample.sample_vol" type="text" class="form-control" placeholder="(μl) X Vials (Nos)." />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Test to be Performed</label>
            <input v-model="newSample.test_to_be_performed" type="text" class="form-control" />
          </div>

          <div class="form-group-row two-columns">
            <div class="form-group">
              <label class="form-label">Warehouse</label>
              <LinkField
                v-model="newSample.warehouse"
                doctype="Warehouse"
                placeholder="Search warehouses…"
                input-class="form-control"
              />
            </div>
            <div class="form-group">
              <label class="form-label">Location</label>
              <input v-model="newSample.location" type="text" class="form-control" placeholder="Freezer, shelf, box…" />
            </div>
          </div>

          <div class="form-group-row two-columns">
            <div class="form-group">
              <label class="form-label">Sampling Date</label>
              <input v-model="newSample.sampling_date" type="date" class="form-control" />
            </div>
            <div class="form-group">
              <label class="form-label">Date of Analysis</label>
              <input v-model="newSample.date_of_analysis" type="date" class="form-control" />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Results</label>
            <input v-model="newSample.results" type="text" class="form-control" />
          </div>

          <div class="form-group">
            <label class="form-label">Remarks</label>
            <input v-model="newSample.remarks" type="text" class="form-control" />
          </div>

          <div class="form-group">
            <label class="form-label">Comments</label>
            <textarea v-model="newSample.comments" class="form-control textarea" rows="3" placeholder="Optional notes on this sample…"></textarea>
            <span class="field-hint">Editable until this run is sent for approval.</span>
          </div>
        </div>

        <div class="modal-footer">
          <button class="btn btn-secondary" @click="showSampleModal = false" :disabled="savingSample">Cancel</button>
          <button
            class="btn btn-primary"
            :disabled="savingSample || !canSubmitSample"
            @click="submitSampleForm"
          >
            {{ savingSample ? 'Adding…' : 'Add Sample' }}
          </button>
        </div>
      </div>
    </div>

    <!-- No Create Stock Entry modal any more: the entry is filled in on its own
         desk form, which is the only place the warehouse can be supplied before
         ERPNext will save it. See openStockEntryForm above. -->
  </div>
</template>
