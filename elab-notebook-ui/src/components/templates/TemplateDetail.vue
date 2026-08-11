<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import LinkField from '../common/LinkField.vue'
import MinutesInput from '../common/MinutesInput.vue'
import RichTextEditor from '../common/RichTextEditor.vue'
import { formatMinutes } from '../../utils/duration'
import { extractFrappeError } from '../../utils/frappeError'
import './TemplateDetail.css'

const route = useRoute()
const router = useRouter()

const DOCTYPE = 'Experiment Template'
const TYPE_OPTIONS = [
  'R&D-Early Stage',
  'R&D-Analytical',
  'Validation',
  'Scale-Up',
  'Process Development'
]

const isNew = computed(() => route.params.id === 'new')
const loading = ref(false)
const saving = ref(false)
const formError = ref('')

// Dirty state tracking
const isDirty = ref(false)
const initialFormState = ref({})

// Workflow state and actions
const workflowState = ref('')
const workflowActions = ref([])
const loadingWorkflowActions = ref(false)
const runningWorkflowAction = ref(false)

// Button visibility logic based on workflow and dirty state
const isReadOnly = computed(() => {
  const state = workflowState.value
  return state === 'Approved' || state === 'Pending from System Manager' || state === 'Pending For Approval'
})

const isSaved = computed(() => !isNew.value && docName.value !== '')

const showSaveButton = computed(() => {
  return isDirty.value && !isReadOnly.value
})

const showWorkflowActions = computed(() => {
  // Show workflow actions only when not dirty and not in new state
  return !isDirty.value && !isNew.value
})

const showStatusBadge = computed(() => {
  return !isNew.value && workflowState.value !== 'Draft'
})
// --- Section 1: General Info
const docName = ref('')
const title = ref('')
const type = ref('')
const description = ref('')
const disable = ref(0)

// --- Section 2: Ownership
const employeeFunction = ref('')
const headName = ref('')
const allowedRoles = ref('')
const project = ref('')
const projectId = ref('')
const remark = ref('')

// --- Section 3: Objective
const activeTab = ref('ownership')
const aim = ref('')
const subAim = ref('')
const rationale = ref('')

// --- Sections 4-8: child tables + free-form fields
const materialRequired = ref([])
const equipmentDetails = ref([])
const methodology = ref([])
const methodologyComments = ref('')
// Structured protocol steps. ExperimentForm copies these into a run's
// experiment_protocol_steps, which is why the template has to be able to author them.
const protocolSteps = ref([])
const steps = ref('')
const observationComments = ref('')
const historyList = ref([])

const loadHistory = async () => {
  if (isNew.value || !docName.value) return
  try {
    const res = await axios.get('/api/method/frappe.client.get_list', {
      params: {
        doctype: 'Version',
        filters: JSON.stringify({
          ref_doctype: 'Experiment Template',
          docname: docName.value
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
      return {
        ...ver,
        parsedData
      }
    })
  } catch (err) {
    console.error('Failed to load version history:', err)
  }
}

// Server-computed total, refreshed from the response after every save.
const storedTotalDuration = ref(0)

// Live preview while rows are being edited. The authoritative value is the one
// validate() writes on the server — this is UX only.
const liveTotalDuration = computed(() =>
  methodology.value.reduce((sum, row) => sum + (Number(row.time_to_complete) || 0), 0)
)

// ---------------------------------------------------------------- data loading

const resetForm = () => {
  docName.value = ''
  title.value = ''
  type.value = ''
  description.value = ''
  disable.value = 0
  employeeFunction.value = ''
  headName.value = ''
  allowedRoles.value = ''
  project.value = ''
  projectId.value = ''
  remark.value = ''
  aim.value = ''
  subAim.value = ''
  rationale.value = ''
  materialRequired.value = []
  equipmentDetails.value = []
  methodology.value = []
  methodologyComments.value = ''
  protocolSteps.value = []
  steps.value = ''
  observationComments.value = ''
  storedTotalDuration.value = 0
  formError.value = ''
  workflowState.value = ''
  workflowActions.value = []
  isDirty.value = false
  initialFormState.value = {}
}

const captureInitialState = () => {
  initialFormState.value = {
    title: title.value,
    type: type.value,
    description: description.value,
    disable: disable.value,
    employeeFunction: employeeFunction.value,
    headName: headName.value,
    allowedRoles: allowedRoles.value,
    project: project.value,
    remark: remark.value,
    aim: aim.value,
    subAim: subAim.value,
    rationale: rationale.value,
    materialRequired: JSON.stringify(materialRequired.value),
    equipmentDetails: JSON.stringify(equipmentDetails.value),
    methodology: JSON.stringify(methodology.value),
    methodologyComments: methodologyComments.value,
    protocolSteps: JSON.stringify(protocolSteps.value),
    steps: steps.value,
    observationComments: observationComments.value
  }
  isDirty.value = false
}

const checkFormDirty = () => {
  const currentState = {
    title: title.value,
    type: type.value,
    description: description.value,
    disable: disable.value,
    employeeFunction: employeeFunction.value,
    headName: headName.value,
    allowedRoles: allowedRoles.value,
    project: project.value,
    remark: remark.value,
    aim: aim.value,
    subAim: subAim.value,
    rationale: rationale.value,
    materialRequired: JSON.stringify(materialRequired.value),
    equipmentDetails: JSON.stringify(equipmentDetails.value),
    methodology: JSON.stringify(methodology.value),
    methodologyComments: methodologyComments.value,
    protocolSteps: JSON.stringify(protocolSteps.value),
    steps: steps.value,
    observationComments: observationComments.value
  }

  isDirty.value = JSON.stringify(currentState) !== JSON.stringify(initialFormState.value)
}

const applyDoc = (data) => {
  docName.value = data.name || ''
  title.value = data.title || ''
  type.value = data.type || ''
  description.value = data.description || ''
  disable.value = data.disable ? 1 : 0

  employeeFunction.value = data.employee_function || ''
  headName.value = data.head_name || ''
  allowedRoles.value = data.allowed_roles || ''
  project.value = data.project || ''
  projectId.value = data.project_id || data.project || ''
  remark.value = data.remark || ''

  aim.value = data.aim || ''
  subAim.value = data.sub_aim || ''
  rationale.value = data.rationale || ''

  materialRequired.value = data.material_required || []
  equipmentDetails.value = data.equipment_details || []
  methodology.value = data.methodology || []
  methodologyComments.value = data.methodology_comments || ''
  protocolSteps.value = data.template_protocol_steps || []
  steps.value = data.steps || ''
  observationComments.value = data.observation_comments || ''

  storedTotalDuration.value = Number(data.total_duration) || 0
  workflowState.value = data.workflow_state || 'Draft'

  captureInitialState()
}

// Two independent grants feed the same button row:
//   - role-based transitions from the workflow (System Manager, Employee, ...)
//   - the review actions delegated to the head of this template's Employee Function
// They are fetched together and merged by action name. Each request swallows its own
// failure so a problem with one source can never remove the other's buttons - the
// function-head grant is strictly additive to what System Manager already sees.
const fetchWorkflowActions = async () => {
  if (isNew.value || !docName.value) {
    workflowActions.value = []
    return
  }
  loadingWorkflowActions.value = true
  try {
    const [roleRes, headRes] = await Promise.all([
      axios
        .get('/api/method/elab_notebook.elab_notebook.api.workflow.get_workflow_actions', {
          params: { doctype: DOCTYPE, docname: docName.value }
        })
        .catch((err) => {
          console.error('Failed to fetch workflow actions', err)
          return null
        }),
      axios
        .get('/api/method/elab_notebook.elab_notebook.api.template.get_function_head_actions', {
          params: { template_name: docName.value }
        })
        .catch((err) => {
          console.error('Failed to fetch function head actions', err)
          return null
        })
    ])

    const roleActions = (roleRes?.data?.message || []).map((a) => ({ ...a, via: 'workflow' }))
    const roleActionNames = new Set(roleActions.map((a) => a.action))
    const headActions = (headRes?.data?.message || [])
      .filter((a) => !roleActionNames.has(a.action))
      .map((a) => ({ ...a, via: 'function_head' }))

    workflowActions.value = [...roleActions, ...headActions]
  } finally {
    loadingWorkflowActions.value = false
  }
}

// `act` carries where the grant came from, so an action the user only holds as
// function head is applied through the endpoint that checks that - the default
// workflow endpoint would reject it on the System Manager role gate.
const runWorkflowAction = async (act) => {
  if (isNew.value || !docName.value) return
  runningWorkflowAction.value = true
  formError.value = ''
  try {
    const res =
      act.via === 'function_head'
        ? await axios.post(
            '/api/method/elab_notebook.elab_notebook.api.template.approve_template',
            {
              template_name: docName.value,
              action: act.action
            }
          )
        : await axios.post(
            '/api/method/elab_notebook.elab_notebook.api.workflow.apply_workflow_action',
            {
              doctype: DOCTYPE,
              docname: docName.value,
              action: act.action
            }
          )
    workflowState.value = res.data.message || ''
    await fetchTemplateDetail()
  } catch (err) {
    console.error('Failed to run workflow action', err)
    formError.value = extractFrappeError(err)
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
  return 'state-draft'
}

const getWorkflowActionClass = (action) => {
  const act = action.toLowerCase()
  if (act.includes('approve')) return 'btn-success'
  if (act.includes('reject')) return 'btn-danger'
  if (act.includes('correction') || act.includes('back')) return 'btn-warning'
  return 'btn-primary'
}

const fetchTemplateDetail = async () => {
  resetForm()
  if (isNew.value) return

  loading.value = true
  try {
    const res = await axios.get(
      '/api/method/elab_notebook.elab_notebook.api.template.get_template_detail',
      { params: { template_name: route.params.id } }
    )
    if (res.data.message) {
      applyDoc(res.data.message)
      await loadHistory()
      await fetchWorkflowActions()
    }
  } catch (err) {
    console.error('Failed to fetch template detail', err)
    formError.value = extractFrappeError(err)
  } finally {
    loading.value = false
  }
}


// ------------------------------------------------------------- link behaviour

// The employee picks their Employee Function first; Projects are then scoped to
// the projects mapped to that function.
const myFunctions = ref([])
const functionsLoaded = ref(false)

const employeeFunctionSearch = async (txt) => {
  const term = (txt || '').toLowerCase()
  if (!term) return myFunctions.value
  return myFunctions.value.filter(
    (f) =>
      f.name.toLowerCase().includes(term) ||
      String(f.function_name || '').toLowerCase().includes(term)
  )
}

const projectSearch = async (txt) => {
  if (!employeeFunction.value) return []
  const res = await axios.get(
    '/api/method/elab_notebook.elab_notebook.api.employee_function.get_employee_function_project_options',
    { params: { employee_function: employeeFunction.value, txt: txt || '' } }
  )
  return res.data.message || []
}

const employeeFunctionHint = computed(() =>
  functionsLoaded.value && !myFunctions.value.length
    ? 'No Employee Function is assigned to you'
    : 'No matches found'
)

const projectHint = computed(() =>
  employeeFunction.value
    ? 'No Project is mapped to this Employee Function'
    : 'Select an Employee Function first'
)

// Only a small minority of Projects carry a department, whereas every Employee
// Function does — so the function's department is the fallback rather than
// leaving the field empty.
const functionDepartment = ref('')

// Head Name mirrors the function's head — never typed by hand.
const applyHeadName = (opt) => {
  headName.value = opt ? opt.function_head_name || '' : ''
  functionDepartment.value = opt ? opt.department || '' : ''
}

const onEmployeeFunctionSelect = (opt) => {
  applyHeadName(opt)
  // A Project is only valid for the function it is mapped to, so a stale
  // selection must not survive a function change.
  project.value = ''
  projectId.value = ''
  allowedRoles.value = ''
}

const onProjectSelect = (opt) => {
  projectId.value = opt ? opt.project_name || opt.name : ''
  // Department follows the Project. The option already carries it, so no
  // second round trip is needed.
  allowedRoles.value = opt ? opt.department || functionDepartment.value || '' : ''
}

// Load the signed-in employee's functions once, and pre-select when there is
// exactly one — an unambiguous answer shouldn't need a click.
const loadMyFunctions = async () => {
  try {
    const res = await axios.get(
      '/api/method/elab_notebook.elab_notebook.api.employee_function.get_current_employee_function'
    )
    myFunctions.value = (res.data.message || {}).functions || []
  } catch (err) {
    console.error('Failed to load employee functions', err)
    myFunctions.value = []
  } finally {
    functionsLoaded.value = true
  }

  if (isNew.value && !employeeFunction.value && myFunctions.value.length === 1) {
    const only = myFunctions.value[0]
    employeeFunction.value = only.name
    applyHeadName(only)
  }
}

// On an existing doc the function is already set, so back-fill the head name
// from the loaded list rather than leaving the read-only field blank.
watch([employeeFunction, myFunctions], () => {
  if (!employeeFunction.value || headName.value) return
  const match = myFunctions.value.find((f) => f.name === employeeFunction.value)
  if (match) applyHeadName(match)
})

const onItemSelect = (row, opt) => {
  row.item_name = opt ? opt.item_name || '' : ''
  row.uom = opt ? opt.stock_uom || '' : ''
}

// ------------------------------------------------------------------ row edits

const addMaterialRow = () =>
  materialRequired.value.push({ item_code: '', item_name: '', uom: '', qty: 0 })

const addEquipmentRow = () =>
  equipmentDetails.value.push({
    equipment_name: '',
    equipment_id: '',
    remarks: ''
  })

const addMethodologyRow = () =>
  methodology.value.push({ method: '', time_to_complete: 0 })

// step_order is pre-filled with the next number so the run's checklist keeps its
// order without the author having to number rows by hand.
const addProtocolStepRow = () =>
  protocolSteps.value.push({
    step_order: protocolSteps.value.length + 1,
    title: '',
    description: '',
    duration: '',
    equipment: '',
    operator_role: '',
    checklist_items: ''
  })

const removeRow = (rows, idx) => rows.splice(idx, 1)

// ---------------------------------------------------------------------- saving

const rowPayload = (row, fields) => {
  // Carrying `name` through lets Frappe update the existing child row instead of
  // dropping and recreating it.
  const out = row.name ? { name: row.name } : {}
  fields.forEach((f) => {
    out[f] = row[f]
  })
  return out
}

const buildPayload = () => ({
  title: title.value,
  type: type.value,
  description: description.value,
  disable: disable.value ? 1 : 0,

  employee_function: employeeFunction.value,
  head_name: headName.value,
  allowed_roles: allowedRoles.value,
  project: project.value,
  remark: remark.value,

  aim: aim.value,
  sub_aim: subAim.value,
  rationale: rationale.value,

  material_required: materialRequired.value.map((row) => ({
    ...rowPayload(row, ['item_code', 'item_name', 'uom']),
    qty: Number(row.qty) || 0
  })),
  equipment_details: equipmentDetails.value.map((row) =>
    rowPayload(row, ['equipment_name', 'equipment_id', 'remarks'])
  ),
  methodology: methodology.value.map((row) => ({
    ...rowPayload(row, ['method']),
    time_to_complete: Number(row.time_to_complete) || 0
  })),
  methodology_comments: methodologyComments.value,

  template_protocol_steps: protocolSteps.value.map((row) => ({
    ...rowPayload(row, [
      'title',
      'description',
      'duration',
      'equipment',
      'operator_role',
      'checklist_items'
    ]),
    step_order: Number(row.step_order) || 0
  })),

  steps: steps.value,

  observation_comments: observationComments.value
})

const validateForm = () => {
  if (!title.value.trim()) return 'Title is required.'
  if (!employeeFunction.value) return 'Employee Function is required.'
  if (!project.value) return 'Project is required.'

  const badMaterial = materialRequired.value.findIndex((r) => !r.item_code || !r.qty)
  if (badMaterial !== -1) {
    return `Material Required row ${badMaterial + 1}: Item Code and Qty are both required.`
  }

  const badMethod = methodology.value.findIndex((r) => !String(r.method || '').trim())
  if (badMethod !== -1) return `Methodology row ${badMethod + 1}: Method is required.`

  return ''
}

const saveTemplate = async () => {
  formError.value = ''

  const problem = validateForm()
  if (problem) {
    formError.value = problem
    return
  }

  saving.value = true
  try {
    // Standard REST insert/update, so the doctype's own validate() runs with the
    // caller's permissions rather than being bypassed.
    const payload = buildPayload()
    const res = isNew.value
      ? await axios.post(`/api/resource/${encodeURIComponent(DOCTYPE)}`, payload)
      : await axios.put(
          `/api/resource/${encodeURIComponent(DOCTYPE)}/${encodeURIComponent(docName.value)}`,
          payload
        )

    const saved = res.data.data
    if (saved) {
      applyDoc(saved)
      await loadHistory()
      await fetchWorkflowActions()
    }

    if (isNew.value && saved?.name) {
      router.push(`/templates/${encodeURIComponent(saved.name)}`)
    }
  } catch (err) {
    console.error('Failed to save template', err)
    formError.value = extractFrappeError(err)
  } finally {
    saving.value = false
  }
}

// Watch for form field changes to set dirty state
watch([
  title,
  type,
  description,
  disable,
  employeeFunction,
  allowedRoles,
  project,
  remark,
  aim,
  subAim,
  rationale,
  methodologyComments,
  steps,
  observationComments
], () => {
  checkFormDirty()
}, { immediate: false })

// Deep watch for array changes
watch([materialRequired, equipmentDetails, methodology], () => {
  checkFormDirty()
}, { deep: true, immediate: false })

watch(() => route.params.id, fetchTemplateDetail)
onMounted(async () => {
  await fetchTemplateDetail()
  await loadMyFunctions()
})
</script>

<template>
  <div class="template-detail-container">
    <div class="page-header">
      <div class="page-header-bg-icon">
        <svg class="header-lab-motif" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
          <path d="M6 3h12M9 3v4L4 18a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2L15 7V3" />
        </svg>
      </div>
      <div class="page-header-left">
        <nav class="breadcrumb-nav">
          <router-link to="/" class="breadcrumb-link">Home</router-link>
          <span class="breadcrumb-separator">&gt;</span>
          <router-link to="/templates" class="breadcrumb-link">Experiment Templates</router-link>
          <span class="breadcrumb-separator">&gt;</span>
          <span class="breadcrumb-current">{{ isNew ? 'New Template' : docName }}</span>
        </nav>
        <h1 class="page-title">
          {{ isNew ? 'New Experiment Template' : (isReadOnly ? `View Template: ${title || docName}` : `Edit Template: ${title || docName}`) }}
          <span v-if="showStatusBadge && workflowState" class="workflow-state-badge" :class="getWorkflowStateClass(workflowState)">
            {{ workflowState }}
          </span>
        </h1>
      </div>

      <div class="page-header-right">
        <router-link to="/templates" class="btn btn-secondary">Back</router-link>
        <template v-if="showSaveButton">
          <button class="btn btn-primary" @click="saveTemplate" :disabled="saving">
            <span v-if="saving" class="spinner btn-spinner"></span>
            {{ saving ? 'Saving...' : 'Save Template' }}
          </button>
        </template>
        <template v-else-if="showWorkflowActions && workflowActions.length > 0">
          <span v-if="loadingWorkflowActions" class="workflow-loading-spinner"></span>
          <button
            v-for="act in workflowActions"
            :key="act.action"
            class="btn btn-workflow"
            :class="getWorkflowActionClass(act.action)"
            @click="runWorkflowAction(act)"
            :disabled="runningWorkflowAction"
          >
            {{ act.action }}
          </button>
        </template>
      </div>
    </div>

    <div v-if="formError" class="form-error-banner">
      <strong>Could not save</strong>
      <span class="form-error-text">{{ formError }}</span>
      <button class="form-error-close" @click="formError = ''">×</button>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading template details...</p>
    </div>

    <div v-else class="detail-layout">
      <!-- 5-Tab Bar -->
      <div class="template-tabs-row">
        <button 
          class="tab-btn" 
          :class="{ active: activeTab === 'ownership' }" 
          @click="activeTab = 'ownership'"
        >
          Ownership
        </button>
        <button 
          class="tab-btn" 
          :class="{ active: activeTab === 'objective' }" 
          @click="activeTab = 'objective'"
        >
          Objective
        </button>
        <button 
          class="tab-btn" 
          :class="{ active: activeTab === 'requirements' }" 
          @click="activeTab = 'requirements'"
        >
          Requirements
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
          :class="{ active: activeTab === 'observation' }" 
          @click="activeTab = 'observation'"
        >
          Observation
        </button>
      </div>

      <fieldset :disabled="isReadOnly" class="detail-layout-tabs-content" style="border: none; padding: 0; margin: 0; min-width: 0; width: 100%;">
        <!-- Tab 1: Ownership -->
        <div v-show="activeTab === 'ownership'" class="tab-pane">
          <section class="meta-card">
            <h3 class="section-title">Ownership</h3>
            <div class="meta-form-grid">
              <div class="form-group">
                <label class="form-label">Employee Function *</label>
                <LinkField
                  v-model="employeeFunction"
                  :search-fn="employeeFunctionSearch"
                  description-field="function_name"
                  :empty-hint="employeeFunctionHint"
                  :clearable="false"
                  placeholder="Search your functions…"
                  @select="onEmployeeFunctionSelect"
                />
                <span v-if="functionsLoaded && !myFunctions.length" class="field-hint warn">
                  No Employee Function is assigned to your employee record.
                </span>
              </div>

              <div class="form-group">
                <label class="form-label">Head Name</label>
                <input
                  type="text"
                  :value="headName"
                  class="form-control readonly"
                  :title="headName"
                  placeholder="Auto-filled from Employee Function"
                  readonly
                />
              </div>

              <div class="form-group">
                <label class="form-label">Project *</label>
                <LinkField
                  v-model="project"
                  :search-fn="projectSearch"
                  :disabled="!employeeFunction"
                  description-field="project_name"
                  :empty-hint="projectHint"
                  placeholder="Search projects for this function…"
                  @select="onProjectSelect"
                />
                <span v-if="!employeeFunction" class="field-hint">
                  Pick an Employee Function to unlock this field.
                </span>
              </div>

              <div class="form-group">
                <label class="form-label">Project Name</label>
                <input
                  type="text"
                  :value="projectId"
                  class="form-control readonly"
                  :title="projectId"
                  placeholder="Auto-filled from Project"
                  readonly
                />
              </div>

              <div class="form-group">
                <label class="form-label">Department</label>
                <LinkField
                  v-model="allowedRoles"
                  doctype="Department"
                  :fields="['department_name']"
                  :search-fields="['name', 'department_name']"
                  :filters="[['disabled', '=', 0]]"
                  description-field="department_name"
                  placeholder="Search departments…"
                />
                <span class="field-hint">Auto-filled from the Project; override if needed.</span>
              </div>

              <div class="form-group span-2">
                <label class="form-label">Remark</label>
                <textarea v-model="remark" rows="3" class="form-control"></textarea>
              </div>
            </div>
          </section>
        </div>

        <!-- Tab 2: Objective -->
        <div v-show="activeTab === 'objective'" class="tab-pane">
          <section class="meta-card">
            <h3 class="section-title">General Info</h3>
            <div class="meta-form-grid">
              <div class="form-group span-2">
                <label class="form-label">Title *</label>
                <input
                  type="text"
                  v-model="title"
                  class="form-control"
                  placeholder="e.g. CRISPR Cas9 knockout protocol"
                />
              </div>

              <div class="form-group">
                <label class="form-label">Type</label>
                <select v-model="type" class="form-control">
                  <option value="">Select type…</option>
                  <option v-for="opt in TYPE_OPTIONS" :key="opt" :value="opt">{{ opt }}</option>
                </select>
              </div>

              <div class="form-group">
                <label class="form-label">Disable</label>
                <label class="checkbox-row">
                  <input type="checkbox" v-model="disable" :true-value="1" :false-value="0" />
                  <span>Disabled templates are hidden from new runs</span>
                </label>
              </div>

              <div class="form-group span-2">
                <label class="form-label">Description</label>
                <textarea
                  v-model="description"
                  rows="3"
                  class="form-control"
                  placeholder="What this template covers…"
                ></textarea>
              </div>
            </div>

            <div class="section-divider" style="margin: 2rem 0; border-top: 1px solid var(--border);"></div>

            <h3 class="section-title">Objective</h3>
            <div class="meta-form-grid">
              <div class="form-group">
                <label class="form-label">Aim</label>
                <textarea v-model="aim" rows="2" class="form-control" placeholder="Primary aim…"></textarea>
              </div>

              <div class="form-group">
                <label class="form-label">Sub Aim</label>
                <textarea v-model="subAim" rows="2" class="form-control" placeholder="Optional sub-aim details…"></textarea>
              </div>

              <div class="form-group span-2">
                <label class="form-label">Rationale</label>
                <textarea v-model="rationale" rows="5" class="form-control" placeholder="Scientific rationale or hypothesis…"></textarea>
              </div>
            </div>
          </section>
        </div>

        <!-- Tab 3: Requirements -->
        <div v-show="activeTab === 'requirements'" class="tab-pane">
          <!-- MATERIAL REQUIRED -->
          <section class="meta-card">
            <div class="table-actions">
              <h3 class="section-title no-margin">Material Required</h3>
              <button class="btn btn-secondary btn-sm btn-add-row" @click="addMaterialRow">+ Add Row</button>
            </div>

            <div class="grid-table-container">
              <div class="grid-table material-required-grid">
                <!-- Header Row -->
                <div class="grid-header-row">
                  <div class="grid-header-cell">Item Code *</div>
                  <div class="grid-header-cell">Item Name</div>
                  <div class="grid-header-cell">UOM</div>
                  <div class="grid-header-cell">Qty *</div>
                  <div class="grid-header-cell grid-header-action"></div>
                </div>

                <!-- Data Rows -->
                <template v-if="materialRequired.length">
                  <div v-for="(row, idx) in materialRequired" :key="idx" class="grid-data-row">
                    <div class="grid-cell">
                      <LinkField
                        v-model="row.item_code"
                        doctype="Item"
                        :fields="['item_name', 'stock_uom']"
                        :search-fields="['name', 'item_name']"
                        description-field="item_name"
                        :filters="[['Item', 'disabled', '=', 0]]"
                        input-class="grid-input"
                        placeholder="Search item…"
                        @select="onItemSelect(row, $event)"
                      />
                    </div>
                    <div class="grid-cell">
                      <input type="text" :value="row.item_name" class="grid-input readonly" readonly />
                    </div>
                    <div class="grid-cell">
                      <LinkField
                        v-model="row.uom"
                        doctype="UOM"
                        input-class="grid-input"
                        placeholder="UOM"
                      />
                    </div>
                    <div class="grid-cell">
                      <input type="number" step="any" min="0" v-model.number="row.qty" class="grid-input" />
                    </div>
                    <div class="grid-cell grid-action-cell">
                      <button class="grid-delete-btn" @click="removeRow(materialRequired, idx)">×</button>
                    </div>
                  </div>
                </template>

                <!-- Empty State -->
                <div v-else class="grid-empty-message">No materials added. Click "+ Add Row" to start.</div>
              </div>
            </div>
          </section>

          <!-- EQUIPMENT DETAILS -->
          <section class="meta-card" style="margin-top: 1.5rem;">
            <div class="table-actions">
              <h3 class="section-title no-margin">Equipment Details</h3>
              <button class="btn btn-secondary btn-sm btn-add-row" @click="addEquipmentRow">+ Add Row</button>
            </div>

            <div class="grid-table-container">
              <div class="grid-table equipment-details-grid">
                <!-- Header Row -->
                <div class="grid-header-row">
                  <div class="grid-header-cell">Equipment ID</div>
                  <div class="grid-header-cell">Equipment Name</div>
                  <div class="grid-header-cell">Remarks</div>
                  <div class="grid-header-cell grid-header-action"></div>
                </div>

                <!-- Data Rows -->
                <template v-if="equipmentDetails.length">
                  <div v-for="(row, idx) in equipmentDetails" :key="idx" class="grid-data-row">
                    <div class="grid-cell">
                      <input type="text" v-model="row.equipment_id" class="grid-input" />
                    </div>
                    <div class="grid-cell">
                      <input type="text" v-model="row.equipment_name" class="grid-input" />
                    </div>
                    <div class="grid-cell">
                      <textarea v-model="row.remarks" rows="1" class="grid-input grid-textarea"></textarea>
                    </div>
                    <div class="grid-cell grid-action-cell">
                      <button class="grid-delete-btn" @click="removeRow(equipmentDetails, idx)">×</button>
                    </div>
                  </div>
                </template>

                <!-- Empty State -->
                <div v-else class="grid-empty-message">No equipment added. Click "+ Add Row" to start.</div>
              </div>
            </div>
          </section>
        </div>

        <!-- Tab 4: Methodology -->
        <div v-show="activeTab === 'methodology'" class="tab-pane">
          <!-- METHODOLOGY -->
          <section class="meta-card">
            <div class="table-actions">
              <h3 class="section-title no-margin">Methodology</h3>
              <button class="btn btn-secondary btn-sm btn-add-row" @click="addMethodologyRow">+ Add Row</button>
            </div>

            <div class="grid-table-container">
              <div class="grid-table methodology-grid">
                <!-- Header Row -->
                <div class="grid-header-row">
                  <div class="grid-header-cell">Method *</div>
                  <div class="grid-header-cell">Time to Complete</div>
                  <div class="grid-header-cell grid-header-action"></div>
                </div>

                <!-- Data Rows -->
                <template v-if="methodology.length">
                  <div v-for="(row, idx) in methodology" :key="idx" class="grid-data-row">
                    <div class="grid-cell">
                      <textarea
                        v-model="row.method"
                        rows="1"
                        class="grid-input grid-textarea"
                        placeholder="Describe the step…"
                      ></textarea>
                    </div>
                    <div class="grid-cell">
                      <MinutesInput v-model="row.time_to_complete" />
                    </div>
                    <div class="grid-cell grid-action-cell">
                      <button class="grid-delete-btn" @click="removeRow(methodology, idx)">×</button>
                    </div>
                  </div>
                </template>

                <!-- Empty State -->
                <div v-else class="grid-empty-message">No methodology steps. Click "+ Add Row" to start.</div>
              </div>
            </div>

            <div class="total-duration-row">
              <span class="total-duration-label">Total Duration</span>
              <span class="total-duration-value">{{ formatMinutes(liveTotalDuration) }}</span>
              <span
                v-if="!isNew && storedTotalDuration !== liveTotalDuration"
                class="total-duration-note unsaved"
              >
                unsaved — server has {{ formatMinutes(storedTotalDuration) }}
              </span>
              <span v-else class="total-duration-note">calculated from Methodology rows on save</span>
            </div>

            <div class="form-group stacked-field">
              <label class="form-label">Methodology Comments</label>
              <RichTextEditor
                v-model="methodologyComments"
                placeholder="Notes that apply across all methodology steps…"
              />
            </div>
          </section>

          <!-- PROTOCOL STEPS (structured - copied into each experiment run) -->
          <section class="meta-card" style="margin-top: 1.5rem;">
            <div class="table-actions">
              <h3 class="section-title no-margin">Protocol Steps</h3>
              <button class="btn btn-secondary btn-sm btn-add-row" @click="addProtocolStepRow">+ Add Row</button>
            </div>
            <p class="field-hint" style="margin: 0 0 0.75rem;">
              These rows become the execution checklist on every experiment run created from this template.
            </p>

            <div class="grid-table-container protocol-steps-scroll">
              <div class="grid-table protocol-steps-grid">
                <!-- Header Row -->
                <div class="grid-header-row">
                  <div class="grid-header-cell">#</div>
                  <div class="grid-header-cell">Title</div>
                  <div class="grid-header-cell">Description</div>
                  <div class="grid-header-cell">Duration</div>
                  <div class="grid-header-cell">Equipment</div>
                  <div class="grid-header-cell">Operator Role</div>
                  <div class="grid-header-cell">Checklist Items</div>
                  <div class="grid-header-cell grid-header-action"></div>
                </div>

                <!-- Data Rows -->
                <template v-if="protocolSteps.length">
                  <div v-for="(row, idx) in protocolSteps" :key="idx" class="grid-data-row">
                    <div class="grid-cell">
                      <input v-model="row.step_order" type="number" min="0" class="grid-input" />
                    </div>
                    <div class="grid-cell">
                      <input v-model="row.title" type="text" class="grid-input" placeholder="e.g. Prepare buffer" />
                    </div>
                    <div class="grid-cell">
                      <textarea
                        v-model="row.description"
                        rows="1"
                        class="grid-input grid-textarea"
                        placeholder="What the operator does…"
                      ></textarea>
                    </div>
                    <div class="grid-cell">
                      <input v-model="row.duration" type="text" class="grid-input" placeholder="e.g. 30 min" />
                    </div>
                    <div class="grid-cell">
                      <input v-model="row.equipment" type="text" class="grid-input" />
                    </div>
                    <div class="grid-cell">
                      <input v-model="row.operator_role" type="text" class="grid-input" />
                    </div>
                    <div class="grid-cell">
                      <textarea
                        v-model="row.checklist_items"
                        rows="1"
                        class="grid-input grid-textarea"
                        placeholder="One check per line…"
                      ></textarea>
                    </div>
                    <div class="grid-cell grid-action-cell">
                      <button class="grid-delete-btn" @click="removeRow(protocolSteps, idx)">×</button>
                    </div>
                  </div>
                </template>

                <!-- Empty State -->
                <div v-else class="grid-empty-message">No protocol steps. Click "+ Add Row" to start.</div>
              </div>
            </div>
          </section>

          <!-- PROTOCOL -->
          <section class="meta-card" style="margin-top: 1.5rem;">
            <h3 class="section-title">Protocol</h3>

            <div class="form-group">
              <label class="form-label">Steps</label>
              <RichTextEditor v-model="steps" placeholder="Free-form protocol write-up…" />
            </div>
          </section>
        </div>

        <!-- Tab 5: Observation -->
        <div v-show="activeTab === 'observation'" class="tab-pane">
          <section class="meta-card">
            <h3 class="section-title">Observation</h3>
            <div class="form-group">
              <label class="form-label">Observation Notes</label>
              <RichTextEditor
                v-model="observationComments"
                placeholder="Describe expected observations, parameters to record, and outcome notes…"
              />
            </div>
          </section>
        </div>

        <!-- AUDIT HISTORY LOG -->
        <section class="meta-card" style="margin-top: 1.5rem;" v-if="!isNew">
          <h3 class="section-title">Audit History Log (Timing, Editor, Changes)</h3>
          
          <div class="history-timeline">
            <div v-for="ver in historyList" :key="ver.name" class="timeline-item">
              <div class="timeline-dot"></div>
              <div class="timeline-content">
                <div class="timeline-header">
                  <span class="timeline-author">Edited by: <strong>{{ ver.owner }}</strong></span>
                  <span class="timeline-time">{{ ver.creation?.split('.')[0] }}</span>
                </div>
                
                <!-- If fields changed -->
                <ul class="timeline-changes" v-if="ver.parsedData && ver.parsedData.changed && ver.parsedData.changed.length > 0">
                  <li v-for="(change, cIdx) in ver.parsedData.changed" :key="cIdx">
                    Field <strong>{{ change[0] }}</strong> updated: 
                    <span class="old-val">"{{ change[1] || 'Empty' }}"</span> &rarr; 
                    <span class="new-val">"{{ change[2] || 'Empty' }}"</span>
                  </li>
                </ul>

                <!-- If tables added/removed rows -->
                <ul class="timeline-changes" v-if="ver.parsedData && (ver.parsedData.added || ver.parsedData.removed)">
                  <li v-if="ver.parsedData.added && ver.parsedData.added.length > 0">
                    Added rows to child tables
                  </li>
                  <li v-if="ver.parsedData.removed && ver.parsedData.removed.length > 0">
                    Removed rows from child tables
                  </li>
                </ul>
                
                <!-- Fallback description -->
                <p class="timeline-desc" v-if="!ver.parsedData || (!ver.parsedData.changed && !ver.parsedData.added && !ver.parsedData.removed)">
                  Updated template settings.
                </p>
              </div>
            </div>

            <div v-if="historyList.length === 0" class="empty-history-text">
              No changes recorded for this template yet.
            </div>
          </div>
        </section>
      </fieldset>
    </div>
  </div>
</template>
