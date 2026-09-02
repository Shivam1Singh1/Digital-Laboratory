<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { useUserStore } from '../../stores/user'
import { formatAuditDate } from '../../utils/dateFormatter'
import { readServerError } from '../../utils/serverError'
import RichTextEditor from '../common/RichTextEditor.vue'
import AddRow from '../common/AddRow.vue'
import FileAttachment from '../common/FileAttachment.vue'
import LinkField from '../common/LinkField.vue'
import RawDataTab from './RawDataTab.vue'
import { showsRawDataTab } from '../../utils/rawData'
import './ExperimentForm.css'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const project = ref(route.query.project || '')
const employeeFunction = ref(route.query.employee_function || '')
const templateId = ref(route.query.template || '')


const experimentTeam = ref(route.query.experiment_team || '')
const isTeamFlow = computed(() => Boolean(experimentTeam.value))


const seedCategory = ref(route.query.experiment_category || '')
const seedParent = ref(route.query.parent_experiment || '')

const loading = ref(true)
const saving = ref(false)
const error = ref('')

const activeTab = ref('general')


const availableMaterials = ref([])
const availableEquipment = ref([])
const availableMethods = ref([])


const materialSearchStates = ref({})
const equipmentSearchStates = ref({})


const isFromTemplate = computed(() => !!experiment.value.experiment_template)

const projectName = ref('')
const employeeFunctionName = ref('')


const scientistName = computed(
  () => userStore.user.employee_name || userStore.user.full_name || '—'
)


const currentUserId = computed(() => userStore.user.name || '—')


const currentEmployeeId = computed(() => userStore.user.employee || '—')

const experiment = ref({
  title: '',
  project: project.value,
  employee_function: employeeFunction.value,
  template: templateId.value,
  experiment_template: templateId.value,
  aim: '',
  sub_aim: '',


  experiment_category: seedCategory.value,


  parent_experiment: seedParent.value,
  rationale: '',
  remark: '',


  experiment_start_date: '',
  experiment_end_date: '',


  experiment_team: experimentTeam.value,

  segment: '',
  cost_center: '',


  experiment_ingredients: [],
  experiment_parameters: [],
  experiment_protocol_steps: [],
  material_required: [],
  equipment_details: [],
  methodology: [],
  observation: '',


  protocol_steps: [],
  observations: [],


  results: '',
  observation_and_conclusion: '',
  conclusion: '',
  result: '',


  sample_details: '',
  sample_detailsgenerated: '',
  sample_generated: 0,
  sample_not_generated: 0,
  trf_no: '',
  batch_manufacturing_date: '',
  handover_date: '',
  project_code_sample: '',
  batch_volume: '',
  batch_no: '',
  storage_condition: '',
  nature_of_sample: '',
  result_attachment: [],
  quality_metrics: [],


  sub_metrics: [],
  sample: []
})


const TEMPLATE_CHILD_FIELDS = [
  'experiment_ingredients',
  'experiment_parameters',
  'experiment_protocol_steps',
  'material_required',
  'equipment_details',
  'methodology',
]

const applyTemplateClone = async (name) => {
  if (!name) return
  try {


    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.template.get_template_clone', {
      params: { template_name: name }
    })
    const { header = {}, children = {} } = res.data.message || {}

    experiment.value.template = name
    experiment.value.experiment_template = name


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
  }
}


const clearTemplateSelection = () => {
  experiment.value.template = ''
  experiment.value.experiment_template = ''
  for (const field of TEMPLATE_CHILD_FIELDS) {
    experiment.value[field] = []
  }
}

const loadTemplate = async () => {
  if (!templateId.value) {
    loading.value = false
    return
  }
  loading.value = true
  await applyTemplateClone(templateId.value)
  loading.value = false
}


const addMaterial = () => {
  experiment.value.material_required.push({
    item_code: '',
    item_name: '',
    uom: '',
    qty: 1,
    added_on: labStamp(),
    added_by: userStore.user.full_name || userStore.user.name
  })
}

const removeMaterial = (index) => {


  if (experiment.value.material_required[index]?.from_template) return
  experiment.value.material_required.splice(index, 1)
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

const removeProtocolStep = (index) => {
  experiment.value.protocol_steps.splice(index, 1)

  renumberProtocolSteps()
}

const addObservationRow = () => {
  experiment.value.observations.push({
    parameter: '',
    unit: '',
    expected_range: '',
    remarks: ''
  })
}

const removeObservationRow = (index) => {
  experiment.value.observations.splice(index, 1)
}

const addEquipment = () => {
  experiment.value.equipment_details.push({
    equipment_name: '',
    equipment_id: '',
    remarks: '',
    added_on: labStamp(),
    added_by: userStore.user.full_name || userStore.user.name
  })
}

const removeEquipment = (index) => {


  if (experiment.value.equipment_details[index]?.from_template) return
  experiment.value.equipment_details.splice(index, 1)
}

const addMethod = () => {
  experiment.value.methodology.push({
    method: '',
    time_to_complete: 0,
    added_on: labStamp(),
    added_by: userStore.user.full_name || userStore.user.name
  })
}

const removeMethod = (index) => {


  if (experiment.value.methodology[index]?.from_template) return
  experiment.value.methodology.splice(index, 1)
}

const SAVE_FALLBACK = 'Error saving experiment. Please verify all required fields.'


const withArticle = (category) =>
  `${'AEIOU'.includes((category || '').charAt(0).toUpperCase()) ? 'an' : 'a'} ${category}`

const capitalise = (text) => text.charAt(0).toUpperCase() + text.slice(1)


const listNames = (names) =>
  names.length <= 1
    ? names[0] || ''
    : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`


const missingRequiredFields = () => {
  const fields = []

  if (!project.value) {
    fields.push({
      label: 'Project',
      tab: 'general',
      message: 'Project is required — pick the project this run belongs to.',
    })
  }
  if (!employeeFunction.value) {
    fields.push({
      label: 'Employee Function',
      tab: 'general',
      message: 'Employee Function is required — pick the function this run belongs to.',
    })
  }
  if (!experiment.value.experiment_category) {
    fields.push({
      label: 'Experiment Category',
      tab: 'general',
      message: 'Experiment Category is required — pick the level this run sits at.',
    })
  }


  if (needsParent.value && !experiment.value.parent_experiment) {
    const self = withArticle(experiment.value.experiment_category)
    const above = withArticle(parentCategory.value)
    fields.push({
      label: 'Parent Experiment',
      tab: 'general',
      message: parentCandidates.value.length
        ? `${capitalise(self)} must sit under ${above} — pick its Parent Experiment.`
        : `${capitalise(self)} must sit under ${above}, and none exists for this project `
          + 'and Employee Function yet. Create one first.',
    })
  }


  if (!experiment.value.experiment_team) {
    fields.push({
      label: 'Experiment Team',
      tab: 'general',
      message: noTeamAvailable.value
        ? `No team is set up for project ${project.value || '—'} under `
          + `${employeeFunctionName.value || employeeFunction.value || 'this function'}. `
          + 'Set one up in Team Setup before starting a run.'
        : 'Experiment Team is required — the run ID is generated from it.',
    })
  }
  if (!(experiment.value.aim || '').trim()) {
    fields.push({ label: 'Aim / Hypothesis', tab: 'details', message: 'Aim / Hypothesis is required.' })
  }


  if (!(experiment.value.sub_aim || '').trim()) {
    fields.push({
      label: 'Sub Aim',
      tab: 'details',
      message: isFromTemplate.value
        ? 'Sub Aim is required, and this template does not provide one - enter it before saving.'
        : 'Sub Aim is required.',
    })
  }

  return fields
}


const validateExperiment = () => {


  const rowsToCheck = experiment.value.material_required || []
  const typedPerRow = rowsToCheck.map(
    (_, idx) => (materialSearchStates.value[idx]?.search || '').trim()
  )
  rowsToCheck.forEach((row, idx) => resolveMaterialSearch(row, idx))


  const missing = missingRequiredFields()
  if (missing.length) {
    activeTab.value = missing[0].tab
    return missing.length === 1
      ? missing[0].message
      : `${listNames(missing.map((f) => f.label))} are required.`
  }

  if (
    experiment.value.experiment_end_date &&
    experiment.value.experiment_start_date &&
    experiment.value.experiment_end_date < experiment.value.experiment_start_date
  ) {
    activeTab.value = 'general'
    return 'End Date cannot be before the Start Date.'
  }

  for (let i = 0; i < rowsToCheck.length; i++) {
    const row = rowsToCheck[i]
    if (!row.item_code) {
      activeTab.value = 'materials'
      const typed = typedPerRow[i]
      return typed
        ? `Material Required row ${i + 1}: "${typed}" is not an item - select an item from the list, or remove the row.`
        : `Material Required row ${i + 1}: select an item from the list, or remove the row.`
    }
    if (!Number(row.qty)) {
      activeTab.value = 'materials'
      return `Material Required row ${i + 1}: enter a quantity greater than zero.`
    }
  }

  return ''
}

const saveExperiment = async () => {


  const validationError = validateExperiment()
  if (validationError) {
    error.value = validationError
    return
  }

  saving.value = true
  error.value = ''

  renumberProtocolSteps()
  try {
    const payload = {
      ...experiment.value,
      doctype: 'Lab Experiment'
    }
    const res = await axios.post('/api/resource/Lab%20Experiment', payload)
    if (res.data && res.data.data) {
      const newId = res.data.data.name
      createdId.value = newId


      if (selectedChildren.value.size) {
        try {
          await axios.post(`/api/method/${HIERARCHY_API}.link_child_experiments`, {
            parent: newId,
            children: Array.from(selectedChildren.value)
          })
        } catch (linkErr) {
          console.error('Failed to link child experiments:', linkErr)
          error.value = `Run ${newId} was created, but no child experiments were linked: `
            + readServerError(linkErr, 'the server rejected the batch.')
            + ` Open ${newId} and link them from its Experiment Tree tab.`
          return
        }
      }

      router.push(`/experiments/${encodeURIComponent(newId)}`)
    }
  } catch (err) {
    console.error('Failed to save experiment:', err)
    error.value = readServerError(err, SAVE_FALLBACK)
  } finally {
    saving.value = false
  }
}


const serverToday = ref('')
const serverTimeZone = ref('')


const serverSkewMs = ref(0)

const loadServerNow = async () => {
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.user.get_server_now')
    const stamp = res.data.message || {}
    serverToday.value = stamp.today || ''
    serverTimeZone.value = stamp.time_zone || ''
    if (stamp.today) experiment.value.experiment_start_date = stamp.today
    if (stamp.now) {


      serverSkewMs.value = new Date(stamp.now.replace(' ', 'T')).getTime() - Date.now()
    }
  } catch (err) {
    console.error('Failed to read the server clock:', err)


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


const labStamp = () => {
  const d = new Date(Date.now() + serverSkewMs.value)
  const pad = (n) => String(n).padStart(2, '0')
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  )
}

const loadProjectAndFunctionNames = async () => {


  projectName.value = ''
  employeeFunctionName.value = ''
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

    const itemsRes = await axios.get('/api/resource/Item?fields=["name","item_name","uom"]&limit_page_length=500')
    availableMaterials.value = itemsRes.data.data || []


    const equipmentRes = await axios.get('/api/resource/Item?filters=[["item_group","=","Equipment"]]&fields=["name","item_name","uom"]&limit_page_length=500')
    availableEquipment.value = equipmentRes.data.data || []
  } catch (err) {
    console.error('Failed to load available items:', err)
  }
}

const selectMaterial = (mat, idx, item) => {
  mat.item_code = item.name
  mat.item_name = item.item_name || item.name
  mat.uom = item.uom || ''
  if (materialSearchStates.value[idx]) {
    materialSearchStates.value[idx].search = item.name
  }
}


const findMaterialItem = (text) => {
  const query = (text || '').trim().toLowerCase()
  if (!query) return null
  const exact = availableMaterials.value.find((m) => m.name.toLowerCase() === query)
  if (exact) return exact
  const matches = availableMaterials.value.filter(
    (m) =>
      m.name.toLowerCase().includes(query) ||
      (m.item_name || '').toLowerCase().includes(query)
  )

  return matches.length === 1 ? matches[0] : null
}

const resolveMaterialSearch = (mat, idx) => {
  const state = materialSearchStates.value[idx]
  if (!state) return
  const typed = (state.search || '').trim()

  if (typed && typed === mat.item_code) return

  const item = findMaterialItem(typed)
  if (item) {
    selectMaterial(mat, idx, item)
    return
  }


  state.search = ''
  mat.item_code = ''
}

const selectEquipment = (eq, item) => {
  eq.equipment_id = item.name
  eq.equipment_name = item.item_name || item.name
}


const segmentOptions = ref([])
const costCenterOptions = ref([])
const financialsLoaded = ref(false)
const fetchedFromTeam = ref(false)


let financialsRun = 0

const loadFinancials = async () => {
  const run = ++financialsRun
  segmentOptions.value = []
  costCenterOptions.value = []
  financialsLoaded.value = false
  fetchedFromTeam.value = false

  if (!employeeFunction.value) {
    experiment.value.segment = ''
    experiment.value.cost_center = ''
    financialsLoaded.value = true
    return
  }

  let teamFin = {}
  try {
    const [fnRes, teamRes] = await Promise.all([
      axios.get('/api/method/elab_notebook.elab_notebook.api.experiment_team.get_segments_and_cost_centers', {
        params: { employee_function: employeeFunction.value },
      }),


      project.value
        ? axios.get('/api/method/elab_notebook.elab_notebook.api.experiment_team.get_team_financials', {
            params: {
              project: project.value,
              employee_function: employeeFunction.value,
              team: experiment.value.experiment_team || undefined,
            },
          })
        : Promise.resolve({ data: {} }),
    ])
    if (run !== financialsRun) return
    segmentOptions.value = fnRes.data.message?.segments || []
    costCenterOptions.value = fnRes.data.message?.cost_centers || []
    teamFin = teamRes.data.message || {}
  } catch (err) {
    if (run !== financialsRun) return
    console.error('Failed to load segments and cost centres:', err)
  } finally {
    if (run === financialsRun) financialsLoaded.value = true
  }


  const settle = (optionsRef, teamValue) => {
    if (teamValue) {
      if (!optionsRef.value.includes(teamValue)) {
        optionsRef.value = [...optionsRef.value, teamValue].sort()
      }
      return teamValue
    }
    return optionsRef.value.length === 1 ? optionsRef.value[0] : ''
  }

  experiment.value.segment = settle(segmentOptions, teamFin.segment)
  experiment.value.cost_center = settle(costCenterOptions, teamFin.cost_center)
  fetchedFromTeam.value = Boolean(teamFin.segment || teamFin.cost_center)
}

const financialsHint = (options, kind) => {
  if (!employeeFunction.value) return 'Set once an Employee Function is picked.'
  if (!financialsLoaded.value) return 'Looking up this run’s bookings…'
  if (fetchedFromTeam.value) return `Fetched from this run’s Experiment Team — change it only if this run books elsewhere.`
  if (!options.length) return `This Employee Function has no ${kind} mapped to it.`
  return options.length === 1
    ? `This function’s only ${kind}, filled in for you.`
    : `The ${kind}s this Employee Function books against — pick the one this run belongs to.`
}

const segmentHint = computed(() => financialsHint(segmentOptions.value, 'Segment'))
const costCenterHint = computed(() => financialsHint(costCenterOptions.value, 'Cost Centre'))


const teamOptions = ref([])
const teamsLoaded = ref(false)


const noTeamAvailable = computed(
  () =>
    Boolean(project.value) &&
    teamsLoaded.value &&
    teamOptions.value.length === 0 &&
    !experiment.value.experiment_team
)

const teamHint = computed(() => {
  if (!project.value) return 'Pick a Project above — its teams are listed here.'
  if (!teamsLoaded.value) return 'Looking up the teams for this project…'
  if (teamOptions.value.length === 0) {
    return noTeamAvailable.value
      ? `No team is set up for project ${project.value || '—'} under `
        + `${employeeFunctionName.value || employeeFunction.value || 'this function'} — set one up first.`
      : 'This run is being created for this team.'
  }
  if (teamOptions.value.length === 1) {
    return "Pre-selected from this project's only team under this function — change it if that is not the one."
  }
  return `This project has ${teamOptions.value.length} teams under this function — confirm which one this run belongs to.`
})


const teamLabel = (t) => (t.team_name ? `${t.team_name} — ${t.name}` : t.name)


const teamNameDisplay = computed(() => {
  if (!experiment.value.experiment_team) return '—'
  const match = teamOptions.value.find((t) => t.name === experiment.value.experiment_team)
  if (!match) return teamsLoaded.value ? '—' : 'Loading…'
  return match.team_name || 'Not named'
})

const loadTeamsForProject = async () => {


  teamOptions.value = []
  teamsLoaded.value = false
  if (!project.value) {
    teamsLoaded.value = true
    return
  }
  try {


    const filters = { project: project.value, status: 'Active' }
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


    if (!experiment.value.experiment_team && teamOptions.value.length === 1) {
      experiment.value.experiment_team = teamOptions.value[0].name
    }
  } catch (err) {
    console.error('Failed to look up Experiment Team', err)
  } finally {
    teamsLoaded.value = true
  }
}


watch(() => experiment.value.experiment_team, loadFinancials)


const teamSetupUrl = computed(() => ({
  path: '/elab-notebook',
  query: {
    create: 1,
    ...(project.value ? { project: project.value } : {}),
    ...(employeeFunction.value ? { employee_function: employeeFunction.value } : {}),
  },
}))


const authorizedProjects = ref([])
const projectsLoaded = ref(false)


const loadAuthorizedProjects = async () => {
  try {
    const res = await axios.get(
      '/api/method/elab_notebook.elab_notebook.api.experiment_team.get_authorized_projects_for_user',
      { params: employeeFunction.value ? { employee_function: employeeFunction.value } : {} }
    )
    authorizedProjects.value = res.data.message || []
  } catch (err) {
    console.error('Failed to load authorized projects:', err)
    authorizedProjects.value = []
  } finally {
    projectsLoaded.value = true
  }
}

const projectSearch = async (txt) => {
  const term = (txt || '').toLowerCase()
  if (!term) return authorizedProjects.value
  return authorizedProjects.value.filter(
    (p) =>
      p.name.toLowerCase().includes(term) ||
      String(p.project_name || '').toLowerCase().includes(term)
  )
}

const projectHint = computed(() => {
  if (!projectsLoaded.value) return 'Looking up the projects you can start a run for…'
  if (!authorizedProjects.value.length) {


    if (employeeFunction.value) {
      return `No project under ${employeeFunction.value} is available to you. `
        + 'Change the Employee Function, or set up an Experiment Team on one of its projects.'
    }
    return 'No project is available to you: a run needs an Experiment Team you are on '
      + '(or head). Set one up in Team Setup first.'
  }
  if (employeeFunction.value) {
    return `Required. Showing projects under ${employeeFunction.value} that you belong to, or head.`
  }
  return 'Required. Only projects with a team you belong to, or head, are listed.'
})


const myFunctions = ref([])
const functionsLoaded = ref(false)


const projectFunctions = ref([])

const functionPool = computed(() =>
  myFunctions.value.length ? myFunctions.value : projectFunctions.value
)

const usingProjectFunctions = computed(
  () => functionsLoaded.value && !myFunctions.value.length
)

const loadMyFunctions = async () => {
  try {
    const res = await axios.get(
      '/api/method/elab_notebook.elab_notebook.api.employee_function.get_current_employee_function'
    )
    myFunctions.value = (res.data.message || {}).functions || []
  } catch (err) {
    console.error('Failed to load employee functions:', err)
    myFunctions.value = []
  } finally {
    functionsLoaded.value = true
  }


  if (!employeeFunction.value && myFunctions.value.length === 1) {
    employeeFunction.value = myFunctions.value[0].name
  }
}

const loadProjectFunctions = async () => {
  projectFunctions.value = []
  if (!project.value || myFunctions.value.length) return
  try {
    const res = await axios.get(
      '/api/method/elab_notebook.elab_notebook.api.experiment_team.get_authorized_functions_for_project',
      { params: { project: project.value } }
    )
    projectFunctions.value = (res.data.message || []).map((name) => ({ name, function_name: '' }))
  } catch (err) {
    console.error('Failed to load functions for project:', err)
    projectFunctions.value = []
  }
}

const employeeFunctionSearch = async (txt) => {
  const term = (txt || '').toLowerCase()
  const pool = functionPool.value
  if (!term) return pool
  return pool.filter(
    (f) =>
      f.name.toLowerCase().includes(term) ||
      String(f.function_name || '').toLowerCase().includes(term)
  )
}

const employeeFunctionHint = computed(() => {
  if (!functionsLoaded.value) return 'Looking up your Employee Function…'
  if (myFunctions.value.length === 1) {
    return 'Your only active Employee Function, filled in for you — change it if this run belongs elsewhere.'
  }
  if (myFunctions.value.length) {
    return `You have ${myFunctions.value.length} active Employee Functions — pick the one this run belongs to.`
  }
  if (!project.value) {
    return 'No Employee Function is assigned to your employee record. Pick a project first, '
      + "and this falls back to that project's functions."
  }
  return projectFunctions.value.length
    ? 'No Employee Function is assigned to your employee record, so these are the functions '
      + 'this project offers you. Ask HR to map your Employee record.'
    : 'No Employee Function is assigned to your employee record, and this project offers none.'
})


watch(employeeFunction, async () => {
  await loadAuthorizedProjects()
  if (project.value && !authorizedProjects.value.some((p) => p.name === project.value)) {
    project.value = ''
  }
})


watch([project, employeeFunction], () => {
  experiment.value.project = project.value
  experiment.value.employee_function = employeeFunction.value
  experiment.value.experiment_team = ''
  experiment.value.segment = ''
  experiment.value.cost_center = ''
  clearTemplateSelection()

  loadProjectAndFunctionNames()
  loadFinancials()
  loadTeamsForProject()
  loadTemplateOptions()
  loadProjectFunctions()
  loadParentCandidates()
  loadChildCandidates()
})


const HIERARCHY_API = 'elab_notebook.elab_notebook.api.hierarchy'

const categoryOptions = ref([])
const childCandidates = ref([])
const selectedChildren = ref(new Set())
const childFilter = ref('')
const loadingChildren = ref(false)

const parentCandidates = ref([])
const loadingParents = ref(false)
const parentsLoaded = ref(false)


const createdId = ref('')

const currentCategoryOption = computed(
  () =>
    categoryOptions.value.find((o) => o.category === experiment.value.experiment_category) || null
)

const childCategory = computed(() => currentCategoryOption.value?.child_category || '')


const parentCategory = computed(() => {
  const current = currentCategoryOption.value
  if (!current) return ''
  return categoryOptions.value.find((o) => o.child_category === current.category)?.category || ''
})


const needsParent = computed(() => Boolean(parentCategory.value))
const usesTemplate = computed(() => Boolean(currentCategoryOption.value?.is_leaf))


const TEMPLATE_TABS = ['materials', 'equipment', 'methodology', 'procedure']


const visibleTabs = computed(() => [
  { key: 'general', label: 'Template' },
  { key: 'details', label: 'Details' },


  ...(showsRawDataTab(experiment.value.experiment_category)
    ? [{ key: 'rawdata', label: 'Raw Data' }]
    : []),


  { key: 'result', label: 'Result' },
  ...(usesTemplate.value
    ? [


        { key: 'materials', label: 'Material & Equipment' },


      ]
    : []),
  { key: 'hierarchy', label: 'Experiment Hierarchy' },
  { key: 'report', label: 'Report' },
])


const canPickChildren = computed(
  () => Boolean(childCategory.value && project.value && employeeFunction.value)
)

const childPickerHint = computed(() => {
  if (!experiment.value.experiment_category) {
    return 'Pick an Experiment Category on the Template tab first.'
  }
  if (!childCategory.value) {
    return `${experiment.value.experiment_category} is the lowest level — it has no children to link.`
  }
  if (!employeeFunction.value) {
    return 'This run has no Employee Function, so no child experiments can be resolved. '
      + 'Linking stays available from the Experiment Tree tab once one is set.'
  }
  if (!project.value) {
    return 'This run has no Project, so no child experiments can be resolved.'
  }
  return `Unlinked ${childCategory.value}s in project ${project.value} under ${employeeFunction.value}. `
    + 'Attaching is optional — you can also link them later from the Experiment Tree tab.'
})

const filteredChildCandidates = computed(() => {
  const needle = childFilter.value.trim().toLowerCase()
  if (!needle) return childCandidates.value
  return childCandidates.value.filter((c) =>
    [c.name, c.title, c.aim].some((v) => (v || '').toLowerCase().includes(needle))
  )
})

const toggleChild = (name) => {

  const next = new Set(selectedChildren.value)
  next.has(name) ? next.delete(name) : next.add(name)
  selectedChildren.value = next
}

const loadCategoryOptions = async () => {
  try {
    const res = await axios.get(`/api/method/${HIERARCHY_API}.get_category_options`)
    categoryOptions.value = res.data.message || []
  } catch (err) {
    console.error('Failed to load experiment categories:', err)
  }
}

const loadChildCandidates = async () => {
  selectedChildren.value = new Set()
  childFilter.value = ''
  childCandidates.value = []
  if (!canPickChildren.value) return

  loadingChildren.value = true
  try {
    const res = await axios.get(`/api/method/${HIERARCHY_API}.get_available_children`, {
      params: {
        project: project.value,
        employee_function: employeeFunction.value,
        parent_category: experiment.value.experiment_category,
      },
    })
    childCandidates.value = res.data.message || []
  } catch (err) {
    console.error('Failed to load available child experiments:', err)
    childCandidates.value = []
  } finally {
    loadingChildren.value = false
  }
}

const parentLabel = (row) => {
  const sub = row.title || row.aim || ''
  return sub ? `${row.name} — ${sub}` : row.name
}

const parentPickerHint = computed(() => {
  if (!parentCategory.value) return ''


  if (!project.value || !employeeFunction.value) {
    const missing = !project.value && !employeeFunction.value
      ? 'Project or Employee Function'
      : (!project.value ? 'Project' : 'Employee Function')
    return `This run has no ${missing} yet, so no parent can be resolved — fill it in above.`
  }
  if (loadingParents.value || !parentsLoaded.value) return 'Looking up the level above…'
  if (!parentCandidates.value.length) {
    return `No ${parentCategory.value} exists for project ${project.value} under `
      + `${employeeFunction.value} yet — create one first, then start this run under it.`
  }
  return `${parentCategory.value}s in project ${project.value} under ${employeeFunction.value}. `
    + 'Required: this level always sits under one.'
})

const loadParentCandidates = async () => {
  parentCandidates.value = []
  parentsLoaded.value = false

  if (!needsParent.value || !project.value || !employeeFunction.value) {
    parentsLoaded.value = true
    return
  }

  loadingParents.value = true
  try {
    const res = await axios.get(`/api/method/${HIERARCHY_API}.get_parent_candidates`, {
      params: {
        project: project.value,
        employee_function: employeeFunction.value,
        category: experiment.value.experiment_category,
      },
    })
    parentCandidates.value = res.data.message || []

    if (!parentCandidates.value.some((c) => c.name === experiment.value.parent_experiment)) {
      experiment.value.parent_experiment = ''
    }
  } catch (err) {
    console.error('Failed to load parent experiments:', err)
    parentCandidates.value = []
  } finally {
    loadingParents.value = false
    parentsLoaded.value = true
  }
}


const templateOptions = ref([])
const templatesLoaded = ref(false)

const loadTemplateOptions = async () => {
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.template.get_experiment_templates', {
      params: { filters: JSON.stringify({ status: ['!=', 'Archived'] }) },
    })
    templateOptions.value = (res.data.message || []).filter((t) => {
      if (employeeFunction.value && t.employee_function && t.employee_function !== employeeFunction.value) return false
      if (t.project && t.project !== project.value) return false
      return true
    })
  } catch (err) {
    console.error('Failed to load templates:', err)
    templateOptions.value = []
  } finally {
    templatesLoaded.value = true
  }
}

const templateLabel = (t) => t.template_name || t.title || t.name


const onTemplatePicked = async (name) => {
  clearTemplateSelection()
  if (name) await applyTemplateClone(name)
}


watch(() => experiment.value.experiment_category, () => {
  loadChildCandidates()
  loadParentCandidates()


  if (!categoryOptions.value.length) return

  if (!needsParent.value) experiment.value.parent_experiment = ''
  if (!usesTemplate.value) clearTemplateSelection()
  if (!usesTemplate.value && TEMPLATE_TABS.includes(activeTab.value)) activeTab.value = 'general'


  if (activeTab.value === 'rawdata' && !showsRawDataTab(experiment.value.experiment_category)) {
    activeTab.value = 'general'
  }
})

onMounted(async () => {
  loadServerNow()
  loadFinancials()
  loadProjectAndFunctionNames()
  loadAvailableItems()
  loadTeamsForProject()
  loadTemplateOptions()
  loadAuthorizedProjects()


  await loadMyFunctions()
  loadProjectFunctions()
  await loadCategoryOptions()


  if (experiment.value.experiment_category) {
    loadParentCandidates()
    loadChildCandidates()
  }


  if (experiment.value.experiment_category && !usesTemplate.value) {
    clearTemplateSelection()
    loading.value = false
    return
  }
  await loadTemplate()
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
        <p class="page-subtitle">
          <template v-if="experiment.template">Pre-filled from template: {{ experiment.template }}</template>
          <!-- Started from the run above: say which one, since the parent is the
               whole reason this form arrived pre-filled. Falls through to the
               line below if that parent turned out not to be a candidate. -->
          <template v-else-if="seedCategory && experiment.parent_experiment">
            {{ experiment.experiment_category }} under {{ experiment.parent_experiment }}
          </template>
          <template v-else-if="experiment.experiment_category">{{ experiment.experiment_category }} — entered by hand</template>
          <template v-else>Pick an Experiment Category to start</template>
        </p>
      </div>

      <div class="page-header-right">
        <button class="btn btn-secondary" @click="router.back()">Cancel</button>
        <!-- Once the run exists, saving again would create a second one. The only
             way forward is the run itself. -->
        <router-link
          v-if="createdId"
          :to="`/experiments/${encodeURIComponent(createdId)}`"
          class="btn btn-primary"
        >
          Open {{ createdId }}
        </router-link>
        <!-- Enabled even with fields still empty: a disabled Save cannot tell
             anyone *why* it is disabled, and this form's whole answer to a
             half-filled run is the message validateExperiment builds. -->
        <button
          v-else
          class="btn btn-primary"
          :disabled="saving || loading"
          @click="saveExperiment"
        >
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
      <!-- Material Required, Equipment Details and Methodology only exist on the
           leaf level, which is the only one that can be run from a template. See
           visibleTabs. -->
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

      <!-- Tab Content Area -->
      <div class="tab-content">
        <!-- 1. GENERAL TAB -->
        <div v-if="activeTab === 'general'" class="tab-pane">
          <div class="pane-grid">
            <!-- The order of this pane is its dependency order. Project comes
                 first because everything below is resolved from it: the teams to
                 choose between, the runs this one can sit under, the templates in
                 scope. A field that says "pick a Project first" now says it below
                 the Project field, not above it. -->
            <div class="form-group-row two-columns">
              <div class="form-group">
                <label class="form-label">Project *</label>
                <LinkField
                  v-model="project"
                  :search-fn="projectSearch"
                  description-field="project_name"
                  :empty-hint="projectsLoaded ? 'No matching project' : 'Loading…'"
                  placeholder="Search your projects…"
                />
                <span
                  class="field-hint"
                  :class="{ 'field-hint-error': projectsLoaded && !authorizedProjects.length }"
                >{{ projectHint }}</span>
              </div>
              <!-- Second because it is the other half of the scope, and because
                   it is usually already answered: it fills itself in from the
                   signed-in user. -->
              <div class="form-group">
                <label class="form-label">Employee Function *</label>
                <LinkField
                  v-model="employeeFunction"
                  :search-fn="employeeFunctionSearch"
                  description-field="function_name"
                  :empty-hint="functionsLoaded ? 'No matching function' : 'Loading…'"
                  placeholder="Search your functions…"
                />
                <span
                  class="field-hint"
                  :class="{ 'field-hint-error': usingProjectFunctions && !functionPool.length }"
                >{{ employeeFunctionHint }}</span>
              </div>
            </div>

            <div class="form-group-row two-columns">
              <!-- Third: the level decides what the rest of this form asks for -
                   whether a parent is needed at all, whether a template applies,
                   which tabs exist. Fixed once the run is saved. -->
              <div class="form-group">
                <label class="form-label">Experiment Category *</label>
                <select v-model="experiment.experiment_category" class="form-control">
                  <option value="">Select a level…</option>
                  <option v-for="opt in categoryOptions" :key="opt.category" :value="opt.category">
                    {{ opt.category }}
                  </option>
                </select>
                <span class="field-hint">
                  Fixed once this run is saved, and it decides what the rest of this
                  form asks for.
                </span>
              </div>

              <!-- Fourth, and only when the level takes one: a Master Experiment
                   sits under nothing, and api/hierarchy.assert_parent_presence
                   rejects a parent on it server-side. Its candidates come from
                   the project and function above, which is why it follows them. -->
              <div v-if="needsParent" class="form-group">
                <label class="form-label">Link to Parent Experiment *</label>
                <select
                  v-model="experiment.parent_experiment"
                  class="form-control"
                  :disabled="!parentsLoaded || !parentCandidates.length"
                >
                  <option value="">
                    {{ parentsLoaded ? `Select the ${parentCategory} this run sits under…` : 'Loading…' }}
                  </option>
                  <option v-for="p in parentCandidates" :key="p.name" :value="p.name">
                    {{ parentLabel(p) }}
                  </option>
                </select>
                <span
                  class="field-hint"
                  :class="{ 'field-hint-error': parentsLoaded && !parentCandidates.length }"
                >{{ parentPickerHint }}</span>
              </div>
            </div>

            <div class="form-group-row two-columns">
              <!-- Fifth: the teams on offer are the ones under the project and
                   function above. -->
              <div class="form-group">
                <label class="form-label">Experiment Team *</label>
                <!-- Always a picker, at every level: the team is confirmed here,
                     never settled off-screen. A single candidate (or the team
                     flow's URL value) pre-selects it, it does not lock it. -->
                <select
                  v-model="experiment.experiment_team"
                  class="form-control"
                  :disabled="!teamsLoaded || (!teamOptions.length && !experiment.experiment_team)"
                >
                  <option value="">{{ teamsLoaded ? 'Select a team…' : 'Loading…' }}</option>
                  <option
                    v-if="experiment.experiment_team && !teamOptions.some((t) => t.name === experiment.experiment_team)"
                    :value="experiment.experiment_team"
                  >
                    {{ experiment.experiment_team }}
                  </option>
                  <option v-for="t in teamOptions" :key="t.name" :value="t.name">
                    {{ teamLabel(t) }}
                  </option>
                </select>
                <span class="field-hint" :class="{ 'field-hint-error': noTeamAvailable }">{{ teamHint }}</span>
                <!-- One way out, not two. Team creation lives in Team Setup and
                     only there: this form used to carry its own copy of the whole
                     thing - name field, roster checkboxes, save_team call - which
                     was the same feature maintained twice. The link seeds the
                     project and function it already knows and opens Team Setup's
                     own dialog, so nothing is retyped on arrival. -->
                <div v-if="noTeamAvailable" class="team-recovery">
                  <router-link :to="teamSetupUrl" class="btn btn-primary btn-sm">
                    Set up a team for this project
                  </router-link>
                </div>
              </div>

              <!-- Only the leaf level runs from a template, and even there it is
                   optional. At every other level the field is absent altogether
                   rather than showing a box that says it does not apply: those
                   levels cannot carry cloned content at all, so there is nothing
                   to tell the user about. -->
              <div v-if="usesTemplate" class="form-group">
                <label class="form-label">Template</label>
                <select
                  :value="experiment.template"
                  class="form-control"
                  :disabled="!templatesLoaded"
                  @change="onTemplatePicked($event.target.value)"
                >
                  <option value="">
                    {{ templatesLoaded ? 'No template — enter this run by hand' : 'Loading…' }}
                  </option>
                  <option v-for="t in templateOptions" :key="t.name" :value="t.name">
                    {{ templateLabel(t) }}
                  </option>
                </select>
                <span class="field-hint">
                  Optional. Picking one copies its materials, equipment and methodology
                  onto this run; leaving it blank starts an empty run.
                </span>
              </div>
            </div>

            <!-- Everything the three pickers above resolve to, read-only and
                 grouped: nothing here is answered by the user, so nothing here
                 sits between two fields that are. -->
            <div class="form-group-row three-columns">
              <div class="form-group">
                <label class="form-label">Project Name</label>
                <input type="text" :value="projectName || 'N/A'" class="form-control readonly" readonly />
              </div>
              <div class="form-group">
                <label class="form-label">Function Name</label>
                <input type="text" :value="employeeFunctionName || 'N/A'" class="form-control readonly" readonly />
              </div>
              <!-- The team's own name, beside the id picked above. Teams created
                   before the field existed have none, and say so rather than
                   showing blank. -->
              <div class="form-group">
                <label class="form-label">Team Name</label>
                <input type="text" :value="teamNameDisplay" class="form-control readonly" readonly />
              </div>
            </div>

            <div class="form-group-row two-columns">
              <!-- Display only. The stored value is stamped server-side from the
                   session at insert, so this shows who that will resolve to. -->
              <div class="form-group">
                <label class="form-label">Scientist (Lead)</label>
                <input type="text" :value="scientistName" class="form-control readonly" readonly />
              </div>
              <!-- The account the run is filed under. Frappe writes it to `owner`
                   on insert and the Employee behind it to employee_code /
                   employee_name (LabExperiment.set_creator_identity), so this is
                   shown rather than posted - the client does not get a say in
                   who authored a run. -->
              <div class="form-group">
                <label class="form-label">Created By</label>
                <input type="text" :value="currentUserId" class="form-control readonly" readonly />
              </div>
            </div>

            <!-- A Date, not a datetime: the doctype stores the day the run
                 started, so a clock face here was promising a precision that was
                 thrown away on save. The start is the site's today; the end is
                 the one of the two the user fills in, and stays open because a
                 run rarely knows its last day on its first. -->
            <div class="form-group-row two-columns">
              <div class="form-group">
                <label class="form-label">Start Date</label>
                <input
                  type="date"
                  :value="experiment.experiment_start_date"
                  class="form-control readonly"
                  readonly
                />
                <span class="field-hint">
                  Today on the lab's clock<template v-if="serverTimeZone"> ({{ serverTimeZone }})</template>.
                </span>
              </div>
              <div class="form-group">
                <label class="form-label">End Date</label>
                <input
                  type="date"
                  v-model="experiment.experiment_end_date"
                  :min="experiment.experiment_start_date || undefined"
                  class="form-control"
                  @click="openDatePicker"
                  @focus="openDatePicker"
                />
                <span class="field-hint">
                  Optional — click the field to pick a date from the calendar. Leave it
                  empty while the run is still going, and set it when the work is done.
                </span>
              </div>
            </div>

            <!-- Both come from the Employee Function above, which is where the
                 organisation books this work. Filled in when the function leaves
                 no choice, offered as a picker when it maps more than one -
                 never typed by hand, and never carried over from another
                 function when the signed-in user changes. -->
            <div class="form-group-row two-columns">
              <div class="form-group">
                <label class="form-label">Segment</label>
                <select
                  v-model="experiment.segment"
                  class="form-control"
                  :disabled="!financialsLoaded || !segmentOptions.length"
                >
                  <option value="">
                    {{ financialsLoaded ? (segmentOptions.length ? 'Select a segment…' : 'None') : 'Loading…' }}
                  </option>
                  <option v-for="s in segmentOptions" :key="s" :value="s">{{ s }}</option>
                </select>
                <span class="field-hint">{{ segmentHint }}</span>
              </div>
              <div class="form-group">
                <label class="form-label">Cost Centre</label>
                <select
                  v-model="experiment.cost_center"
                  class="form-control"
                  :disabled="!financialsLoaded || !costCenterOptions.length"
                >
                  <option value="">
                    {{ financialsLoaded ? (costCenterOptions.length ? 'Select a cost centre…' : 'None') : 'Loading…' }}
                  </option>
                  <option v-for="c in costCenterOptions" :key="c" :value="c">{{ c }}</option>
                </select>
                <span class="field-hint">{{ costCenterHint }}</span>
              </div>
            </div>

          </div>
        </div>

        <!-- 2. DETAILS TAB -->
        <!-- The run's write-up: what it sets out to do and what was seen. Split
             out of Template so that tab carries the run's setup alone. -->
        <div v-if="activeTab === 'details'" class="tab-pane">
          <div class="pane-grid">
            <!-- The run's own title. The field has always existed on Lab
                 Experiment (`title`) but nothing ever asked for one, so every
                 run carried an empty title and the record header had nothing to
                 print. It is what the run is called; the Aim below is what it
                 sets out to show. -->
            <div class="form-group-row two-columns">
              <div class="form-group">
                <label class="form-label">Experiment Title</label>
                <input
                  type="text"
                  v-model="experiment.title"
                  class="form-control"
                  placeholder="What this run is called…"
                  :readonly="isFromTemplate"
                  :class="{ readonly: isFromTemplate }"
                />
                <span class="field-hint">
                  <template v-if="isFromTemplate">Taken from the selected template.</template>
                  <template v-else>Shown as this run's heading once it is saved. Optional — the Aim stands in when it is blank.</template>
                </span>
              </div>
              <!-- Who the run is filed under, as stored: the Employee id comes
                   from the signed-in user's Employee record at insert
                   (LabExperiment.set_creator_identity) and is fixed afterwards. -->
              <div class="form-group">
                <label class="form-label">Employee ID (Creator)</label>
                <input type="text" :value="currentEmployeeId" class="form-control readonly" readonly />
                <span class="field-hint">
                  Stamped from your Employee record when the run is saved — {{ scientistName }}.
                </span>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Aim / Hypothesis *</label>
              <textarea
                v-model="experiment.aim"
                class="form-control textarea"
                :readonly="isFromTemplate"
                :class="{ readonly: isFromTemplate }"
                rows="3"
                placeholder="Aim of the experiment..."
              ></textarea>
              <span v-if="isFromTemplate" class="field-hint">Fixed by the selected template.</span>
            </div>

            <!-- Sub Aim stays editable even on a template run: it is mandatory on
                 Lab Experiment but optional on Experiment Template, so a template
                 can arrive without one and this is the only place to supply it. -->
            <div class="form-group">
              <label class="form-label">Sub Aim *</label>
              <textarea
                v-model="experiment.sub_aim"
                class="form-control textarea"
                rows="2"
                placeholder="Sub-aim of the experiment..."
              ></textarea>
            </div>

            <div class="form-group">
              <label class="form-label">Rationale</label>
              <textarea
                v-model="experiment.rationale"
                class="form-control textarea"
                :readonly="isFromTemplate"
                :class="{ readonly: isFromTemplate }"
                rows="3"
                placeholder="Hypothesis rationale..."
              ></textarea>
            </div>

            <!-- Same two tables the detail page carries, in the same order, so a
                 run can be written up as it is created instead of being saved
                 and then reopened. Both optional: a run saves with them empty,
                 and nothing on the server reads either one. -->
            <div class="form-group stacked-field">
              <label class="form-label">Protocol Steps</label>
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
                      <!-- Positional, like the Observation table below. step_no
                           is kept equal to it by renumberProtocolSteps. -->
                      <td class="text-center">{{ idx + 1 }}</td>
                      <td>
                        <input
                          type="text"
                          v-model="step.instruction"
                          class="form-control table-input"
                          placeholder="What to do at this step…"
                        />
                      </td>
                      <td>
                        <input
                          type="number"
                          v-model="step.expected_duration"
                          class="form-control table-input"
                          min="0"
                          placeholder="seconds"
                        />
                      </td>
                      <td class="text-center">
                        <input type="checkbox" v-model="step.is_critical" :true-value="1" :false-value="0" />
                      </td>
                      <!-- Uploads through Frappe's upload_file, like the Raw Data
                           tab's attachment rows and the rich-text editor's attach
                           button. The bound value is still the stored file_url. -->
                      <td>
                        <FileAttachment v-model="step.attachment" />
                      </td>
                      <td>
                        <button class="delete-row-btn" title="Delete step" @click="removeProtocolStep(idx)">×</button>
                      </td>
                    </tr>
                    <tr v-if="experiment.protocol_steps.length === 0">
                      <td colspan="6" class="empty-table-cell">No Data</td>
                    </tr>
                    <tr class="add-row-tr">
                      <td colspan="6"><AddRow label="Add Step" @add="addProtocolStep" /></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="form-group stacked-field">
              <label class="form-label">Observation Table</label>
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
                      <!-- Positional, like the doctype grid's own idx - this child
                           table has no No. column of its own. -->
                      <td class="text-center">{{ idx + 1 }}</td>
                      <td>
                        <input type="text" v-model="obs.parameter" class="form-control table-input" placeholder="e.g. Temperature" />
                      </td>
                      <td>
                        <input type="text" v-model="obs.unit" class="form-control table-input" placeholder="e.g. °C" />
                      </td>
                      <td>
                        <input type="text" v-model="obs.expected_range" class="form-control table-input" placeholder="e.g. 20–25" />
                      </td>
                      <td>
                        <input type="text" v-model="obs.remarks" class="form-control table-input" placeholder="Short note…" />
                      </td>
                      <td>
                        <button class="delete-row-btn" title="Delete observation" @click="removeObservationRow(idx)">×</button>
                      </td>
                    </tr>
                    <tr v-if="experiment.observations.length === 0">
                      <td colspan="6" class="empty-table-cell">No Data</td>
                    </tr>
                    <tr class="add-row-tr">
                      <td colspan="6"><AddRow label="Add Observation" @add="addObservationRow" /></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="form-group stacked-field">
              <label class="form-label">Observation</label>
              <RichTextEditor v-model="experiment.observation" placeholder="Enter observations…" tables />
            </div>
          </div>
        </div>

        <!-- 2. MATERIAL REQUIRED TAB -->
        <div v-if="activeTab === 'materials'" class="tab-pane">
          <div class="pane-header-row">
            <h3 class="pane-subtitle">Required Formulation Ingredients</h3>
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
                          @blur="() => setTimeout(() => {
                            if (materialSearchStates[idx]) materialSearchStates[idx].showDropdown = false;
                            resolveMaterialSearch(mat, idx);
                          }, 200)"
                          class="form-control table-input search-input"
                          placeholder="Search item..."
                          style="position: relative; z-index: 100;"
                        />
                        <div v-if="materialSearchStates[idx]?.showDropdown" class="item-dropdown" style="position: absolute; top: 100%; left: 0; right: 0; margin-top: 2px;">
                          <div
                            v-for="item in availableMaterials.filter(m => !materialSearchStates[idx]?.search || m.name.toLowerCase().includes(materialSearchStates[idx].search.toLowerCase()) || m.item_name.toLowerCase().includes(materialSearchStates[idx].search.toLowerCase()))"
                            :key="item.name"
                            @mousedown="() => { selectMaterial(mat, idx, item); materialSearchStates[idx].showDropdown = false; }"
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
                  <td colspan="5" class="empty-table-cell">No materials required for this run yet.</td>
                </tr>
                <tr class="add-row-tr">
                  <td colspan="5"><AddRow label="Add Material" @add="addMaterial" /></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 3. EQUIPMENT DETAILS — the second half of the Material & Equipment
             tab. Same key as the materials pane above so the two render one
             under the other; the pane's own contents are unchanged. -->
        <div v-if="activeTab === 'materials'" class="tab-pane">
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
                <tr class="add-row-tr">
                  <td colspan="4"><AddRow label="Add Equipment" @add="addEquipment" /></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 4. METHODOLOGY — now the last section of the Details tab. Same key
             as the Details panes above so it stacks under them. usesTemplate is
             kept from when this was its own tab: Details shows at every level,
             and a Master Experiment has no use for a Methodology table. -->
        <div v-if="activeTab === 'details' && usesTemplate" class="tab-pane">
          <div class="pane-header-row">
            <h3 class="pane-subtitle">Experimental Methodology</h3>
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
                <tr class="add-row-tr">
                  <td colspan="3"><AddRow label="Add Method" @add="addMethod" /></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-if="activeTab === 'hierarchy'" class="tab-pane">
          <section class="meta-card">
            <h3 class="pane-subtitle">Experiment Hierarchy</h3>

            <div v-if="!experiment.experiment_category" class="hierarchy-empty">
              Pick an Experiment Category on the Template tab first — it decides what
              this run can sit under, and what it can adopt.
            </div>

            <!-- The run this one sits under is asked for on the Template tab,
                 beside the level that decides whether it needs one at all. What
                 is left here is the other direction: the runs this one adopts. -->
            <div v-if="needsParent" class="form-group stacked-field">
              <label class="form-label">Parent Experiment</label>
              <input
                type="text"
                :value="experiment.parent_experiment || 'Not linked yet'"
                class="form-control readonly"
                readonly
              />
              <span class="field-hint">
                Set on the Template tab — this run sits under {{ withArticle(parentCategory) }}.
              </span>
            </div>

            <div v-if="experiment.experiment_category" class="form-group stacked-field">
              <label class="form-label">
                Link {{ childCategory ? `${childCategory}s` : 'Child Experiments' }}
              </label>
              <span class="field-hint">{{ childPickerHint }}</span>

              <template v-if="canPickChildren">
                <div v-if="loadingChildren" class="hierarchy-status">
                  Looking for available experiments…
                </div>
                <div v-else-if="!childCandidates.length" class="hierarchy-empty">
                  No unlinked {{ childCategory }} exists for this project and Employee
                  Function yet. Create them first, then link them from this run's
                  Experiment Tree tab.
                </div>
                <template v-else>
                  <div class="hierarchy-picker-head">
                    <input
                      v-model="childFilter"
                      type="text"
                      class="form-control hierarchy-filter"
                      placeholder="Filter by ID, title or aim…"
                    />
                    <span class="hierarchy-pill">{{ selectedChildren.size }} selected</span>
                  </div>
                  <div v-if="!filteredChildCandidates.length" class="hierarchy-empty">
                    No available experiment matches “{{ childFilter }}”.
                  </div>
                  <ul v-else class="hierarchy-candidates">
                    <li
                      v-for="c in filteredChildCandidates"
                      :key="c.name"
                      class="hierarchy-candidate"
                      :class="{ picked: selectedChildren.has(c.name) }"
                      @click="toggleChild(c.name)"
                    >
                      <input
                        type="checkbox"
                        :checked="selectedChildren.has(c.name)"
                        @click.stop="toggleChild(c.name)"
                      />
                      <div class="hierarchy-candidate-text">
                        <span class="hierarchy-candidate-id font-mono">{{ c.name }}</span>
                        <span class="hierarchy-candidate-sub">
                          {{ c.title || c.aim || 'Untitled run' }}
                        </span>
                      </div>
                    </li>
                  </ul>
                </template>
              </template>
            </div>
          </section>
        </div>

        <!-- REPORT TAB -->
        <!-- Present at every level, as on the saved run, but there is nothing to
             roll up until the record exists: the report is this run plus its
             descendants, and neither exists yet. Saying so beats an empty card. -->
        <div v-if="activeTab === 'rawdata'" class="tab-pane">
          <RawDataTab :experiment="experiment" />
        </div>

        <!-- RESULT TAB -->
        <!-- Four fields off Lab Experiment's own result_tab, in the doctype's
             order. The three write-ups are descriptive prose and open empty; the
             editor's own toolbar is there for anyone who wants to lay a table
             out by hand, but nothing is pre-built. -->
        <div v-if="activeTab === 'result'" class="tab-pane">
          <section class="meta-card">
            <h3 class="pane-subtitle">Results</h3>
            <div class="form-group stacked-field">
              <RichTextEditor
                v-model="experiment.results"
                placeholder="Describe what the run produced…"
                min-height="200px"
                tables
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
              />
            </div>
          </section>

          <section class="meta-card">
            <div class="form-group">
              <label class="form-label">Result</label>
              <select v-model="experiment.result" class="form-control">
                <!-- Blank first, matching the doctype's Select, so an unjudged
                     run stays unjudged rather than defaulting to Pass. -->
                <option value="">Not decided yet</option>
                <option value="Pass">Pass</option>
                <option value="Fail">Fail</option>
              </select>
            </div>
          </section>
        </div>

        <div v-if="activeTab === 'report'" class="tab-pane">
          <section class="meta-card">
            <h3 class="pane-subtitle">Report</h3>
            <p class="rep-pending">
              The report rolls up this run and everything linked below it, so it is
              built once the run has been saved.
              <template v-if="createdId">
                <br />
                <router-link :to="`/experiments/${encodeURIComponent(createdId)}?tab=report`">
                  Open the report for {{ createdId }}
                </router-link>
              </template>
            </p>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>
