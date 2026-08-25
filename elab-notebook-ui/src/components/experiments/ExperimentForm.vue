<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { useUserStore } from '../../stores/user'
import { formatAuditDate } from '../../utils/dateFormatter'
import { readServerError } from '../../utils/serverError'
import RichTextEditor from '../common/RichTextEditor.vue'
import AddRow from '../common/AddRow.vue'
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
// Present only when the run was started from a team's Create Experiment button.
// Everything team-specific below keys off this, so the general New Experiment
// entry point is untouched.
const experimentTeam = ref(route.query.experiment_team || '')
const isTeamFlow = computed(() => Boolean(experimentTeam.value))

// Present only when the run was started from an existing run's Create button
// (ExperimentDetail.startChildRun): the level below that run, and that run as
// this one's parent. Both seed the hierarchy fields below and neither is
// locked - they pre-select the same pickers the general entry point offers.
const seedCategory = ref(route.query.experiment_category || '')
const seedParent = ref(route.query.parent_experiment || '')

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

// Who the server will file this run under once it is saved. Never posted - see
// the note on the experiment ref below.
const scientistName = computed(
  () => userStore.user.employee_name || userStore.user.full_name || '—'
)

// The signed-in account itself, shown beside the Employee it resolves to. Frappe
// stores it on the record as `owner` at insert; it is displayed here so the
// person filling the form can see which account the run will be filed under.
const currentUserId = computed(() => userStore.user.name || '—')

// The Employee behind that account - the id the run actually stores in
// employee_code. Shown, never posted: the server stamps it from the session and
// discards whatever the payload carried.
const currentEmployeeId = computed(() => userStore.user.employee || '—')

const experiment = ref({
  title: '',
  project: project.value,
  employee_function: employeeFunction.value,
  template: templateId.value,
  experiment_template: templateId.value,
  aim: '',
  sub_aim: '',
  // The level this run sits at. Mandatory on new runs (LabExperiment.validate_category)
  // and fixed once saved, so it is asked for here and nowhere else. It also
  // decides which of the fields below apply at all - see the hierarchy section.
  experiment_category: seedCategory.value,
  // The run one level up. Required at every level except the root, which takes
  // none (api/hierarchy.assert_parent_presence).
  parent_experiment: seedParent.value,
  rationale: '',
  remark: '',
  // Filled from the site's clock on mount (loadServerNow), not from the browser's:
  // the two are not the same machine, let alone the same timezone. Left blank
  // until then rather than seeded with a value that would have to be corrected -
  // and Lab Experiment.experiment_start_date defaults to Today server-side, so a
  // run posted before the lookup lands is still stamped by the server, not by
  // whatever the browser believed the date was.
  experiment_start_date: '',
  experiment_end_date: '',
  // employee_code / employee_name are deliberately absent: the server stamps the
  // author from the session (LabExperiment.set_creator_identity) and discards
  // whatever the payload carried, so sending a value here would only suggest the
  // client had a say in it. The name is shown below from the user store.
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
  observation: '',

  // The run's own step list and observation rows, same two tables the detail
  // page edits. Seeded here for the reason given below: the payload is this
  // object posted whole, so a table Vue never saw is a table the server never
  // receives. Not in TEMPLATE_CHILD_FIELDS - neither is ever cloned from a
  // template, so no row here can arrive flagged from_template.
  protocol_steps: [],
  observations: [],

  // Result tab. All three write-ups start empty: they are descriptive prose, and
  // an author who wants a table can build one in the editor. Seeded here anyway,
  // blank and all, for the reason given above - the payload is this object
  // posted whole, so a key Vue never saw is a key the server never receives.
  // `result` stays empty too: blank is the first option of the doctype's Select,
  // and a run nobody has judged yet should not post as Pass.
  results: '',
  observation_and_conclusion: '',
  conclusion: '',
  result: '',

  // Raw Data tab. Seeded here rather than left to appear on first keystroke:
  // the payload is this object posted whole, and a key Vue never saw is a key
  // the server never receives. Checks are 0/1 to match the doctype's Check.
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
  // Sub Experiment only, but seeded at every level for the reason above: the
  // payload is this object posted whole. An empty array on the other levels
  // costs nothing and is never shown.
  sub_metrics: [],
  sample: []
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

const applyTemplateClone = async (name) => {
  if (!name) return
  try {
    // The server owns the template -> run mapping (api/template.py
    // _clone_template_children). Mapping the tables here as well is what let the
    // two clone paths drift apart, and it is how imported rows ended up
    // unflagged. Every cloned row comes back with from_template = 1 already set.
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.template.get_template_clone', {
      params: { template_name: name }
    })
    const { header = {}, children = {} } = res.data.message || {}

    experiment.value.template = name
    experiment.value.experiment_template = name

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
  }
}

// Dropping the template has to drop what it cloned as well. Leaving the rows
// behind would post material, equipment and methodology - each still flagged
// from_template = 1, and so undeletable afterwards - onto a run whose level is
// not supposed to carry any of it.
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

// Item management actions
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
  // Imported rows are protected server-side too - see
  // LabExperiment.validate_imported_rows_kept().
  if (experiment.value.material_required[index]?.from_template) return
  experiment.value.material_required.splice(index, 1)
}

// No from_template guard on these two, unlike the tables above: they are never
// populated from a template, so every row is one the user added here and every
// row is theirs to delete.
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

const removeProtocolStep = (index) => {
  experiment.value.protocol_steps.splice(index, 1)
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
  // Imported rows are protected server-side too - see
  // LabExperiment.validate_imported_rows_kept().
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
  // Imported rows are protected server-side too - see
  // LabExperiment.validate_imported_rows_kept().
  if (experiment.value.methodology[index]?.from_template) return
  experiment.value.methodology.splice(index, 1)
}

const SAVE_FALLBACK = 'Error saving experiment. Please verify all required fields.'

// Level two is literally "Experiment", so the article cannot be baked into the
// message strings - "a Experiment" is what every one of them would say.
// Mirrors _a() in api/hierarchy.py, which does the same for the server's errors.
const withArticle = (category) =>
  `${'AEIOU'.includes((category || '').charAt(0).toUpperCase()) ? 'an' : 'a'} ${category}`

const capitalise = (text) => text.charAt(0).toUpperCase() + text.slice(1)

// "Project", "Project and Employee Function", "Project, Employee Function and
// Experiment Team" - a list a person would read out loud.
const listNames = (names) =>
  names.length <= 1
    ? names[0] || ''
    : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`

// Every mandatory field on this form, in the order the pane asks for them, each
// with the tab it lives on and the sentence to use when it is the only one
// missing. One field missing gets the sentence that says what to do about it;
// several get named together, because being sent back for one at a time is how a
// form feels like it is hiding the rules.
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
  // Named here rather than left to the server's rejection, but the server rule
  // is the control: api/hierarchy.assert_parent_presence runs on every write,
  // including a direct POST that never sees this form.
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
  // The run's ID is derived from its team, so this one is fatal rather than
  // cosmetic - and when the pair simply has no team, saying "select one" would
  // be pointing at an empty list.
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
  // A template may legitimately carry a blank Sub Aim while Lab Experiment
  // requires one, so the form asks for it rather than inventing a placeholder.
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

// Everything the server would reject with a bare "value missing", named here
// instead - including which Material Required row is at fault. A template may
// legitimately carry a blank Sub Aim while Lab Experiment requires one, so the
// form asks for it rather than inventing a placeholder.
const validateExperiment = () => {
  // The blur resolver runs on a 200ms delay so a dropdown pick lands first, and
  // clicking Save straight from the search box beats it. Settle every row here,
  // keeping what was typed so the message can quote it back.
  const rowsToCheck = experiment.value.material_required || []
  const typedPerRow = rowsToCheck.map(
    (_, idx) => (materialSearchStates.value[idx]?.search || '').trim()
  )
  rowsToCheck.forEach((row, idx) => resolveMaterialSearch(row, idx))

  // Every empty mandatory field, gathered before anything is reported, so the
  // message names all of them at once instead of sending the user round the form
  // one rejection at a time. The order is the order the pane asks for them.
  const missing = missingRequiredFields()
  if (missing.length) {
    activeTab.value = missing[0].tab
    return missing.length === 1
      ? missing[0].message
      : `${listNames(missing.map((f) => f.label))} are required.`
  }
  // Both are plain dates, so a string compare is the date compare.
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
  // The Experiment Team used to be checked here, ahead of everything else, which
  // meant a form with three fields empty only ever reported that one.
  // validateExperiment now gathers them all and names them together.
  const validationError = validateExperiment()
  if (validationError) {
    error.value = validationError
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
      createdId.value = newId

      // Children are linked in a second call: `parent_experiment` lives on the
      // child, so there is nothing to write until the parent has a name. The
      // link itself is all-or-nothing server-side, but it is a separate
      // transaction from the create - so a failure here leaves a real run with
      // no children, and saying so is the only honest option. Re-saving would
      // create a second run, which is why Save is closed off once createdId is set.
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

// The site's clock. `experiment_start_date` is a Date field on Lab Experiment,
// so what is stored is a day - the form used to show a time next to it that was
// both in the wrong timezone and discarded on save.
const serverToday = ref('')
const serverTimeZone = ref('')
// How far this browser is from the site. Kept rather than the timestamp itself
// so a row added twenty minutes into filling the form is stamped twenty minutes
// later, still on the site's clock.
const serverSkewMs = ref(0)

const loadServerNow = async () => {
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.user.get_server_now')
    const stamp = res.data.message || {}
    serverToday.value = stamp.today || ''
    serverTimeZone.value = stamp.time_zone || ''
    if (stamp.today) experiment.value.experiment_start_date = stamp.today
    if (stamp.now) {
      // Read as local so the difference is between wall clocks, not instants -
      // which is what makes the getters below print the site's time.
      serverSkewMs.value = new Date(stamp.now.replace(' ', 'T')).getTime() - Date.now()
    }
  } catch (err) {
    console.error('Failed to read the server clock:', err)
    // Left blank on purpose: the doctype's own `Today` default then fills it in
    // server-side, which is the same clock this call was asking for.
  }
}

// A native date field only opens its calendar from the small icon at its end,
// which is easy to miss and easy to mis-aim at - the field reads as a text box
// you are meant to type a date into. This opens the calendar from a click
// anywhere in the control. showPicker() needs a real user gesture and is not in
// every browser, so a failure here is not an error: the icon and typing both
// still work.
const openDatePicker = (event) => {
  const input = event.currentTarget
  if (!input || input.readOnly || input.disabled) return
  try {
    input.showPicker?.()
  } catch {
    /* Browser declined (unsupported, or not a trusted gesture) - leave the
       field as a plain date input. */
  }
}

// 'YYYY-MM-DD HH:mm:ss' on the site's clock - the shape Frappe stores, and the
// one formatAuditDate reads back without shifting it. `new Date().toISOString()`
// gave neither: UTC, and a trailing Z that moves the value again on display.
const labStamp = () => {
  const d = new Date(Date.now() + serverSkewMs.value)
  const pad = (n) => String(n).padStart(2, '0')
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  )
}

const loadProjectAndFunctionNames = async () => {
  // Cleared first: both are picked on this form now, so a name left over from
  // the previous pick would sit under the new one.
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

const selectMaterial = (mat, idx, item) => {
  mat.item_code = item.name
  mat.item_name = item.item_name || item.name
  mat.uom = item.uom || ''
  if (materialSearchStates.value[idx]) {
    materialSearchStates.value[idx].search = item.name
  }
}

// item_code is a Link to Item, so only a real Item id may be stored. Typing in
// the search box updates the search state alone - the code is set by picking a
// suggestion. Text typed but never picked used to survive on screen while
// item_code stayed empty, and the row only failed on save with the server's
// generic "value missing". Resolve or wipe it when the cell loses focus so the
// cell always shows what the row actually holds.
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
  // Only an unambiguous match may be applied on the user's behalf.
  return matches.length === 1 ? matches[0] : null
}

const resolveMaterialSearch = (mat, idx) => {
  const state = materialSearchStates.value[idx]
  if (!state) return
  const typed = (state.search || '').trim()
  // Already settled by picking a suggestion.
  if (typed && typed === mat.item_code) return

  const item = findMaterialItem(typed)
  if (item) {
    selectMaterial(mat, idx, item)
    return
  }
  // Nothing matched (or the text was cleared): leave the cell empty rather than
  // showing text with no item behind it.
  state.search = ''
  mat.item_code = ''
}

const selectEquipment = (eq, item) => {
  eq.equipment_id = item.name
  eq.equipment_name = item.item_name || item.name
}

// Segment and Cost Centre come off the team the run is filed under: a team is
// set up by picking a pair (ExperimentTeam.validate refuses one without), and a
// run booked anywhere other than where its own team books is a run filed under
// the wrong budget. The Employee Function supplies the list the picker offers -
// the function record carries the pairs its work is booked against, which is the
// same list Team Setup chose from - so the field is still answerable before any
// team exists, and two users on different functions never inherit each other's
// cost centre. Team first, function as the fallback.
const segmentOptions = ref([])
const costCenterOptions = ref([])
const financialsLoaded = ref(false)
const fetchedFromTeam = ref(false)

// The team picker settles after this runs (loadTeamsForProject pre-selects a
// lone team), so two loads can be in flight at once and the earlier one must not
// land last with the team-less answer.
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
      // The pair belonging to the team named in the picker. Passing it is what
      // makes this the run's own team rather than whichever team of this project
      // and function happens to be oldest.
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

  // The team's value wins outright, including when the function no longer maps
  // it - the team books where it books, and blanking the field would quietly
  // re-file the run. A value the list is missing is added to it so the picker
  // can show what is selected. With no team to read, a function offering exactly
  // one answer fills itself in and anything else is left for the user to pick.
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

// The run's ID is derived from its team (LabExperiment.set_series), so a run
// cannot be saved without one - at every Experiment Category, the root included.
// The picker is always shown and always editable, including on the team flow
// where the team's Create Experiment button passes one in the URL: that value
// pre-selects the field rather than replacing it, because the team a run is
// filed under is now something the user confirms rather than something decided
// off-screen. A project + function pair maps to many teams by design
// (api/experiment_team.save_team always creates a new record rather than reusing
// one), so there is a real choice to make here.
const teamOptions = ref([])
const teamsLoaded = ref(false)

// "No team exists for this pair" is only true once there is a pair to check.
// Project starts empty on the blank entry point, and an empty project is not a
// project with nothing set up for it - reporting it as one put a red error and a
// Team Setup link on a form the user had not filled in yet.
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

// Shown in the picker: team_name is the friendly label but is empty on teams
// created before it existed, so the id carries the row on its own.
const teamLabel = (t) => (t.team_name ? `${t.team_name} — ${t.name}` : t.name)

// The selected team's name, read back out of the options the picker was built
// from. Most teams predate the field, so "Not named" is the common answer and is
// said plainly rather than left as an empty box.
const teamNameDisplay = computed(() => {
  if (!experiment.value.experiment_team) return '—'
  const match = teamOptions.value.find((t) => t.name === experiment.value.experiment_team)
  if (!match) return teamsLoaded.value ? '—' : 'Loading…'
  return match.team_name || 'Not named'
})

const loadTeamsForProject = async () => {
  // Loaded on the team flow too: the URL team pre-selects the picker, it does
  // not stand in for it, so the alternatives still have to be on hand.
  // Re-run whenever the project or Employee Function changes, so the previous
  // pair's teams are cleared rather than left on offer.
  teamOptions.value = []
  teamsLoaded.value = false
  if (!project.value) {
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
    // Pre-select the only candidate, but leave the field open: the user is meant
    // to see which team the run lands on, not have it decided silently.
    if (!experiment.value.experiment_team && teamOptions.value.length === 1) {
      experiment.value.experiment_team = teamOptions.value[0].name
    }
  } catch (err) {
    console.error('Failed to look up Experiment Team', err)
  } finally {
    teamsLoaded.value = true
  }
}

// Which team the run is filed under is what decides where it books, so the
// financials are re-read whenever that answer changes - including the
// pre-selection above, which lands after the first read. Without this the run
// keeps the pair of whichever team was resolved first while naming another.
watch(() => experiment.value.experiment_team, loadFinancials)

// ---------------------------------------------------------------------------
// Getting a team when the project has none
// ---------------------------------------------------------------------------
// This form used to carry its own team-creation panel - name field, roster
// checkboxes, its own save_team call - which meant the same feature existed
// twice, here and in Team Setup, and had to be fixed twice. It is gone. The link
// below carries the project and function this form already resolved, plus
// create=1, and Team Setup opens its own dialog seeded with them.
//
// Deliberate consequence: leaving this form loses what has been typed into it.
// That is why the inline panel existed. Team Setup is one page and one save, and
// the run is started again from a project that now has a team.
const teamSetupUrl = computed(() => ({
  path: '/elab-notebook',
  query: {
    create: 1,
    ...(project.value ? { project: project.value } : {}),
    ...(employeeFunction.value ? { employee_function: employeeFunction.value } : {}),
  },
}))

// ---------------------------------------------------------------------------
// Project and Employee Function
// ---------------------------------------------------------------------------
// Both used to be settled before this form opened - they arrived in the URL or
// not at all, and a run started without them could never be saved because the
// Experiment Team picker had nothing to resolve. They are fields of this form
// now, filled here like any other. A value arriving in the URL (the team flow,
// or a Master's Create Experiment button) still pre-fills them and still wins
// over anything resolved below.

// Projects the user may actually start a run for - a team must exist and the
// user must be on it or head its function. Narrower than the function -> project
// mapping on purpose: a project with no team is a dead end here.
const authorizedProjects = ref([])
const projectsLoaded = ref(false)

// Scoped to the chosen Employee Function once there is one. The narrowing is the
// server's, not a filter applied to a list it already sent: a head is authorised
// for projects that carry no team yet, and those exist only in the function ->
// project mapping, so they cannot be recovered from an unfiltered response.
//
// Before a function is picked this asks for all of them, which is what keeps the
// no-function fallback reachable: a user whose employee record maps to no
// function picks a project first and takes the function from that project's
// teams (loadProjectFunctions). Filtering on an empty function would empty the
// picker they need to get out of that state.
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
    // Two different dead ends, and they need different things done about them:
    // the function may be the wrong one for this run, or the user may have no
    // route into any project at all.
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

// The signed-in user's own active Employee Functions, from the resolver the
// Experiment Template form already uses (api/employee_function
// .get_current_employee_function, which reads Employee.custom_function_code).
// One resolver, one definition of "your function".
const myFunctions = ref([])
const functionsLoaded = ref(false)

// Only consulted when the resolver comes back empty - see the hint below. These
// are the functions the *project* offers the user, which is what the create
// modal used to ask for, so an employee record with no function mapping is not
// left unable to start a run.
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

  // Pre-select only an unambiguous answer, and never over an explicit one: a
  // function passed in the URL is what the flow that opened this form decided,
  // and it stays. Pre-selected, not locked - the picker below stays open, the
  // same rule the Experiment Team picker follows.
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

// The project list itself is scoped by the function, so it is reloaded when the
// function changes - and only then. Kept out of the pair watcher below because
// that one also fires on `project`, and reloading the list a project was just
// chosen from would be a round trip that can only return what is already there.
//
// A project chosen under the previous function is dropped if the new one does
// not offer it, for the same reason that watcher drops the team and template:
// carrying it over leaves a value the picker no longer lists but the payload
// still posts. Cleared after the reload, so the decision is made against the new
// list rather than the old one.
watch(employeeFunction, async () => {
  await loadAuthorizedProjects()
  if (project.value && !authorizedProjects.value.some((p) => p.name === project.value)) {
    project.value = ''
  }
})

// Everything scoped by the pair has to be resolved again when either half of it
// changes: the teams the run can be filed under, the financials copied from that
// team, the templates in scope, and the runs it can sit under or adopt. Whatever
// was picked for the previous pair is dropped first rather than carried over -
// a team, template or parent from another project is not a choice, it is a stale
// value that would post silently.
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

// ---------------------------------------------------------------------------
// Category hierarchy
// ---------------------------------------------------------------------------
// The level a run sits at, and the runs one level below it that this one adopts
// on creation. The level ordering is not retyped here: get_category_options
// ships it from elab_notebook.api.hierarchy, which is the same tuple the
// server validates against.

const HIERARCHY_API = 'elab_notebook.elab_notebook.api.hierarchy'

const categoryOptions = ref([])
const childCandidates = ref([])
const selectedChildren = ref(new Set())
const childFilter = ref('')
const loadingChildren = ref(false)

const parentCandidates = ref([])
const loadingParents = ref(false)
const parentsLoaded = ref(false)

// Set once the run exists. Save is blocked afterwards so a failed link step
// cannot be retried into a second run.
const createdId = ref('')

const currentCategoryOption = computed(
  () =>
    categoryOptions.value.find((o) => o.category === experiment.value.experiment_category) || null
)

const childCategory = computed(() => currentCategoryOption.value?.child_category || '')

// The level directly above the chosen one, read back out of the same shipped
// ordering rather than retyped: the option whose child_category is this one.
const parentCategory = computed(() => {
  const current = currentCategoryOption.value
  if (!current) return ''
  return categoryOptions.value.find((o) => o.child_category === current.category)?.category || ''
})

// Which of the four levels this is, expressed as what the level *does* rather
// than by name. Both fall out of the ordering get_category_options ships, so the
// form never hard-codes "Master Experiment" or "Sub Sub Experiment" - renaming a
// level server-side does not leave a stale string here.
const needsParent = computed(() => Boolean(parentCategory.value))
const usesTemplate = computed(() => Boolean(currentCategoryOption.value?.is_leaf))

// Tabs that only exist for a run that can carry template-cloned content -
// Protocol Steps among them, since experiment_protocol_steps is cloned from a
// template like the other three and a level that takes no template can never
// have any. Hidden rather than disabled at the other levels: an empty tab that
// can never hold anything reads as a bug.
const TEMPLATE_TABS = ['materials', 'equipment', 'methodology', 'procedure']

// Four tabs at every level, plus the template-only ones at the leaf. Observation
// is not a tab of its own any more - it is part of the run's write-up and sits
// with Aim, Sub Aim and Rationale under Details.
const visibleTabs = computed(() => [
  { key: 'general', label: 'Template' },
  { key: 'details', label: 'Details' },
  // Third at every level that has it, which is why it sits above the
  // template-only block rather than after it: at the leaf those four tabs
  // appear and would otherwise push Raw Data down to seventh.
  // Hidden on a Master Experiment - see utils/rawData.js, which mirrors the
  // doctype's own depends_on rather than restating the rule.
  ...(showsRawDataTab(experiment.value.experiment_category)
    ? [{ key: 'rawdata', label: 'Raw Data' }]
    : []),
  // After Raw Data, not before it as on the desk form. The desk runs
  // Procedure -> Result -> Raw Data, but this app has no Procedure tab at all
  // and deliberately holds Raw Data third at every level (above). Slotting
  // Result in ahead of it would push Raw Data to fourth and break that; the
  // doctype puts no depends_on on result_tab, so unlike Raw Data this one shows
  // at every level including Master Experiment.
  { key: 'result', label: 'Result' },
  ...(usesTemplate.value
    ? [
        // One tab, two stacked sections: Material Required above, Equipment
        // Details below. Keyed 'materials', which is also what TEMPLATE_TABS
        // resets from, so nothing else had to change.
        { key: 'materials', label: 'Material & Equipment' },
        // Methodology moved under Details; Protocol Steps is gone outright.
        // Both tables stay on the server, untouched.
      ]
    : []),
  { key: 'hierarchy', label: 'Experiment Hierarchy' },
  { key: 'report', label: 'Report' },
])

// Both scope values are required to resolve candidates, and a blank
// employee_function is deliberately not matched against other blanks - see
// get_available_children. Runs predating the hierarchy have no function set, and
// blank-matching would pull unrelated orphans into a tree.
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
  // Reassigning is what Vue tracks; mutating the Set in place does not re-render.
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
  // Names the half that is actually missing: the Employee Function fills itself
  // in from the signed-in user, so "no Project and Employee Function" was
  // reporting a blank field that was not blank.
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
    // A parent picked for the previous level is not a parent for this one.
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

// Templates for the leaf level only, scoped the same way the create modal scopes
// them: a template with no project is shared, one with a project must match.
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

// Re-cloning on every keystroke of a picker is not possible - the pick itself is
// the event - but switching templates has to drop the previous one's rows first,
// or the two sets would be merged into one run.
const onTemplatePicked = async (name) => {
  clearTemplateSelection()
  if (name) await applyTemplateClone(name)
}

// Changing the level changes everything the form asks for: which runs are
// adoptable, which run can be its parent, and whether it carries a template at
// all. Rebuilding rather than carrying selections across levels is what keeps a
// Master from being posted with a Sub Sub's material rows still attached.
watch(() => experiment.value.experiment_category, () => {
  loadChildCandidates()
  loadParentCandidates()

  // Guarded on the options being in hand: before they load, every level would
  // look like "no template, no parent" and wipe a template arriving by URL.
  if (!categoryOptions.value.length) return

  if (!needsParent.value) experiment.value.parent_experiment = ''
  if (!usesTemplate.value) clearTemplateSelection()
  if (!usesTemplate.value && TEMPLATE_TABS.includes(activeTab.value)) activeTab.value = 'general'
  // Same for Raw Data: a Master Experiment has no such tab, so the pane must
  // not stay open underneath a tab row that no longer lists it.
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
  // Resolves the signed-in user's function, and pre-selects it when there is
  // exactly one. Awaited so the fallback below knows whether it is needed.
  await loadMyFunctions()
  loadProjectFunctions()
  await loadCategoryOptions()

  // A category that arrived in the URL was set before this component mounted,
  // so the watcher above - which is what normally fills the parent and child
  // pickers - never fires for it. Prime them here instead, once the ordering
  // those pickers read is in hand. The parent seeded from the URL survives only
  // if it is a real candidate: loadParentCandidates drops anything the server
  // does not offer for this level and scope.
  if (experiment.value.experiment_category) {
    loadParentCandidates()
    loadChildCandidates()
  }

  // A template in the URL belongs to the one level that can carry one, so it is
  // dropped here rather than cloned first: a run started at a level with no
  // Material Required, Equipment Details or Methodology tab would otherwise be
  // posted with those rows attached, each flagged from_template = 1 and so
  // undeletable afterwards. The watcher above does the same on a level *change*;
  // it never fires for a level that arrived already set.
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
                      <td>
                        <input type="number" v-model="step.step_no" class="form-control table-input" min="0" />
                      </td>
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
                      <!-- Path, not an upload widget: this SPA has no uploader
                           anywhere, and the Raw Data tab enters its attachments
                           the same way. -->
                      <td>
                        <input
                          type="text"
                          v-model="step.attachment"
                          class="form-control table-input"
                          placeholder="/files/…"
                        />
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
              <RichTextEditor v-model="experiment.observation" placeholder="Enter observations…" />
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
              />
            </div>
          </section>

          <section class="meta-card">
            <h3 class="pane-subtitle">Observation</h3>
            <div class="form-group stacked-field">
              <RichTextEditor
                v-model="experiment.observation_and_conclusion"
                placeholder="Describe what was observed…"
              />
            </div>
          </section>

          <section class="meta-card">
            <h3 class="pane-subtitle">Conclusion</h3>
            <div class="form-group stacked-field">
              <RichTextEditor
                v-model="experiment.conclusion"
                placeholder="What the run concludes…"
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
