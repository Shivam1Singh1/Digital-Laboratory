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
const aim = ref('')
const subAim = ref('')
const rationale = ref('')

// --- Sections 4-8: child tables + free-form fields
const materialRequired = ref([])
const equipmentDetails = ref([])
const methodology = ref([])
const methodologyComments = ref('')
const steps = ref('')
const observationTable = ref([])
const observationComments = ref('')

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
  steps.value = ''
  observationTable.value = []
  observationComments.value = ''
  storedTotalDuration.value = 0
  formError.value = ''
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
  steps.value = data.steps || ''
  observationTable.value = data.observation_table || []
  observationComments.value = data.observation_comments || ''

  storedTotalDuration.value = Number(data.total_duration) || 0
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
    if (res.data.message) applyDoc(res.data.message)
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

// Head Name mirrors the function's head — never typed by hand.
const applyHeadName = (opt) => {
  headName.value = opt ? opt.function_head_name || '' : ''
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
  projectId.value = opt ? opt.name : ''
  // Department follows the Project. The option already carries it, so no
  // second round trip is needed.
  allowedRoles.value = opt ? opt.department || '' : ''
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
    refer_to_experiment: '',
    equipment_name: '',
    equipment_id: '',
    remarks: ''
  })

const addMethodologyRow = () =>
  methodology.value.push({ method: '', time_to_complete: 0 })

const addObservationRow = () =>
  observationTable.value.push({
    parameter: '',
    observed_value: '',
    remarks: '',
    observed_on: ''
  })

const removeRow = (rows, idx) => rows.splice(idx, 1)

// ----------------------------------------------------------------- datetime IO

// Frappe Datetime is "YYYY-MM-DD HH:mm:ss"; <input type="datetime-local"> is
// "YYYY-MM-DDTHH:mm".
const toDatetimeInput = (val) => (val ? String(val).replace(' ', 'T').slice(0, 16) : '')
const fromDatetimeInput = (val) => (val ? `${val.replace('T', ' ')}:00` : null)

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
    rowPayload(row, ['refer_to_experiment', 'equipment_name', 'equipment_id', 'remarks'])
  ),
  methodology: methodology.value.map((row) => ({
    ...rowPayload(row, ['method']),
    // Stored as a plain Int number of minutes.
    time_to_complete: Number(row.time_to_complete) || 0
  })),
  methodology_comments: methodologyComments.value,

  steps: steps.value,

  observation_table: observationTable.value.map((row) => ({
    ...rowPayload(row, ['parameter', 'observed_value', 'remarks']),
    observed_on: fromDatetimeInput(toDatetimeInput(row.observed_on))
  })),
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
    if (saved) applyDoc(saved)

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

watch(() => route.params.id, fetchTemplateDetail)
onMounted(async () => {
  await fetchTemplateDetail()
  await loadMyFunctions()
})
</script>

<template>
  <div class="template-detail-container">
    <div class="page-header">
      <div class="page-header-left">
        <nav class="breadcrumb-nav">
          <router-link to="/" class="breadcrumb-link">Home</router-link>
          <span class="breadcrumb-separator">&gt;</span>
          <router-link to="/templates" class="breadcrumb-link">Experiment Templates</router-link>
          <span class="breadcrumb-separator">&gt;</span>
          <span class="breadcrumb-current">{{ isNew ? 'New Template' : docName }}</span>
        </nav>
        <h1 class="page-title">
          {{ isNew ? 'New Experiment Template' : `Edit Template: ${title || docName}` }}
        </h1>
      </div>

      <div class="page-header-right">
        <router-link to="/templates" class="btn btn-secondary">Cancel</router-link>
        <button class="btn btn-primary" @click="saveTemplate" :disabled="saving">
          <span v-if="saving" class="spinner btn-spinner"></span>
          {{ saving ? 'Saving...' : 'Save Template' }}
        </button>
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
      <!-- 1. GENERAL INFO -->
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

          <div class="form-group span-2">
            <label class="form-label">Description</label>
            <textarea
              v-model="description"
              rows="3"
              class="form-control"
              placeholder="What this template covers…"
            ></textarea>
          </div>

          <div class="form-group">
            <label class="form-label">Disable</label>
            <label class="checkbox-row">
              <input type="checkbox" v-model="disable" :true-value="1" :false-value="0" />
              <span>Disabled templates are hidden from new runs</span>
            </label>
          </div>
        </div>
      </section>

      <!-- 2. OWNERSHIP -->
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
            <label class="form-label">Project ID</label>
            <input
              type="text"
              :value="projectId"
              class="form-control readonly"
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

          <div class="form-group span-3">
            <label class="form-label">Remark</label>
            <textarea v-model="remark" rows="2" class="form-control"></textarea>
          </div>
        </div>
      </section>

      <!-- 3. OBJECTIVE -->
      <section class="meta-card">
        <h3 class="section-title">Objective</h3>
        <div class="meta-form-grid">
          <div class="form-group span-3">
            <label class="form-label">Aim</label>
            <input type="text" v-model="aim" class="form-control" placeholder="Primary aim" />
          </div>

          <div class="form-group span-3">
            <label class="form-label">Sub Aim</label>
            <textarea v-model="subAim" rows="2" class="form-control"></textarea>
          </div>

          <div class="form-group span-3">
            <label class="form-label">Rationale</label>
            <textarea v-model="rationale" rows="4" class="form-control"></textarea>
          </div>
        </div>
      </section>

      <!-- 4. MATERIAL REQUIRED -->
      <section class="meta-card">
        <div class="table-actions">
          <h3 class="section-title no-margin">Material Required</h3>
          <button class="btn btn-secondary btn-sm" @click="addMaterialRow">+ Add Row</button>
        </div>

        <div class="table-scroll">
          <table class="grid-table">
            <thead>
              <tr>
                <th class="col-link">Item Code *</th>
                <th class="col-wide">Item Name</th>
                <th class="col-uom">UOM</th>
                <th class="col-qty">Qty *</th>
                <th class="grid-action-col"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in materialRequired" :key="idx">
                <td data-label="Item Code">
                  <LinkField
                    v-model="row.item_code"
                    doctype="Item"
                    :fields="['item_name', 'stock_uom']"
                    :search-fields="['name', 'item_name']"
                    description-field="item_name"
                    input-class="grid-input"
                    placeholder="Search item…"
                    @select="onItemSelect(row, $event)"
                  />
                </td>
                <td data-label="Item Name">
                  <input type="text" :value="row.item_name" class="grid-input readonly" readonly />
                </td>
                <td data-label="UOM">
                  <LinkField
                    v-model="row.uom"
                    doctype="UOM"
                    input-class="grid-input"
                    placeholder="UOM"
                  />
                </td>
                <td data-label="Qty">
                  <input type="number" step="any" min="0" v-model.number="row.qty" class="grid-input" />
                </td>
                <td class="grid-action-col">
                  <button class="grid-delete-btn" @click="removeRow(materialRequired, idx)">×</button>
                </td>
              </tr>
              <tr v-if="!materialRequired.length">
                <td colspan="5" class="grid-empty">No materials added. Click "+ Add Row" to start.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 5. EQUIPMENT DETAILS -->
      <section class="meta-card">
        <div class="table-actions">
          <h3 class="section-title no-margin">Equipment Details</h3>
          <button class="btn btn-secondary btn-sm" @click="addEquipmentRow">+ Add Row</button>
        </div>

        <div class="table-scroll">
          <table class="grid-table">
            <thead>
              <tr>
                <th class="col-link">Refer to Experiment</th>
                <th class="col-link">Equipment Name</th>
                <th class="col-uom">Equipment ID</th>
                <th class="col-wide">Remarks</th>
                <th class="grid-action-col"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in equipmentDetails" :key="idx">
                <td data-label="Refer to Experiment">
                  <input
                    type="text"
                    v-model="row.refer_to_experiment"
                    class="grid-input"
                    placeholder="Free text reference"
                  />
                </td>
                <td data-label="Equipment Name">
                  <input type="text" v-model="row.equipment_name" class="grid-input" />
                </td>
                <td data-label="Equipment ID">
                  <input type="text" v-model="row.equipment_id" class="grid-input" />
                </td>
                <td data-label="Remarks">
                  <textarea v-model="row.remarks" rows="1" class="grid-input textarea-input"></textarea>
                </td>
                <td class="grid-action-col">
                  <button class="grid-delete-btn" @click="removeRow(equipmentDetails, idx)">×</button>
                </td>
              </tr>
              <tr v-if="!equipmentDetails.length">
                <td colspan="5" class="grid-empty">No equipment added. Click "+ Add Row" to start.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 6. METHODOLOGY -->
      <section class="meta-card">
        <div class="table-actions">
          <h3 class="section-title no-margin">Methodology</h3>
          <button class="btn btn-secondary btn-sm" @click="addMethodologyRow">+ Add Row</button>
        </div>

        <div class="table-scroll">
          <table class="grid-table">
            <thead>
              <tr>
                <th class="col-wide">Method *</th>
                <th class="col-minutes">Time to Complete</th>
                <th class="grid-action-col"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in methodology" :key="idx">
                <td data-label="Method">
                  <textarea
                    v-model="row.method"
                    rows="1"
                    class="grid-input textarea-input"
                    placeholder="Describe the step…"
                  ></textarea>
                </td>
                <td data-label="Time to Complete">
                  <MinutesInput v-model="row.time_to_complete" />
                </td>
                <td class="grid-action-col">
                  <button class="grid-delete-btn" @click="removeRow(methodology, idx)">×</button>
                </td>
              </tr>
              <tr v-if="!methodology.length">
                <td colspan="3" class="grid-empty">No methodology steps. Click "+ Add Row" to start.</td>
              </tr>
            </tbody>
          </table>
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

      <!-- 7. PROTOCOL -->
      <section class="meta-card">
        <h3 class="section-title">Protocol</h3>

        <div class="form-group">
          <label class="form-label">Steps</label>
          <RichTextEditor v-model="steps" placeholder="Free-form protocol write-up…" />
        </div>
      </section>

      <!-- 8. OBSERVATION -->
      <section class="meta-card">
        <div class="table-actions">
          <h3 class="section-title no-margin">Observation</h3>
          <button class="btn btn-secondary btn-sm" @click="addObservationRow">+ Add Row</button>
        </div>

        <div class="table-scroll">
          <table class="grid-table">
            <thead>
              <tr>
                <th class="col-link">Parameter</th>
                <th class="col-link">Observed Value</th>
                <th class="col-wide">Remarks</th>
                <th class="col-datetime">Observed On</th>
                <th class="grid-action-col"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, idx) in observationTable" :key="idx">
                <td data-label="Parameter">
                  <input type="text" v-model="row.parameter" class="grid-input" />
                </td>
                <td data-label="Observed Value">
                  <input type="text" v-model="row.observed_value" class="grid-input" />
                </td>
                <td data-label="Remarks">
                  <textarea v-model="row.remarks" rows="1" class="grid-input textarea-input"></textarea>
                </td>
                <td data-label="Observed On">
                  <input
                    type="datetime-local"
                    class="grid-input"
                    :value="toDatetimeInput(row.observed_on)"
                    @input="row.observed_on = $event.target.value"
                  />
                </td>
                <td class="grid-action-col">
                  <button class="grid-delete-btn" @click="removeRow(observationTable, idx)">×</button>
                </td>
              </tr>
              <tr v-if="!observationTable.length">
                <td colspan="5" class="grid-empty">No observations. Click "+ Add Row" to start.</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="form-group stacked-field">
          <label class="form-label">Observation Comments</label>
          <RichTextEditor v-model="observationComments" placeholder="Free-form observation notes…" />
        </div>
      </section>
    </div>
  </div>
</template>
