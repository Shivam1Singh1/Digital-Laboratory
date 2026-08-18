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
import AddRow from '../common/AddRow.vue'
import { readServerError } from '../../utils/serverError'
import './ExperimentDetail.css'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const successMessage = ref('')

// Tab ids, in the order the row renders them. Also the allow-list for ?tab= -
// an unknown value falls back to Template rather than blanking the pane.
// `tree` keeps its id though it now reads "Experiment Hierarchy": links out of
// ExperimentTree carry ?tab=tree, and renaming the key would break every one.
const TAB_KEYS = [
  'general',
  'details',
  'materials',
  'equipment',
  'methodology',
  'procedure',
  'tree',
  'rawdata',
  'report',
  'samples',
  'history',
]

const activeTab = ref('general')
const experiment = ref(null)

// Only the leaf level carries template-cloned content, so its four tabs are the
// only ones that appear conditionally. Mirrors visibleTabs in ExperimentForm -
// the create and edit forms show the same set for the same record.
const TEMPLATE_TABS = ['materials', 'equipment', 'methodology', 'procedure']

const usesTemplate = computed(
  () => experiment.value?.experiment_category === 'Sub Sub Experiment'
)

// The level ordering, shipped by api/hierarchy.get_category_options rather than
// retyped here - the same source ExperimentForm reads it from. It is what tells
// this component which record is the root and what its children are called,
// without a level name being spelled out in JavaScript.
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

// The root is the level no other level adopts, and the level below it is that
// option's child_category - "Experiment", which is what the button below reads.
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

// Starting the level below is offered on the root alone for now: it is the one
// level whose Template tab carries nothing, so the header has room for it.
const canStartChildRun = computed(() => isRootExperiment.value && Boolean(childCategory.value))

// The create form's own pre-fill mechanism - the URL query it already reads on
// the team flow (see CreateExperimentModal.handleProceed). Nothing here is
// locked: every value lands in an editable field, the team included.
const startChildRun = () => {
  if (!canStartChildRun.value) return
  const query = {
    experiment_category: childCategory.value,
    // The reason this lives on the saved record and not on the create form:
    // parent_experiment is a Link, so there is nothing to point at until the
    // parent has a name.
    parent_experiment: experiment.value.name,
    project: experiment.value.project,
    employee_function: experiment.value.employee_function,
    experiment_team: experiment.value.experiment_team,
  }
  // A blank Link reaches the form as an empty string either way; leaving it out
  // keeps the URL honest about what was actually carried over.
  for (const key of Object.keys(query)) {
    if (!query[key]) delete query[key]
  }
  router.push({ path: '/experiments/new', query })
}

// Samples and History have no create-time meaning and so exist only here.
const visibleTabs = computed(() => [
  { key: 'general', label: 'Template' },
  { key: 'details', label: 'Details' },
  ...(usesTemplate.value
    ? [
        { key: 'materials', label: 'Material Required' },
        { key: 'equipment', label: 'Equipment Details' },
        { key: 'methodology', label: 'Methodology' },
        { key: 'procedure', label: 'Protocol Steps' },
      ]
    : []),
  { key: 'tree', label: 'Experiment Hierarchy' },
  // Hidden on a Master Experiment - utils/rawData.js mirrors the doctype's own
  // depends_on so this form and the create form hide the same thing.
  ...(showsRawDataTab(experiment.value?.experiment_category)
    ? [{ key: 'rawdata', label: 'Raw Data' }]
    : []),
  { key: 'report', label: 'Report' },
  { key: 'samples', label: 'Samples' },
  { key: 'history', label: 'History/Audit Log' },
])

// The experiment's id is generated from its team, so the team is the natural
// parent to jump to. The desk form is the target because /elab-notebook/:id in
// this app is the team *setup* page, not a record view.
const teamUrl = computed(() =>
  experiment.value?.experiment_team
    ? `/app/experiment-team/${encodeURIComponent(experiment.value.experiment_team)}`
    : ''
)

// The team's own name. It is not on the run - only the link is - so it is read
// once per record and shown beside the id.
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

// A native date field only opens its calendar from the small icon at its end.
// Mirrors openDatePicker in ExperimentForm: a click anywhere in the control
// opens it, and a browser that declines leaves a plain, still-typable date field.
const openDatePicker = (event) => {
  const input = event.currentTarget
  if (!input || input.readOnly || input.disabled) return
  try {
    input.showPicker?.()
  } catch {
    /* Unsupported or not a trusted gesture. */
  }
}

const teamLabel = computed(() => {
  const team = experiment.value?.experiment_team || ''
  return teamName.value ? `${teamName.value} — ${team}` : team
})

// Runs created before the naming key moved to Experiment Team still carry a
// notebook, and it is still what their id was built from - so the link stays,
// but only for those records. New runs leave elab_notebook empty and the field
// is hidden entirely rather than rendering an empty row.
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
    const res = await axios.get(`/api/resource/Lab%20Experiment/${encodeURIComponent(route.params.id)}`)
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

// _server_messages is a JSON list of JSON strings; joining it raw puts the
// encoded payload on screen.
// The run's stage. `workflow_state` drives the flow; `experiment_status` is the
// scientific outcome and is deliberately left alone until the outcome is known
// (LabExperiment.validate_terminal_outcome freezes it the moment it goes
// Completed/Failed, which is why finishing must not be a side effect of saving).
const runState = computed(() => experiment.value?.workflow_state || 'Draft')
const isDraft = computed(() => runState.value === 'Draft')
const isRunning = computed(() => runState.value === 'Running')

// Actions the run action bar drives explicitly. The header lists whatever else
// the workflow offers (Approve / Reject / Edit & Resubmit) so there are never
// two buttons for the same transition - and no raw "Save" action next to the
// form's own Save.
const DRIVEN_ACTIONS = ['Save', 'Start Running', 'Complete Experiment', 'Send For Approval']
const headerWorkflowActions = computed(() =>
  workflowActions.value.filter((a) => !DRIVEN_ACTIONS.includes(a.action))
)

// Neither Draft -> Running nor Running -> Pending Approval is a single hop in
// "Lab Experiment Flow"; each is two existing transitions. Applying them in
// sequence leaves the Workflow record untouched. If the second call fails the
// run simply stops at the intermediate state and the bar re-renders from
// whatever came back, so nothing is stranded.
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
  applyWorkflowChain(['Save', 'Start Running'], 'Run started - every tab is editable from here on.')

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
    const res = await axios.put(`/api/resource/Lab%20Experiment/${encodeURIComponent(route.params.id)}`, experiment.value)
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

// Item edits. Materials and Equipment had no add-row action at all here, so on a
// run cloned from a template - where the only rows are imported and therefore
// read-only - those tables could not be changed in any way.
const addMaterial = () => {
  experiment.value.material_required.push({ item_code: '', item_name: '', uom: '', qty: 1 })
}

const addEquipment = () => {
  experiment.value.equipment_details.push({ equipment_name: '', equipment_id: '', remarks: '' })
}

const addMethod = () => {
  experiment.value.methodology.push({
    method: '',
    time_to_complete: 0
  })
}

// item_code is a Link to Item, so a row the user adds has to pick a real one -
// and picking it fills the descriptive columns the same way the create form does.
const onMaterialItemSelect = (mat, item) => {
  if (!item) return
  mat.item_name = item.item_name || item.name
  mat.uom = item.stock_uom || item.uom || ''
}

// Rows cloned from an Experiment Template are editable but must not be removed.
// The server enforces this in LabExperiment.validate_imported_rows_kept(); these
// checks just keep the UI from offering an action that would be rejected on save.
const isImportedRow = (row) => Boolean(row?.from_template)

const removeChildRow = (fieldname, index) => {
  const rows = experiment.value?.[fieldname]
  if (!rows || isImportedRow(rows[index])) return
  rows.splice(index, 1)
}

const removeMethod = (index) => removeChildRow('methodology', index)
const removeMaterial = (index) => removeChildRow('material_required', index)
const removeEquipment = (index) => removeChildRow('equipment_details', index)

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
  uom: '',
  comments: ''
})

// Comments are edited per sample and saved on their own, so the textarea is
// backed by a draft keyed on the sample id rather than by samplesList - a
// reload mid-edit would otherwise wipe what was being typed.
const commentDrafts = ref({})
const savingCommentsFor = ref('')
const commentsNotice = ref('')

const commentDraft = (sample) =>
  commentDrafts.value[sample.name] ?? (sample.comments || '')

const setCommentDraft = (sample, value) => {
  commentDrafts.value = { ...commentDrafts.value, [sample.name]: value }
}

const commentsDirty = (sample) => commentDraft(sample).trim() !== (sample.comments || '').trim()

// Comments freeze at Pending Approval, which is what isSampleLocked() already
// covers. Unlike the sample's other fields there is no System Manager override:
// Sample.validate_comments_lock mirrors validate_post_approval_lock, which binds
// everyone, so offering the control to a System Manager would only produce a
// server rejection.
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
    // Drop the draft so the reloaded row becomes the source of truth again.
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

// The Failed outcome survives the flow change: a run that produced nothing still
// has to be recorded and signed off. It is its own button, never folded into
// Complete & Send for Approval, and it is the only place that writes
// experiment_status = Failed. That write is permanent -
// LabExperiment.validate_terminal_outcome refuses to move a terminal outcome.
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

// Errors belong inside the dialog, next to the fields that caused them - an
// alert() dumped the raw _server_messages JSON on screen and threw away what the
// user had typed the moment they dismissed it.
const sampleError = ref('')

const openRegisterModal = () => {
  sampleError.value = ''
  showRegisterModal.value = true
}

const registerSample = async () => {
  sampleError.value = ''
  if (!newSample.value.item || newSample.value.qty <= 0) {
    sampleError.value = 'Select an item and enter a quantity greater than zero.'
    return
  }
  savingSample.value = true
  try {
    const payload = {
      experiment: experiment.value.name,
      item: newSample.value.item,
      name_of_sample: newSample.value.name_of_sample,
      qty: newSample.value.qty,
      comments: newSample.value.comments
    }
    // Posted without a docstatus, so the Sample lands as a Draft and stays
    // editable. Submitting it is the user's own later action, after which every
    // field except `comments` is frozen - that one is allow_on_submit so it can
    // keep taking notes until the run is sent for approval.
    await axios.post('/api/resource/Sample', payload)

    // Producing a sample no longer ends the run: it records the fact and leaves
    // the run Running and editable. experiment_status is settled only by
    // Complete & Send for Approval or Mark as Failed, because
    // validate_terminal_outcome freezes these fields as soon as it goes terminal.
    await axios.put(`/api/resource/Lab%20Experiment/${encodeURIComponent(experiment.value.name)}`, {
      sample_generated: 1,
      sample_not_generated: 0
    })


    // Reset and reload
    newSample.value = { item: '', name_of_sample: '', qty: 0, uom: '', comments: '' }
    showRegisterModal.value = false
    await loadSamples()
    await loadExperiment()
  } catch (err) {
    console.error('Failed to register sample:', err)
    sampleError.value = readServerError(
      err,
      'Could not register the sample. Please check the details and try again.'
    )
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
  // Keep the tab in the URL so a link out of the tree lands on the same tab, and
  // so a reload or a shared link comes back to it. `replace` because switching
  // tabs is not a navigation step worth a Back-button entry.
  if (newTab !== (route.query.tab || 'general')) {
    router.replace({ query: { ...route.query, tab: newTab === 'general' ? undefined : newTab } })
  }
})

const applyTabFromRoute = () => {
  const wanted = String(route.query.tab || '')
  activeTab.value = TAB_KEYS.includes(wanted) ? wanted : 'general'
}

// A ?tab=materials link, or a tab left open while navigating between runs, can
// land on a level that has no such tab. The pane would simply render nothing, so
// fall back to Template rather than showing an empty card under a tab bar that
// does not contain the selected tab. Runs on load too - the category is not
// known until the record arrives.
watch([usesTemplate, activeTab], ([leaf, tab]) => {
  if (!leaf && TEMPLATE_TABS.includes(tab)) activeTab.value = 'general'
})

// A ?tab=rawdata link, or the tab left open while navigating between runs, can
// land on a Master Experiment, which has no Raw Data tab. Same fallback: show
// Template rather than a pane the tab row above no longer offers.
watch([() => experiment.value?.experiment_category, activeTab], ([category, tab]) => {
  if (tab === 'rawdata' && !showsRawDataTab(category)) activeTab.value = 'general'
})

const loadEverything = async () => {
  // Sequenced rather than fired together: loadSamples reads experiment.value.name
  // and returns early without it, so launching them in parallel meant the samples
  // list stayed empty until the Samples tab was opened - and the Create Sample
  // button, which is gated on "no sample exists yet", was deciding from a list
  // that had never loaded.
  await loadExperiment()
  loadTeamName()
  loadHistory()
  loadSamples()
}

// Clicking through the Experiment Tree changes only the :id param, and Vue
// reuses this component when the route record is unchanged - so onMounted alone
// left the header, tabs and samples showing the run we navigated away from
// while the tree itself had already moved on.
watch(
  () => route.params.id,
  (next, previous) => {
    if (!next || next === previous) return
    // Drop the outgoing run's data before fetching the new one. The header and
    // the tab panes are gated on `experiment` alone, not on `loading` - the
    // loading block is their sibling, not their wrapper - so leaving it in place
    // renders the run we just navigated away from underneath the new run's URL
    // until the fetch returns.
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

          <template v-if="isRunning">
            <!-- Gated in the UI on exactly what Sample enforces server-side: the run
                 must be Running, and one non-cancelled Sample per run is the limit -
                 so the user never has to discover that through a backend error. -->
            <span :title="getCreateSampleTooltip()">
              <button class="btn btn-sm btn-success" :disabled="!canCreateSample()" @click="openRegisterModal">
                Create Sample
              </button>
            </span>
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
            <div class="form-group-row">
              <div class="form-group">
                <label class="form-label">Experiment Team</label>
                <a
                  v-if="experiment.experiment_team"
                  :href="teamUrl"
                  target="_blank"
                  rel="noopener"
                  class="form-control link-value"
                  :title="`Open ${experiment.experiment_team}`"
                >
                  <!-- Name first, id second - the same label the create form's
                       picker uses. Teams made before team_name existed have
                       none, and then the id stands on its own. -->
                  <span class="link-value-text">{{ teamLabel }}</span>
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
          <div v-if="isWorkflowLocked() && !isSystemManager" class="info-banner" style="background-color: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: 0.85rem; color: #F59E0B;">
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

            <section class="meta-card">
              <h3 class="pane-subtitle">Observation Comments</h3>
              <div class="form-group stacked-field">
                <RichTextEditor v-model="experiment.observation" placeholder="Enter observations…" :readonly="isWorkflowLocked() && !isSystemManager" />
              </div>
            </section>
          </div>
        </div>

        <!-- MATERIALS TAB (EDITABLE with delete) -->
        <div v-if="activeTab === 'materials'" class="tab-pane">
          <div v-if="isWorkflowLocked() && !isSystemManager" class="info-banner" style="background-color: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: 0.85rem; color: #F59E0B;">
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

        <!-- 3. EQUIPMENT TAB (EDITABLE with delete) -->
        <div v-if="activeTab === 'equipment'" class="tab-pane">
          <div v-if="isWorkflowLocked() && !isSystemManager" class="info-banner" style="background-color: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: 0.85rem; color: #F59E0B;">
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
        <div v-if="activeTab === 'methodology'" class="tab-pane">
          <div v-if="isWorkflowLocked() && !isSystemManager" class="info-banner" style="background-color: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: 0.85rem; color: #F59E0B;">
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
                @click="openRegisterModal"
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

            <!-- Comments sit below the table rather than in a column: a textarea
                 in a table cell is unusable, and there is at most one live
                 sample per run anyway (validate_one_sample_per_experiment). -->
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
        </div>

        <!-- EXPERIMENT HIERARCHY TAB -->
        <div v-if="activeTab === 'tree'" class="tab-pane">
          <ExperimentTree :experiment-id="String(route.params.id)" />
        </div>

        <!-- REPORT TAB -->
        <!-- Editable while the run is; the same lock the Save button obeys. -->
        <div v-if="activeTab === 'rawdata'" class="tab-pane">
          <RawDataTab
            :experiment="experiment"
            :readonly="isWorkflowLocked() && !isSystemManager"
          />
        </div>

        <div v-if="activeTab === 'report'" class="tab-pane">
          <ExperimentReport :experiment-id="String(route.params.id)" />
        </div>
      </div>
    </div>

    <!-- 8. Register Sample Modal Dialog -->
    <div v-if="showRegisterModal && experiment" class="modal-overlay" @click.self="showRegisterModal = false">
      <div class="modal-container sample-register-modal">
        <div class="modal-header">
          <h3 class="modal-title">Register Output Sample</h3>
          <button class="modal-close-btn" @click="showRegisterModal = false">×</button>
        </div>
        
        <div class="modal-body">
          <div v-if="sampleError" class="form-error-banner" style="margin-bottom: 1rem;">
            <strong>Error:</strong> {{ sampleError }}
            <button class="form-error-close" @click="sampleError = ''">×</button>
          </div>

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

          <div class="form-group">
            <label class="form-label">Comments</label>
            <textarea
              v-model="newSample.comments"
              class="form-control textarea"
              rows="3"
              placeholder="Optional notes on this sample…"
            ></textarea>
            <span class="field-hint">Editable until this run is sent for approval.</span>
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
