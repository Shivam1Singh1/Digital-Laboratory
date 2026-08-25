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
import { formatAuditDate } from '../../utils/dateFormatter'
import { deskUrl } from '../../utils/frappeUrl'
import './ExperimentDetail.css'
// === DYNAMIC-PERMS-START ===
// import { usePermissionStore } from '../../stores/permissions'
// === DYNAMIC-PERMS-END ===

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
// === DYNAMIC-PERMS-START ===
// const permStore = usePermissionStore()
// === DYNAMIC-PERMS-END ===

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
  // Third at every level that has it - above the template-only block, which
  // only appears at the leaf and would otherwise push Raw Data to seventh.
  // Hidden on a Master Experiment - utils/rawData.js mirrors the doctype's own
  // depends_on so this form and the create form hide the same thing.
  ...(showsRawDataTab(experiment.value?.experiment_category)
    ? [{ key: 'rawdata', label: 'Raw Data' }]
    : []),
  // Kept in the same slot as the create form - after Raw Data rather than
  // before it as on the desk - so the two forms in this app present the run's
  // tabs in one order. result_tab carries no depends_on, so this shows at every
  // level, Master Experiment included.
  { key: 'result', label: 'Result' },
  ...(usesTemplate.value
    ? [
        // One tab, two stacked sections: Material Required above, Equipment
        // Details below. Keyed 'materials' so existing ?tab=materials links and
        // the TEMPLATE_TABS reset guard keep working unchanged.
        { key: 'materials', label: 'Material & Equipment' },
        // Methodology's content moved under Details and its tab is gone with it.
        // Protocol Steps is gone outright: it showed experiment_protocol_steps,
        // the template's planned checklist, which is no longer surfaced in the
        // SPA at all. The table and its data are untouched on the server.
      ]
    : []),
  { key: 'tree', label: 'Experiment Hierarchy' },
  { key: 'report', label: 'Report' },
  { key: 'samples', label: 'Samples' },
  // History/Audit Log is hidden, not removed: the pane below and loadHistory()
  // are intact, so putting the line back here is all it takes to show it again.
  // ?tab=history still opens it for anyone holding such a link.
])

// The experiment's id is generated from its team, so the team is the natural
// parent to jump to - and it stays inside this app. The old comment here said
// /elab-notebook/:id was the team *setup* page and sent the user to the desk
// form instead; that was wrong. `/elab-notebook` with no id is TeamSetup,
// `/elab-notebook/:id` is TeamDetail, which is the record view (router.js).
//
// experiment_team holds the Experiment Team docname, and get_team_detail takes
// a docname despite its `team_name` parameter being named after the label - so
// this value goes straight through with nothing to resolve.
const teamRoute = computed(() =>
  experiment.value?.experiment_team
    ? `/elab-notebook/${encodeURIComponent(experiment.value.experiment_team)}`
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
    // === DYNAMIC-PERMS-START ===
    // await refreshPermsAfterTransition()
    // === DYNAMIC-PERMS-END ===
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
    // === DYNAMIC-PERMS-START ===
    // await refreshPermsAfterTransition()
    // === DYNAMIC-PERMS-END ===
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
// === DYNAMIC-PERMS-START ===
// // The one genuine hardcoded role check on these four pages: a role name matched
// // in JS against a list the client happens to hold. Everything else that looked
// // like one turned out to be a server-computed domain answer. Replaced by the
// // record-level permission dict, which is decided by Frappe over the same doc -
// // Role Permission Manager, User Permissions and has_lab_experiment_permission
// // together - instead of one string this file knows about.
// //
// // The name is kept because ~20 template sites read it; what it now means is
// // "may override the workflow lock". ORed with the old check so a System Manager
// // whose permission dict has not arrived yet is never worse off than before.
// const isSystemManager = computed(() => {
//   return (
//     permStore.can('Lab Experiment', 'write', route.params.id) ||
//     userStore.user?.roles?.includes('System Manager') ||
//     false
//   )
// })
// === DYNAMIC-PERMS-END ===
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

// The run's own protocol steps and observations. Distinct from
// experiment_protocol_steps, which is the template's planned checklist shown on
// the Procedure tab and cloned in by api/template.py - these two are the run's
// own record and are never populated from a template.
//
// step_no is seeded from the current length rather than left blank: the doctype
// carries a real step_no column (it predates idx being the convention), so a row
// with none reads as step 0 in the grid.
const addProtocolStep = () => {
  const rows = experiment.value.protocol_steps
  rows.push({
    step_no: rows.length + 1,
    instruction: '',
    expected_duration: 0,
    is_critical: 0,
    attachment: ''
  })
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
const removeProtocolStep = (index) => removeChildRow('protocol_steps', index)
const removeObservationRow = (index) => removeChildRow('observations', index)

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
// Samples are generated in a batch from the run's Sample rows (see
// api/generation.py), so there is no per-sample draft object here any more.
const loadingSamples = ref(false)
const samplesList = ref([])

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
    // === DYNAMIC-PERMS-START ===
    // // Sample is its own doctype with its own has_sample_permission hook, so a
    // // row's permissions are not the parent run's and cannot be derived from
    // // them. One fetch per row, keyed on the Sample name. The store dedupes
    // // in-flight keys, so re-entering this tab does not refetch what it holds.
    // await Promise.all(
    //   samplesList.value.map((s) => permStore.fetchAndCache('Sample', s.name))
    // )
    // === DYNAMIC-PERMS-END ===
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

const getDocstatusLabel = (statusNum) => {
  if (statusNum === 0) return 'Draft'
  if (statusNum === 1) return 'Submitted'
  if (statusNum === 2) return 'Cancelled'
  return 'Unknown'
}

// Two independent actions on a concluded run, and they stay independent:
//
//   Add Sample       - repeatable. A run yields samples in rounds, so there is no
//                      point at which "no more samples" becomes true.
//   Create Stock Entry - once. The materials were consumed once, and
//                      Lab Experiment.stock_entry is what says it already happened.
//
// api/generation.py owns both rules; everything here only decides what the two
// buttons say and when they are live.
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

// The exact list Sample.validate_experiment_workflow_state accepts. Mirrored
// rather than approximated: the old test here asked whether the state looked
// approved or rejected, which let Draft and Saved through - both of which the
// doctype refuses, so the button was live and the save threw.
//
// This is NOT the status gate that was removed. That one was on
// `experiment_status` and lived in api/generation; this is the Sample doctype's
// own rule about its parent run's `workflow_state`, and it is still enforced
// server-side. A run in Draft has to be Started before it can carry samples.
const SAMPLE_ALLOWED_RUN_STATES = [
  'Running',
  'Completed',
  'Pending Approval from System Manager'
]

const runAcceptsSamples = () =>
  SAMPLE_ALLOWED_RUN_STATES.includes(experiment.value?.workflow_state || '')

// ---- Add Sample (repeatable) ----------------------------------------------
const showSampleModal = ref(false)
const savingSample = ref(false)
const sampleFormError = ref('')
const newSample = ref({ item: '', qty: 1, name_of_sample: '', comments: '', uom: '' })

// FUTURE STATUS GATE: `c.is_concluded` used to be a term here, and dropping it
// is what makes this button live at any Experiment Status. Put it back here and
// in addSampleReason() below when the stage is decided - and in
// api/generation._experiment_for_generation, which is the half that actually
// enforces. This function only decides whether the button looks pressable.
//
// runAcceptsSamples() is NOT that gate and stays: it mirrors the Sample
// doctype's own rule, so dropping it would only move the refusal to a backend
// error.
const canAddSample = () => {
  const c = generationCtx.value
  return Boolean(c && c.can_create_sample && runAcceptsSamples())
}

const addSampleReason = () => {
  const c = generationCtx.value
  if (!c) return 'Loading…'
  if (!runAcceptsSamples()) {
    const state = experiment.value?.workflow_state || 'Draft'
    // Draft is a step away from working; Approved is a door that has shut. The
    // two need different sentences because one of them has something to do.
    if (state === 'Draft' || state === 'Saved') {
      return `This run is ${state}. Start the run first — samples can be added from Running onwards.`
    }
    return `This run is ${state}, and samples can no longer be written against it. `
      + 'Samples must be added before it is approved.'
  }
  if (!c.can_create_sample) return 'You do not have permission to create Samples.'
  return 'Add as many samples as this run produced — there is no limit.'
}

const openSampleModal = () => {
  sampleFormError.value = ''
  newSample.value = { item: '', qty: 1, name_of_sample: '', comments: '', uom: '' }
  showSampleModal.value = true
}

// uom is read_only on Sample and fetched from the item server-side; shown here
// only so the dialog is not silent about what unit the quantity is in.
const onSampleItem = (opt) => {
  newSample.value.uom = opt ? opt.stock_uom || '' : ''
  if (opt && !newSample.value.name_of_sample) newSample.value.name_of_sample = opt.item_name || ''
}

// What was typed into the item picker, kept so "Create the Item" can carry it
// over as the new item's name. The picker itself only ever reports a committed
// link, and a name that matched nothing is exactly the case this is for.
const sampleItemSearch = ref('')
const onSampleItemSearch = (text) => {
  sampleItemSearch.value = text || ''
}

const newItemHintTail = computed(() =>
  sampleItemSearch.value.trim()
    ? `— opens prefilled as “${sampleItemSearch.value.trim()}”, then search for it here.`
    : '— fill in its classification there, then search for it here.'
)

// The Item form, not a mini-form in this dialog. Item here is mandatory on
// stock_uom, four separate Item Group fields and an HSN/SAC code; inventing
// defaults for a GST classification from a sample dialog would put wrong tax
// data in the item master. Only the name is carried over, because the name is
// the only part this dialog actually knows.
const openNewItemForm = () => {
  const typed = sampleItemSearch.value.trim()
  window.open(
    deskUrl('/app/item/new', typed ? { item_name: typed } : {}),
    '_blank',
    'noopener'
  )
}

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
      item: newSample.value.item,
      qty: newSample.value.qty,
      name_of_sample: newSample.value.name_of_sample || null,
      comments: newSample.value.comments || null
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

// ---- Create Stock Entry (once) --------------------------------------------

// FUTURE STATUS GATE: `c.is_concluded` was a term here too - see the note on
// canAddSample above. The three remaining terms are not status gates and all
// stay: `stock_entry` is the one-per-run rule, `material_row_count` is "there is
// nothing to issue", and `can_create_stock_entry` is a permission.
const canCreateStockEntry = () => {
  const c = generationCtx.value
  return Boolean(
    c && !c.stock_entry && c.material_row_count > 0 && c.can_create_stock_entry
  )
}

const stockEntryReason = () => {
  const c = generationCtx.value
  if (!c) return 'Loading…'
  if (c.stock_entry) return ''          // the link is shown instead
  if (!c.material_row_count) {
    return 'No Material Required rows on this run, so there is no stock to issue.'
  }
  if (!c.can_create_stock_entry) return 'You do not have permission to create Stock Entries.'
  return `Opens a Stock Entry prefilled with ${c.material_row_count} material `
    + `line${c.material_row_count === 1 ? '' : 's'} — pick the warehouse there and save.`
}

// Opens the real Stock Entry form, prefilled, instead of asking for a warehouse
// here and saving on the user's behalf. Not a preference: ERPNext refuses to
// save a Material Consumption entry whose rows carry no source warehouse, so
// there was never a draft to create before one had been picked. The desk form is
// where the rest of the entry gets filled in anyway.
//
// public/js/stock_entry.js reads `elab_experiment` off this URL and fills the
// form from api/generation.get_stock_entry_prefill.
//
// Nothing is reserved by opening it. `Lab Experiment.stock_entry` is stamped
// after the user saves, so the button below only hides on the next load of this
// page - not the moment it is clicked.
const openStockEntryForm = () => {
  const url = deskUrl('/app/stock-entry/new', { elab_experiment: route.params.id })
  window.open(url, '_blank', 'noopener')
}


const deskStockEntryUrl = (name) => deskUrl(`/app/stock-entry/${encodeURIComponent(name)}`)

// The in-app Sample detail, the same target SampleList.openSample pushes. Not
// the desk form: /samples/:id is a real route in this app (router.js), and
// sending a row to the desk instead would leave the run behind.
const openSample = (sample) => {
  router.push(`/samples/${encodeURIComponent(sample.name)}`)
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

// Tabs that were folded into another one. Their keys stay recognised rather
// than being dropped: links to them were handed out while they were tabs, and
// landing on the tab that now holds that content beats bouncing to Template.
// 'procedure' is deliberately absent - that pane is gone, not moved, so
// ?tab=procedure falls through to Template like any unknown key.
const MERGED_TABS = { equipment: 'materials', methodology: 'details' }

const applyTabFromRoute = () => {
  const wanted = String(route.query.tab || '')
  const resolved = MERGED_TABS[wanted] || wanted
  activeTab.value = TAB_KEYS.includes(resolved) ? resolved : 'general'
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

// === DYNAMIC-PERMS-START ===
// // Re-read after any transition. The dict describes the state the run was in
// // before the action, and the workflow lock this page gates on is exactly what
// // the action just changed. Kept apart from get_workflow_actions on purpose:
// // that answers "which transition may I press", which get_doc_permissions does
// // not model and must not be folded into.
// //
// // NOTE, verified: get_doc_permissions is called with ptype=None, and Frappe
// // invokes the controller hook once with that same None - so a ptype-specific
// // rule (Approved revokes delete) does NOT show up in the dict. Re-fetching is
// // still right, but do not rely on the dict alone for state-dependent rules.
// const refreshPermsAfterTransition = async () => {
//   permStore.invalidate('Lab Experiment', route.params.id)
//   await permStore.fetchAndCache('Lab Experiment', route.params.id)
// }
// === DYNAMIC-PERMS-END ===

const loadEverything = async () => {
  // Sequenced rather than fired together: loadSamples reads experiment.value.name
  // and returns early without it, so launching them in parallel meant the samples
  // list stayed empty until the Samples tab was opened - and the button that
  // reads that list was deciding from one that had never loaded.
  await loadExperiment()
  // Drives the Generate button and, more importantly, the sentence under it that
  // says why it cannot be pressed.
  loadGenerationContext()
  // === DYNAMIC-PERMS-START ===
  // // Record-level, alongside the rest rather than before it: nothing above reads
  // // the dict, and can() fails closed until it lands.
  // permStore.fetchAndCache('Lab Experiment', route.params.id)
  // === DYNAMIC-PERMS-END ===
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
                      <td>
                        <input
                          type="number"
                          v-model="step.step_no"
                          class="form-control table-input"
                          min="0"
                          :disabled="isWorkflowLocked() && !isSystemManager"
                        />
                      </td>
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
                           SPA has no upload widget anywhere, so an Attach field
                           is entered as the file path it stores. -->
                      <td>
                        <input
                          type="text"
                          v-model="step.attachment"
                          class="form-control table-input"
                          placeholder="/files/…"
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

        <!-- 3. EQUIPMENT — the second half of the Material & Equipment tab.
             Shares the tab key with the materials pane above so the two stack,
             rather than being folded into that pane's markup: the banner and
             table below are untouched, only what reveals them changed. -->
        <div v-if="activeTab === 'materials'" class="tab-pane">
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
        <!-- Methodology — now the last section of the Details tab. Same key as
             the Details panes above so it stacks under them; the pane's own
             contents are unchanged.
             `usesTemplate` is kept from when this was its own tab: Details shows
             at every level, and without it a Master Experiment would start
             carrying a Methodology table it has no use for. -->
        <div v-if="activeTab === 'details' && usesTemplate" class="tab-pane">
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
          <div v-if="isSampleLocked()" class="info-banner" style="background-color: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: 0.85rem; color: #F59E0B;">
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
                        style="padding: 0.25rem 0.5rem; font-size: 0.75rem;"
                      >
                        {{ submittingSampleId === sample.name ? 'Submitting...' : 'Submit' }}
                      </button>
                      <button
                        v-if="sample.docstatus === 1"
                        class="btn btn-sm btn-danger"
                        :disabled="cancellingSampleId === sample.name || (isSampleLocked() && !isSystemManager)"
                        :title="isSampleLocked() && !isSystemManager ? 'Sample is locked in this workflow state' : 'Cancel sample'"
                        @click.stop="cancelSample(sample)"
                        style="padding: 0.25rem 0.5rem; font-size: 0.75rem;"
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
        <div v-if="activeTab === 'result'" class="tab-pane">
          <div v-if="isWorkflowLocked() && !isSystemManager" class="info-banner" style="background-color: rgba(245, 158, 11, 0.12); border: 1px solid #F59E0B; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: 0.85rem; color: #F59E0B;">
            ⚠️ This experiment is locked. Only System Managers can edit the result in this state.
          </div>

          <section class="meta-card">
            <h3 class="pane-subtitle">Results</h3>
            <div class="form-group stacked-field">
              <RichTextEditor
                v-model="experiment.results"
                placeholder="Describe what the run produced…"
                min-height="200px"
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
      <div class="modal-content">
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
            <label class="form-label">Item *</label>
            <LinkField
              v-model="newSample.item"
              doctype="Item"
              :fields="['item_name', 'stock_uom']"
              :search-fields="['name', 'item_name']"
              description-field="item_name"
              placeholder="Search items…"
              input-class="form-control"
              @select="onSampleItem"
              @search="onSampleItemSearch"
            />
            <!-- For a substance this run just produced that has no Item yet.
                 Opens the real Item form rather than asking for the item here:
                 an Item on this site needs an HSN/SAC code and four Item Group
                 classifications, and those are tax and reporting decisions that
                 should not be guessed at from a sample dialog. -->
            <span class="field-hint">
              New substance with no Item yet?
              <a href="#" class="inline-link" @click.prevent="openNewItemForm">
                Create the Item
              </a>
              {{ newItemHintTail }}
            </span>
          </div>

          <div class="form-group-row two-columns">
            <div class="form-group">
              <label class="form-label">Quantity *</label>
              <input v-model.number="newSample.qty" type="number" min="0" step="any" class="form-control" />
            </div>
            <div class="form-group">
              <label class="form-label">UOM</label>
              <input type="text" :value="newSample.uom || '—'" class="form-control readonly" readonly />
              <span class="field-hint">Comes from the item.</span>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Sample Name</label>
            <input v-model="newSample.name_of_sample" type="text" class="form-control" placeholder="e.g. Aliquot 1" />
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
            :disabled="savingSample || !newSample.item || !(newSample.qty > 0)"
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
