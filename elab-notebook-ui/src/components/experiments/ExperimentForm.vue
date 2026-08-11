<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { useUserStore } from '../../stores/user'
import { formatAuditDate } from '../../utils/dateFormatter'
import RichTextEditor from '../common/RichTextEditor.vue'
import LinkField from '../common/LinkField.vue'
import './ExperimentForm.css'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const project = ref(route.query.project || '')
const employeeFunction = ref(route.query.employee_function || '')
const templateId = ref(route.query.template || '')

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
  // Required: the naming rule derives the experiment id from its notebook.
  elab_notebook: '',

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

const loadTemplate = async () => {
  if (!templateId.value) {
    loading.value = false
    return
  }
  loading.value = true
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.template.get_template_detail', {
      params: { template_name: templateId.value }
    })
    const doc = res.data.message || {}
    
    // `title` is a Link to Experiment Template, so it can only hold a template id -
    // a descriptive string like "Run: X" fails link validation. The readable run name
    // lives in `aim`, which is the required Data field.
    experiment.value.title = templateId.value || ''
    experiment.value.aim = doc.aim || doc.template_name || doc.name
    experiment.value.sub_aim = doc.sub_aim || ''
    experiment.value.rationale = doc.rationale || ''
    experiment.value.remark = doc.remark || ''
    
    // Map ingredients
    if (doc.template_ingredients) {
      experiment.value.experiment_ingredients = doc.template_ingredients.map(ing => ({
        chemical: ing.chemical,
        grade: ing.grade,
        default_quantity: ing.default_quantity,
        unit: ing.unit,
        concentration: ing.concentration,
        supplier: ing.supplier,
        from_template: true
      }))
    }
    
    // Map parameters
    if (doc.template_parameters) {
      experiment.value.experiment_parameters = doc.template_parameters.map(p => ({
        parameter_name: p.parameter_name,
        target_value: p.target_value,
        min_value: p.min_value,
        max_value: p.max_value,
        unit: p.unit,
        type: p.type
      }))
    }
    
    // Map protocol steps
    if (doc.template_protocol_steps) {
      experiment.value.experiment_protocol_steps = doc.template_protocol_steps.map(s => ({
        step_order: s.step_order,
        title: s.title,
        description: s.description,
        duration: s.duration,
        equipment: s.equipment,
        operator_role: s.operator_role,
        checklist_items: s.checklist_items,
        from_template: true
      }))
    }
    
    // Map material required
    if (doc.material_required) {
      experiment.value.material_required = doc.material_required.map(m => ({
        item_code: m.item_code,
        item_name: m.item_name,
        uom: m.uom,
        qty: m.qty
      }))
    }
    
    // Map equipment details
    if (doc.equipment_details) {
      experiment.value.equipment_details = doc.equipment_details.map(e => ({
        equipment_name: e.equipment_name,
        equipment_id: e.equipment_id,
        remarks: e.remarks,
        from_template: true
      }))
    }

    // Map methodology
    if (doc.methodology) {
      experiment.value.methodology = doc.methodology.map(m => ({
        method: m.method,
        time_to_complete: m.time_to_complete,
        from_template: true
      }))
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
  const isTemplate = experiment.value.material_required[index]?.from_template
  console.log('removeMaterial called - index:', index, 'from_template:', isTemplate)
  if (isTemplate) {
    console.warn('Cannot delete template-sourced material')
    return
  }
  experiment.value.material_required.splice(index, 1)
  console.log('Material removed')
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
  const isTemplate = experiment.value.equipment_details[index]?.from_template
  console.log('removeEquipment called - index:', index, 'from_template:', isTemplate)
  if (isTemplate) {
    console.warn('Cannot delete template-sourced equipment')
    return
  }
  experiment.value.equipment_details.splice(index, 1)
  console.log('Equipment removed')
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
  const isTemplate = experiment.value.methodology[index]?.from_template
  console.log('removeMethod called - index:', index, 'from_template:', isTemplate)
  if (isTemplate) {
    console.warn('Cannot delete template-sourced method')
    return
  }
  experiment.value.methodology.splice(index, 1)
  console.log('Method removed')
}

const saveExperiment = async () => {
  // Both are Link/derived fields the server rejects with an opaque error, so name the
  // real problem here rather than falling through to "verify all required fields".
  if (!experiment.value.elab_notebook) {
    error.value = 'Select an ELab Notebook - the run ID is generated from it.'
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
      doctype: 'Experiment'
    }
    const res = await axios.post('/api/resource/Experiment', payload)
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

// The run's ID is derived from its notebook, so pre-select the project's notebook when
// there is exactly one - an ambiguous match is left for the user to choose.
const preselectNotebook = async () => {
  if (!project.value || experiment.value.elab_notebook) return
  try {
    const res = await axios.get('/api/method/frappe.client.get_list', {
      params: {
        doctype: 'ELab Notebook',
        filters: JSON.stringify({ project: project.value }),
        fields: JSON.stringify(['name']),
        limit_page_length: 2
      }
    })
    const found = res.data.message || []
    if (found.length === 1) experiment.value.elab_notebook = found[0].name
  } catch (err) {
    console.error('Failed to preselect ELab Notebook', err)
  }
}

onMounted(() => {
  loadTemplate()
  loadTeamFinancials()
  loadProjectAndFunctionNames()
  loadAvailableItems()
  preselectNotebook()
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
        <button class="btn btn-primary" :disabled="saving || loading" @click="saveExperiment">
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
                <label class="form-label">ELab Notebook *</label>
                <LinkField
                  v-model="experiment.elab_notebook"
                  doctype="ELab Notebook"
                  :fields="['project', 'employee_function']"
                  :search-fields="['name']"
                  description-field="project"
                  placeholder="Search notebooks…"
                />
                <span class="field-hint">
                  The run's ID is generated from the notebook it belongs to.
                </span>
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
                      <input type="text" v-model="mat.item_name" class="form-control table-input" :readonly="mat.from_template" :class="{ readonly: mat.from_template }" placeholder="Item Description" />
                    </td>
                    <td>
                      <input type="text" v-model="mat.uom" class="form-control table-input" :readonly="mat.from_template" :class="{ readonly: mat.from_template }" placeholder="e.g. L, mL, mg" />
                    </td>
                    <td>
                      <input type="number" v-model="mat.qty" class="form-control table-input" :readonly="mat.from_template" :class="{ readonly: mat.from_template }" min="0" step="any" />
                    </td>
                    <td>
                      <button v-if="!mat.from_template" class="delete-row-btn" @click="removeMaterial(idx)" title="Remove item">×</button>
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
                      <input type="text" v-model="eq.equipment_name" class="form-control table-input" :readonly="eq.from_template" :class="{ readonly: eq.from_template }" placeholder="Equipment Name" />
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
                      <input type="text" v-model="eq.remarks" class="form-control table-input" :readonly="eq.from_template" :class="{ readonly: eq.from_template }" placeholder="Allocation comments..." />
                    </td>
                    <td>
                      <button v-if="!eq.from_template" class="delete-row-btn" @click="removeEquipment(idx)">×</button>
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
                      <input type="text" v-model="meth.method" class="form-control table-input" :readonly="meth.from_template" :class="{ readonly: meth.from_template }" placeholder="e.g. HPLC separation" />
                    </td>
                    <td>
                      <input type="number" v-model="meth.time_to_complete" class="form-control table-input" :readonly="meth.from_template" :class="{ readonly: meth.from_template }" min="0" />
                    </td>
                    <td>
                      <button v-if="!meth.from_template" class="delete-row-btn" @click="removeMethod(idx)">×</button>
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
