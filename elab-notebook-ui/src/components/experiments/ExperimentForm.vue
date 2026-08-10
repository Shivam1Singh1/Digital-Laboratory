<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { useUserStore } from '../../stores/user'
import RichTextEditor from '../common/RichTextEditor.vue'
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
  experiment_start_date: new Date().toISOString().split('T')[0],
  experiment_end_date: '',
  employee_code: userStore.user.name,
  employee_name: userStore.user.full_name,
  
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
    
    experiment.value.title = `Run: ${doc.template_name || doc.title || doc.name}`
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
        supplier: ing.supplier
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
        checklist_items: s.checklist_items
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
        remarks: e.remarks
      }))
    }
    
    // Map methodology
    if (doc.methodology) {
      experiment.value.methodology = doc.methodology.map(m => ({
        method: m.method,
        time_to_complete: m.time_to_complete
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
    qty: 1
  })
}

const removeMaterial = (index) => {
  experiment.value.material_required.splice(index, 1)
}

const addEquipment = () => {
  experiment.value.equipment_details.push({
    equipment_name: '',
    equipment_id: '',
    remarks: ''
  })
}

const removeEquipment = (index) => {
  experiment.value.equipment_details.splice(index, 1)
}

const addMethod = () => {
  experiment.value.methodology.push({
    method: '',
    time_to_complete: 0
  })
}

const removeMethod = (index) => {
  experiment.value.methodology.splice(index, 1)
}

const saveExperiment = async () => {
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

onMounted(() => {
  loadTemplate()
  loadTeamFinancials()
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
            <div class="form-group">
              <label class="form-label">Run Title *</label>
              <input type="text" v-model="experiment.title" class="form-control" placeholder="Enter a name for this run..." required />
            </div>

            <div class="form-group-row">
              <div class="form-group">
                <label class="form-label">Project</label>
                <input type="text" :value="experiment.project" class="form-control readonly" readonly />
              </div>
              <div class="form-group">
                <label class="form-label">Employee Function</label>
                <input type="text" :value="experiment.employee_function" class="form-control readonly" readonly />
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
                <input type="date" v-model="experiment.experiment_start_date" class="form-control" />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Aim / Hypothesis *</label>
              <input type="text" v-model="experiment.aim" class="form-control" placeholder="Aim of the experiment..." />
            </div>

            <div class="form-group">
              <label class="form-label">Sub Aim</label>
              <input type="text" v-model="experiment.sub_aim" class="form-control" placeholder="Sub-aim (optional)..." />
            </div>

            <div class="form-group">
              <label class="form-label">Rationale</label>
              <textarea v-model="experiment.rationale" class="form-control textarea" rows="4" placeholder="Hypothesis rationale..."></textarea>
            </div>
          </div>
        </div>

        <!-- 2. MATERIAL REQUIRED TAB -->
        <div v-if="activeTab === 'materials'" class="tab-pane">
          <div class="pane-header-row">
            <h3 class="pane-subtitle">Required Formulation Ingredients</h3>
            <button class="btn btn-secondary btn-sm" @click="addMaterial">+ Add Material</button>
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
                  <td>
                    <input type="text" v-model="mat.item_code" class="form-control table-input" placeholder="e.g. CHEM-001" />
                  </td>
                  <td>
                    <input type="text" v-model="mat.item_name" class="form-control table-input" placeholder="Item Description" />
                  </td>
                  <td>
                    <input type="text" v-model="mat.uom" class="form-control table-input" placeholder="e.g. L, mL, mg" />
                  </td>
                  <td>
                    <input type="number" v-model="mat.qty" class="form-control table-input" min="0" step="any" />
                  </td>
                  <td>
                    <button class="delete-row-btn" @click="removeMaterial(idx)" title="Remove item">×</button>
                  </td>
                </tr>
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
            <button class="btn btn-secondary btn-sm" @click="addEquipment">+ Add Equipment</button>
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
                  <td>
                    <input type="text" v-model="eq.equipment_name" class="form-control table-input" placeholder="e.g. Centrifuge" />
                  </td>
                  <td>
                    <input type="text" v-model="eq.equipment_id" class="form-control table-input" placeholder="e.g. DEV-0089" />
                  </td>
                  <td>
                    <input type="text" v-model="eq.remarks" class="form-control table-input" placeholder="Allocation comments..." />
                  </td>
                  <td>
                    <button class="delete-row-btn" @click="removeEquipment(idx)">×</button>
                  </td>
                </tr>
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
            <button class="btn btn-secondary btn-sm" @click="addMethod">+ Add Method</button>
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
                    <input type="text" v-model="meth.method" class="form-control table-input" placeholder="e.g. HPLC separation" />
                  </td>
                  <td>
                    <input type="number" v-model="meth.time_to_complete" class="form-control table-input" min="0" />
                  </td>
                  <td>
                    <button class="delete-row-btn" @click="removeMethod(idx)">×</button>
                  </td>
                </tr>
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
