<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { useUserStore } from '../../stores/user'
import { formatAuditDate } from '../../utils/dateFormatter'
import RichTextEditor from '../common/RichTextEditor.vue'
import './ExperimentForm.css'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const project = ref(route.query.project || '')
const employeeFunction = ref(route.query.employee_function || '')
const templateId = ref(route.query.template || '')
// Present only when the run was started from a team's Create Experiment button.
// Everything team-specific below keys off this, so the general New Experiment
// entry point is untouched.
const experimentTeam = ref(route.query.experiment_team || '')
const isTeamFlow = computed(() => Boolean(experimentTeam.value))

const loading = ref(true)
const saving = ref(false)
const error = ref('')

const activeTab = ref('general')

// Available items for dropdowns
const availableMaterials = ref([])
const availableEquipment = ref([])
const availableMethods = ref([])

// Search states for each row
const materialSearchStates = ref({})
const equipmentSearchStates = ref({})

// Check if experiment is from template - makes template-sourced fields read-only
const isFromTemplate = computed(() => !!experiment.value.experiment_template)

const projectName = ref('')
const employeeFunctionName = ref('')

const experiment = ref({
  title: '',
  project: project.value,
  employee_function: employeeFunction.value,
  template: templateId.value,
  experiment_template: templateId.value,
  aim: '',
  sub_aim: '',
  rationale: '',
  remark: '',
  experiment_start_date: new Date().toISOString().slice(0, 16),
  experiment_end_date: '',
  // employee_code is a Link to Employee - the User id is not a valid value here.
  employee_code: userStore.user.employee || '',
  employee_name: userStore.user.employee_name || userStore.user.full_name,
  // Required: the naming rule derives the experiment id from its team. Seeded
  // from the URL on the team flow; picked below on the general entry point.
  experiment_team: experimentTeam.value,

  segment: '',
  cost_center: '',

  // Child tables
  experiment_ingredients: [],
  experiment_parameters: [],
  experiment_protocol_steps: [],
  material_required: [],
  equipment_details: [],
  methodology: [],
  observation: ''
})

// Mirrors TEMPLATE_CHILD_MAP in elab_notebook/api/template.py. Rows in these
// tables can arrive pre-flagged with from_template = 1, which makes them
// editable but not deletable.
const TEMPLATE_CHILD_FIELDS = [
  'experiment_ingredients',
  'experiment_parameters',
  'experiment_protocol_steps',
  'material_required',
  'equipment_details',
  'methodology',
]

const loadTemplate = async () => {
  if (!templateId.value) {
    loading.value = false
    return
  }
  loading.value = true
  try {
    // The server owns the template -> run mapping (api/template.py
    // _clone_template_children). Mapping the tables here as well is what let the
    // two clone paths drift apart, and it is how imported rows ended up
    // unflagged. Every cloned row comes back with from_template = 1 already set.
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.template.get_template_clone', {
      params: { template_name: templateId.value }
    })
    const { header = {}, children = {} } = res.data.message || {}

    // `title` is the run's own name (Data) - it used to be a read-only Link that
    // could only hold a template id, which is why older runs are named after
    // their template.
    experiment.value.title = header.title || ''
    experiment.value.aim = header.aim || header.title || ''
    experiment.value.sub_aim = header.sub_aim || ''
    experiment.value.rationale = header.rationale || ''
    experiment.value.remark = header.remark || ''

    for (const field of TEMPLATE_CHILD_FIELDS) {
      experiment.value[field] = children[field] || []
    }
  } catch (err) {
    console.error('Failed to load template:', err)
    error.value = 'Failed to load details from selected template.'
  } finally {
    loading.value = false
  }
}

// Item management actions
const addMaterial = () => {
  experiment.value.material_required.push({
    item_code: '',
    item_name: '',
    uom: '',
    qty: 1,
    added_on: new Date().toISOString(),
    added_by: userStore.user.full_name || userStore.user.name
  })
}

const removeMaterial = (index) => {
  // Imported rows are protected server-side too - see
  // LabExperiment.validate_imported_rows_kept().
  if (experiment.value.material_required[index]?.from_template) return
  experiment.value.material_required.splice(index, 1)
}

const addEquipment = () => {
  experiment.value.equipment_details.push({
    equipment_name: '',
    equipment_id: '',
    remarks: '',
    added_on: new Date().toISOString(),
    added_by: userStore.user.full_name || userStore.user.name
  })
}

const removeEquipment = (index) => {
  // Imported rows are protected server-side too - see
  // LabExperiment.validate_imported_rows_kept().
  if (experiment.value.equipment_details[index]?.from_template) return
  experiment.value.equipment_details.splice(index, 1)
}

const addMethod = () => {
  experiment.value.methodology.push({
    method: '',
    time_to_complete: 0,
    added_on: new Date().toISOString(),
    added_by: userStore.user.full_name || userStore.user.name
  })
}

const removeMethod = (index) => {
  // Imported rows are protected server-side too - see
  // LabExperiment.validate_imported_rows_kept().
  if (experiment.value.methodology[index]?.from_template) return
  experiment.value.methodology.splice(index, 1)
}

const saveExperiment = async () => {
  // Both are Link/derived fields the server rejects with an opaque error, so name the
  // real problem here rather than falling through to "verify all required fields".
  if (!experiment.value.experiment_team) {
    error.value = noTeamAvailable.value
      ? `No team is set up for project ${project.value || '—'} under `
        + `${employeeFunction.value || 'this function'}. Set one up in Team Setup before starting a run.`
      : 'Select an Experiment Team - the run ID is generated from it.'
    return
  }
  if (!experiment.value.employee_code) {
    experiment.value.employee_code = userStore.user.employee || ''
  }
  if (!experiment.value.employee_code) {
    error.value =
      'Your user account is not linked to an Employee record, which is required to log a run.'
    return
  }

  saving.value = true
  error.value = ''
  try {
    const payload = {
      ...experiment.value,
      doctype: 'Lab Experiment'
    }
    const res = await axios.post('/api/resource/Lab%20Experiment', payload)
    if (res.data && res.data.data) {
      const newId = res.data.data.name
      router.push(`/experiments/${encodeURIComponent(newId)}`)
    }
  } catch (err) {
    console.error('Failed to save experiment:', err)
    error.value = err.response?.data?._server_messages 
      ? JSON.parse(err.response.data._server_messages).join(', ') 
      : 'Error saving experiment. Please verify all required fields.'
  } finally {
    saving.value = false
  }
}

const loadProjectAndFunctionNames = async () => {
  try {
    if (project.value) {
      const projRes = await axios.get(`/api/resource/Project/${project.value}`)
      projectName.value = projRes.data.data?.project_name || project.value
    }
    if (employeeFunction.value) {
      const funcRes = await axios.get(`/api/resource/Employee Function/${employeeFunction.value}`)
      employeeFunctionName.value = funcRes.data.data?.function_name || employeeFunction.value
    }
  } catch (err) {
    console.error('Failed to load project/function names:', err)
  }
}

const loadAvailableItems = async () => {
  try {
    // Load available items from Item doctype
    const itemsRes = await axios.get('/api/resource/Item?fields=["name","item_name","uom"]&limit_page_length=500')
    availableMaterials.value = itemsRes.data.data || []

    // Load available equipment from Item doctype with item_group = Equipment
    const equipmentRes = await axios.get('/api/resource/Item?filters=[["item_group","=","Equipment"]]&fields=["name","item_name","uom"]&limit_page_length=500')
    availableEquipment.value = equipmentRes.data.data || []
  } catch (err) {
    console.error('Failed to load available items:', err)
  }
}

const selectMaterial = (mat, item) => {
  mat.item_code = item.name
  mat.item_name = item.item_name || item.name
  mat.uom = item.uom || ''
}

const selectEquipment = (eq, item) => {
  eq.equipment_id = item.name
  eq.equipment_name = item.item_name || item.name
}

const loadTeamFinancials = async () => {
  if (!project.value || !employeeFunction.value) return
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.experiment_team.get_team_financials', {
      params: {
        project: project.value,
        employee_function: employeeFunction.value
      }
    })
    const fin = res.data.message || {}
    experiment.value.segment = fin.segment || ''
    experiment.value.cost_center = fin.cost_center || ''
  } catch (err) {
    console.error('Failed to load team financials:', err)
  }
}

// The run's ID is derived from its team (LabExperiment.set_series), so a run
// cannot be saved without one. The team flow already settled it upstream - the
// team's Create Experiment button passes it in the URL - so there the field is
// only shown, never asked. The general New Experiment entry point has no team
// in context and has to ask, because a project + function pair maps to many
// teams by design (api/experiment_team.save_team always creates a new record
// rather than reusing one).
const teamOptions = ref([])
const teamsLoaded = ref(false)

// Only the general entry point can dead-end: the team flow arrives with a team
// already in hand.
const noTeamAvailable = computed(
  () => !isTeamFlow.value && teamsLoaded.value && teamOptions.value.length === 0
)

const teamHint = computed(() => {
  if (isTeamFlow.value) return 'This run is being created for this team.'
  if (!teamsLoaded.value) return 'Looking up the teams for this project…'
  if (teamOptions.value.length === 0) {
    return `No team is set up for project ${project.value || '—'} under `
      + `${employeeFunctionName.value || employeeFunction.value || 'this function'} — set one up first.`
  }
  if (teamOptions.value.length === 1) return "Set from this project's only team."
  return `This project has ${teamOptions.value.length} teams under this function — choose which one this run belongs to.`
})

// Shown in the picker: team_name is the friendly label but is empty on teams
// created before it existed, so the id carries the row on its own.
const teamLabel = (t) => (t.team_name ? `${t.team_name} — ${t.name}` : t.name)

const loadTeamsForProject = async () => {
  // Nothing to choose when the team flow already named the team.
  if (isTeamFlow.value || !project.value) {
    teamsLoaded.value = true
    return
  }
  try {
    // No filter for membership here: get_team_permission_query_conditions
    // already narrows the list to teams the user heads or belongs to, which is
    // the same gate LabExperiment.validate_participant applies on save.
    const filters = { project: project.value }
    if (employeeFunction.value) {
      filters.employee_function = employeeFunction.value
    }
    const res = await axios.get('/api/method/frappe.client.get_list', {
      params: {
        doctype: 'Experiment Team',
        filters: JSON.stringify(filters),
        fields: JSON.stringify(['name', 'team_name']),
        order_by: 'creation desc',
        limit_page_length: 0
      }
    })
    teamOptions.value = res.data.message || []
    // A list of one is not a choice - settle it rather than making the user pick.
    if (teamOptions.value.length === 1) {
      experiment.value.experiment_team = teamOptions.value[0].name
    }
  } catch (err) {
    console.error('Failed to look up Experiment Team', err)
  } finally {
    teamsLoaded.value = true
  }
}

onMounted(() => {
  loadTemplate()
  loadTeamFinancials()
  loadProjectAndFunctionNames()
  loadAvailableItems()
  loadTeamsForProject()
})
</script>

<template>
  <div class="experiment-form-container">
    <!-- Header Area -->
    <div class="page-header">
      <div class="page-header-left">
        <nav class="breadcrumb-nav">
          <router-link to="/" class="breadcrumb-link">Home</router-link>
          <span class="breadcrumb-separator">&gt;</span>
          <router-link to="/experiments" class="breadcrumb-link">Experiments</router-link>
          <span class="breadcrumb-separator">&gt;</span>
          <span class="breadcrumb-current">New Run</span>
        </nav>
        <h1 class="page-title">Create Experiment Run</h1>
        <p class="page-subtitle">Pre-filled from template: {{ templateId }}</p>
      </div>

      <div class="page-header-right">
        <button class="btn btn-secondary" @click="router.back()">Cancel</button>
        <button class="btn btn-primary" :disabled="saving || loading || !experiment.experiment_team" @click="saveExperiment">
          {{ saving ? 'Saving...' : 'Save Run' }}
        </button>
      </div>
    </div>

    <!-- Error Banner -->
    <div v-if="error" class="form-error-banner">
      <strong>Error:</strong> {{ error }}
      <button class="form-error-close" @click="error = ''">×</button>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Initializing experiment from template data...</p>
    </div>

    <div v-else class="form-layout card">
      <!-- Tabs Selector -->
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
      </div>

      <!-- Tab Content Area -->
      <div class="tab-content">
        <!-- 1. GENERAL TAB -->
        <div v-if="activeTab === 'general'" class="tab-pane">
          <div class="pane-grid">
            <div class="form-group-row two-columns">
              <div class="form-group">
                <label class="form-label">Template</label>
                <input
                  type="text"
                  :value="experiment.title || 'None'"
                  class="form-control readonly"
                  readonly
                />
              </div>
              <div class="form-group">
                <label class="form-label">Experiment Team *</label>
                <!-- Locked when the team flow or a single candidate settles it;
                     only a genuine choice opens the picker. -->
                <input
                  v-if="isTeamFlow || teamOptions.length === 1"
                  type="text"
                  :value="experiment.experiment_team"
                  class="form-control readonly font-mono"
                  readonly
                />
                <select
                  v-else
                  v-model="experiment.experiment_team"
                  class="form-control"
                  :disabled="!teamsLoaded || !teamOptions.length"
                >
                  <option value="">{{ teamsLoaded ? 'Select a team…' : 'Loading…' }}</option>
                  <option v-for="t in teamOptions" :key="t.name" :value="t.name">
                    {{ teamLabel(t) }}
                  </option>
                </select>
                <span class="field-hint" :class="{ 'field-hint-error': noTeamAvailable }">{{ teamHint }}</span>
                <!-- The dead end is deliberate, so it has to offer a way out -
                     but only ever to Team Setup: nothing is created from here. -->
                <div v-if="noTeamAvailable" class="team-recovery">
                  <router-link to="/elab-notebook" class="btn btn-secondary btn-sm">
                    Go to Team Setup
                  </router-link>
                </div>
              </div>
            </div>

            <!-- Project Details Row -->
            <div class="form-group-row three-columns">
              <div class="form-group">
                <label class="form-label">Project ID</label>
                <input type="text" :value="experiment.project" class="form-control readonly" readonly />
              </div>
              <div class="form-group">
                <label class="form-label">Project Name</label>
                <input type="text" :value="projectName || 'N/A'" class="form-control readonly" readonly />
              </div>
              <div class="form-group">
                <label class="form-label">Employee Function</label>
                <input type="text" :value="experiment.employee_function" class="form-control readonly" readonly />
              </div>
            </div>

            <div class="form-group-row three-columns">
              <div class="form-group">
                <label class="form-label">Function Name</label>
                <input type="text" :value="employeeFunctionName || 'N/A'" class="form-control readonly" readonly />
              </div>
              <div class="form-group">
                <label class="form-label">Scientist (Lead)</label>
                <input type="text" :value="experiment.employee_name" class="form-control readonly" readonly />
              </div>
              <div class="form-group">
                <label class="form-label">Start Date & Time</label>
                <input type="datetime-local" :value="experiment.experiment_start_date" class="form-control readonly" readonly />
              </div>
            </div>

            <div class="form-group-row two-columns">
              <div class="form-group">
                <label class="form-label">Segment</label>
                <input type="text" :value="experiment.segment || 'None'" class="form-control readonly" readonly />
              </div>
              <div class="form-group">
                <label class="form-label">Cost Centre</label>
                <input type="text" :value="experiment.cost_center || 'None'" class="form-control readonly" readonly />
              </div>
            </div>

            <!-- Template Details Section -->
            <div v-if="experiment.aim || experiment.sub_aim || experiment.rationale" class="template-details-section">
              <div v-if="experiment.aim" class="form-group">
                <label class="form-label">Aim / Hypothesis</label>
                <textarea class="form-control readonly" :value="experiment.aim" readonly rows="2"></textarea>
              </div>
              <div v-if="experiment.sub_aim" class="form-group">
                <label class="form-label">Sub Aim</label>
                <textarea class="form-control readonly" :value="experiment.sub_aim" readonly rows="2"></textarea>
              </div>
              <div v-if="experiment.rationale" class="form-group">
                <label class="form-label">Rationale</label>
                <textarea class="form-control readonly" :value="experiment.rationale" readonly rows="2"></textarea>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Aim / Hypothesis *</label>
              <textarea
                :value="experiment.aim"
                class="form-control textarea"
                :readonly="isFromTemplate"
                :class="{ readonly: isFromTemplate }"
                rows="3"
                placeholder="Aim of the experiment..."
              ></textarea>
            </div>

            <div class="form-group">
              <label class="form-label">Sub Aim</label>
              <textarea
                :value="experiment.sub_aim"
                class="form-control textarea"
                :readonly="isFromTemplate"
                :class="{ readonly: isFromTemplate }"
                rows="2"
                placeholder="Sub-aim (optional)..."
              ></textarea>
            </div>

            <div class="form-group">
              <label class="form-label">Rationale</label>
              <textarea
                :value="experiment.rationale"
                class="form-control textarea"
                :readonly="isFromTemplate"
                :class="{ readonly: isFromTemplate }"
                rows="3"
                placeholder="Hypothesis rationale..."
              ></textarea>
            </div>
          </div>
        </div>

        <!-- 2. MATERIAL REQUIRED TAB -->
        <div v-if="activeTab === 'materials'" class="tab-pane">
          <div class="pane-header-row">
            <h3 class="pane-subtitle">Required Formulation Ingredients</h3>
            <button class="btn btn-secondary btn-sm btn-add-row" @click="addMaterial">+ Add Material</button>
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
                <template v-for="(mat, idx) in experiment.material_required" :key="idx">
                  <tr :class="{ 'template-row': mat.from_template }">
                    <td>
                      <div v-if="!mat.from_template" class="search-field-wrapper" :style="{ position: 'relative' }">
                        <input
                          type="text"
                          :value="materialSearchStates[idx]?.search || mat.item_code"
                          @input="(e) => {
                            if(!materialSearchStates[idx]) materialSearchStates[idx] = {};
                            materialSearchStates[idx].search = e.target.value;
                            materialSearchStates[idx].showDropdown = true;
                          }"
                          @focus="() => { if(!materialSearchStates[idx]) materialSearchStates[idx] = {}; materialSearchStates[idx].showDropdown = true; }"
                          @blur="() => setTimeout(() => { if(materialSearchStates[idx]) materialSearchStates[idx].showDropdown = false; }, 200)"
                          class="form-control table-input search-input"
                          placeholder="Search item..."
                          style="position: relative; z-index: 100;"
                        />
                        <div v-if="materialSearchStates[idx]?.showDropdown" class="item-dropdown" style="position: absolute; top: 100%; left: 0; right: 0; margin-top: 2px;">
                          <div
                            v-for="item in availableMaterials.filter(m => !materialSearchStates[idx]?.search || m.name.toLowerCase().includes(materialSearchStates[idx].search.toLowerCase()) || m.item_name.toLowerCase().includes(materialSearchStates[idx].search.toLowerCase()))"
                            :key="item.name"
                            @mousedown="() => { mat.item_code = item.name; mat.item_name = item.item_name; mat.uom = item.uom || ''; materialSearchStates[idx].search = item.name; materialSearchStates[idx].showDropdown = false; }"
                            class="dropdown-item"
                          >
                            <strong>{{ item.name }}</strong><br>
                            <small>{{ item.item_name }}</small>
                          </div>
                        </div>
                      </div>
                      <input v-else type="text" :value="mat.item_code" class="form-control table-input readonly" readonly />
                    </td>
                    <td>
                      <input type="text" v-model="mat.item_name" class="form-control table-input" placeholder="Item Description" :readonly="mat.from_template" :class="{ readonly: mat.from_template }" />
                    </td>
                    <td>
                      <input type="text" v-model="mat.uom" class="form-control table-input" placeholder="e.g. L, mL, mg" :readonly="mat.from_template" :class="{ readonly: mat.from_template }" />
                    </td>
                    <td>
                      <input type="number" v-model="mat.qty" class="form-control table-input" min="0" step="any" :readonly="mat.from_template" :class="{ readonly: mat.from_template }" />
                    </td>
                    <td>
                      <button v-if="!mat.from_template" class="delete-row-btn" @click="removeMaterial(idx)" title="Remove item">×</button>
                      <span v-else class="imported-row-lock" title="Imported from the Experiment Template - read-only and cannot be deleted">&#128274;</span>
                    </td>
                  </tr>
                  <tr v-if="mat.added_on" class="history-row">
                    <td colspan="5" class="history-cell">
                      {{ formatAuditDate(mat.added_on) }} by {{ mat.added_by }}
                    </td>
                  </tr>
                </template>
                <tr v-if="experiment.material_required.length === 0">
                  <td colspan="5" class="empty-table-cell">No materials required for this run. Click '+ Add Material' to insert.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 3. EQUIPMENT DETAILS TAB -->
        <div v-if="activeTab === 'equipment'" class="tab-pane">
          <div class="pane-header-row">
            <h3 class="pane-subtitle">Instruments & Tool Allocation</h3>
            <button class="btn btn-secondary btn-sm btn-add-row" @click="addEquipment">+ Add Equipment</button>
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
                <template v-for="(eq, idx) in experiment.equipment_details" :key="idx">
                  <tr :class="{ 'template-row': eq.from_template }">
                    <td>
                      <input type="text" v-model="eq.equipment_name" class="form-control table-input" placeholder="Equipment Name" :readonly="eq.from_template" :class="{ readonly: eq.from_template }" />
                    </td>
                    <td>
                      <div v-if="!eq.from_template" class="search-field-wrapper" :style="{ position: 'relative' }">
                        <input
                          type="text"
                          :value="equipmentSearchStates[idx]?.search || eq.equipment_id"
                          @input="(e) => {
                            if(!equipmentSearchStates[idx]) equipmentSearchStates[idx] = {};
                            equipmentSearchStates[idx].search = e.target.value;
                            equipmentSearchStates[idx].showDropdown = true;
                          }"
                          @focus="() => { if(!equipmentSearchStates[idx]) equipmentSearchStates[idx] = {}; equipmentSearchStates[idx].showDropdown = true; }"
                          @blur="() => setTimeout(() => { if(equipmentSearchStates[idx]) equipmentSearchStates[idx].showDropdown = false; }, 200)"
                          class="form-control table-input search-input"
                          placeholder="Search equipment..."
                          style="position: relative; z-index: 100;"
                        />
                        <div v-if="equipmentSearchStates[idx]?.showDropdown" class="item-dropdown" style="position: absolute; top: 100%; left: 0; right: 0; margin-top: 2px;">
                          <div
                            v-for="item in availableEquipment.filter(eq => !equipmentSearchStates[idx]?.search || eq.name.toLowerCase().includes(equipmentSearchStates[idx].search.toLowerCase()) || eq.item_name.toLowerCase().includes(equipmentSearchStates[idx].search.toLowerCase()))"
                            :key="item.name"
                            @mousedown="() => { eq.equipment_id = item.name; eq.equipment_name = item.item_name; equipmentSearchStates[idx].search = item.name; equipmentSearchStates[idx].showDropdown = false; }"
                            class="dropdown-item"
                          >
                            <strong>{{ item.name }}</strong><br>
                            <small>{{ item.item_name }}</small>
                          </div>
                        </div>
                      </div>
                      <input v-else type="text" :value="eq.equipment_id" class="form-control table-input readonly" readonly />
                    </td>
                    <td>
                      <input type="text" v-model="eq.remarks" class="form-control table-input" placeholder="Allocation comments..." :readonly="eq.from_template" :class="{ readonly: eq.from_template }" />
                    </td>
                    <td>
                      <button v-if="!eq.from_template" class="delete-row-btn" @click="removeEquipment(idx)">×</button>
                      <span v-else class="imported-row-lock" title="Imported from the Experiment Template - read-only and cannot be deleted">&#128274;</span>
                    </td>
                  </tr>
                  <tr v-if="eq.added_on" class="history-row">
                    <td colspan="4" class="history-cell">
                      {{ formatAuditDate(eq.added_on) }} by {{ eq.added_by }}
                    </td>
                  </tr>
                </template>
                <tr v-if="experiment.equipment_details.length === 0">
                  <td colspan="4" class="empty-table-cell">No equipment allocated.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 4. METHODOLOGY TAB -->
        <div v-if="activeTab === 'methodology'" class="tab-pane">
          <div class="pane-header-row">
            <h3 class="pane-subtitle">Experimental Methodology</h3>
            <button class="btn btn-secondary btn-sm btn-add-row" @click="addMethod">+ Add Method</button>
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
                <template v-for="(meth, idx) in experiment.methodology" :key="idx">
                  <tr :class="{ 'template-row': meth.from_template }">
                    <td>
                      <input type="text" v-model="meth.method" class="form-control table-input" placeholder="e.g. HPLC separation" :readonly="meth.from_template" :class="{ readonly: meth.from_template }" />
                    </td>
                    <td>
                      <input type="number" v-model="meth.time_to_complete" class="form-control table-input" min="0" :readonly="meth.from_template" :class="{ readonly: meth.from_template }" />
                    </td>
                    <td>
                      <button v-if="!meth.from_template" class="delete-row-btn" @click="removeMethod(idx)">×</button>
                      <span v-else class="imported-row-lock" title="Imported from the Experiment Template - read-only and cannot be deleted">&#128274;</span>
                    </td>
                  </tr>
                  <tr v-if="meth.added_on" class="history-row">
                    <td colspan="3" class="history-cell">
                      {{ formatAuditDate(meth.added_on) }} by {{ meth.added_by }}
                    </td>
                  </tr>
                </template>
                <tr v-if="experiment.methodology.length === 0">
                  <td colspan="3" class="empty-table-cell">No specific methodology steps.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 5. PROTOCOL STEPS TAB -->
        <div v-if="activeTab === 'procedure'" class="tab-pane">
          <h3 class="pane-subtitle">Standard Execution Procedure (Checklist)</h3>
          
          <div class="protocol-steps-list">
            <div 
              v-for="step in experiment.experiment_protocol_steps" 
              :key="step.step_order" 
              class="protocol-step-item"
            >
              <div class="step-num">{{ step.step_order }}.</div>
              <div class="step-details">
                <div class="step-title-row">
                  <strong class="step-heading">{{ step.title }}</strong>
                  <span v-if="step.duration" class="step-duration">Duration: {{ step.duration }}</span>
                </div>
                <p class="step-desc">{{ step.description }}</p>
                <div class="step-meta" v-if="step.equipment || step.operator_role">
                  <span v-if="step.equipment">Equipment: <strong>{{ step.equipment }}</strong></span>
                  <span v-if="step.operator_role">Role: <strong>{{ step.operator_role }}</strong></span>
                </div>
              </div>
            </div>
            <div v-if="experiment.experiment_protocol_steps.length === 0" class="empty-list-pane">
              No checklist steps loaded from template.
            </div>
          </div>
        </div>

        <!-- 6. OBSERVATION TAB -->
        <div v-if="activeTab === 'observations'" class="tab-pane">
          <section class="meta-card">
            <h3 class="pane-subtitle">Observation Comments</h3>
            <div class="form-group stacked-field">
              <RichTextEditor v-model="experiment.observation" placeholder="Enter observations…" />
            </div>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>
