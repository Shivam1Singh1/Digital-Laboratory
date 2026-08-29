<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { useUserStore } from '../../stores/user'
import { extractFrappeError } from '../../utils/frappeError'
import PageHeader from '../layout/PageHeader.vue'
import './TeamSetup.css'
// === DYNAMIC-PERMS-START ===
// import { usePermissionStore } from '../../stores/permissions'
// === DYNAMIC-PERMS-END ===

const userStore = useUserStore()
const route = useRoute()
const API = 'elab_notebook.elab_notebook.api.experiment_team'
// === DYNAMIC-PERMS-START ===
// const permStore = usePermissionStore()
//
// // OR, never AND. Frappe's doctype-level create on Experiment Team belongs to
// // System Manager alone, while the page's real gate is "do you head this
// // Employee Function" - and _assert_head lets a System Manager through by
// // bypass. ANDing the two would hide Create Team from every head who is not a
// // System Manager, which is all of them here (verified: has_permission says
// // create=0 for the head, who can nonetheless create a team). ORing adds the
// // case the domain check misses - a System Manager who heads nothing but may
// // still create by bypass - and takes nothing away.
// const canCreateTeam = computed(
//   () => isHead.value || permStore.can('Experiment Team', 'create')
// )
// === DYNAMIC-PERMS-END ===

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const notice = ref('')

// Only Employee Function heads can create teams; participants only get the list.
const isHead = ref(false)
const functions = ref([])
const myTeams = ref([])

// --- dialog state
const showDialog = ref(false)
const teamName = ref('')
const employeeFunction = ref('')
const project = ref('')
const selected = ref(new Set())
const search = ref('')

const segment = ref('')
const costCenter = ref('')
const segments = ref([])
const costCenters = ref([])

const loadSegmentsAndCostCenters = async () => {
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.experiment_team.get_segments_and_cost_centers', {
      params: { employee_function: employeeFunction.value || undefined }
    })
    segments.value = res.data.message.segments || []
    costCenters.value = res.data.message.cost_centers || []
  } catch (err) {
    console.error('Failed to load segments/cost centers', err)
  }
}

const currentFunction = computed(
  () => functions.value.find((f) => f.name === employeeFunction.value) || null
)

const headName = computed(() => currentFunction.value?.function_head_name || '')
const projects = computed(() => currentFunction.value?.projects || [])
const members = computed(() => currentFunction.value?.members || [])

const filteredMembers = computed(() => {
  const term = search.value.trim().toLowerCase()
  if (!term) return members.value
  return members.value.filter(
    (m) =>
      m.user.toLowerCase().includes(term) ||
      String(m.full_name || '').toLowerCase().includes(term)
  )
})

const canSave = computed(() => {
  return (
    !!teamName.value &&
    !!project.value &&
    !!segment.value &&
    !!costCenter.value &&
    selected.value.size > 0 &&
    !saving.value
  )
})

const call = async (method, params = {}) => {
  const res = await axios.get(`/api/method/${API}.${method}`, { params })
  return res.data.message
}

// ------------------------------------------------------------------ loading

const loadContext = async () => {
  loading.value = true
  error.value = ''
  try {
    const ctx = await call('get_create_context')
    isHead.value = !!ctx.is_head
    functions.value = ctx.functions || []
    if (functions.value.length) employeeFunction.value = functions.value[0].name
    await loadMyTeams()
  } catch (err) {
    console.error('Failed to load context', err)
    error.value = extractFrappeError(err)
  } finally {
    loading.value = false
  }
}

// Two separate numbers per team. They used to be one: the badge printed the
// experiment count twice, once labelled Samples, so a team with no samples at
// all still read "6 Samples".
const teamExperimentCounts = ref({})
const teamSampleCounts = ref({})

const fetchTeamExperimentCounts = async () => {
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.dashboard.get_team_experiment_counts')
    const counts = res.data.message || []
    const expMap = {}
    const sampleMap = {}
    for (const item of counts) {
      expMap[item.team] = item.count
      sampleMap[item.team] = item.sample_count
    }
    teamExperimentCounts.value = expMap
    teamSampleCounts.value = sampleMap
  } catch (err) {
    console.error('Failed to fetch team experiment counts', err)
  }
}

const loadMyTeams = async () => {
  try {
    const teams = await call('get_my_teams')
    myTeams.value = teams || []
    console.log('Teams loaded:', myTeams.value.length)
    await fetchTeamExperimentCounts()
  } catch (err) {
    console.error('Failed to load teams', err)
    error.value = extractFrappeError(err)
  }
}

const filteredMyTeams = computed(() => {
  const proj = userStore.currentProject
  if (!proj || proj === 'all') return myTeams.value
  return myTeams.value.filter((t) => t.project === proj)
})

const currentPage = ref(1)
const pageSize = 7

const totalPages = computed(() => Math.ceil(filteredMyTeams.value.length / pageSize))

const paginatedMyTeams = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  const end = start + pageSize
  return filteredMyTeams.value.slice(start, end)
})

watch(() => userStore.currentProject, () => {
  currentPage.value = 1
})

// A team is identified by its ID, since the same function/project/member set
// can legitimately exist many times over.
const memberPreview = (t) => {
  const names = t.participant_names || []
  if (!names.length) return 'no participants'
  if (names.length <= 2) return names.join(', ')
  return `${names.slice(0, 2).join(', ')} +${names.length - 2}`
}

// ------------------------------------------------------------------- dialog

const openDialog = () => {
  teamName.value = ''
  project.value = ''
  selected.value = new Set()
  search.value = ''
  notice.value = ''
  error.value = ''
  segment.value = ''
  costCenter.value = ''
  showDialog.value = true
}

const closeDialog = () => {
  showDialog.value = false
}

const toggle = (user) => {
  // Sets are not deeply reactive in Vue 3, so replace it to trigger updates.
  const next = new Set(selected.value)
  next.has(user) ? next.delete(user) : next.add(user)
  selected.value = next
}

const save = async () => {
  error.value = ''

  // Client-side validation
  if (!teamName.value.trim()) {
    error.value = 'Team Name is required.'
    return
  }
  if (selected.value.size === 0) {
    error.value = 'At least one team member must be selected.'
    return
  }

  saving.value = true
  try {
    const participants = Array.from(selected.value).map((user) => ({ user }))
    const res = await axios.post(`/api/method/${API}.save_team`, {
      employee_function: employeeFunction.value,
      project: project.value,
      team_name: teamName.value,
      participants: participants,
      segment: segment.value,
      cost_center: costCenter.value
    })
    const msg = res.data.message || {}
    notice.value = `Created "${msg.team_name}" (${msg.name}) - ${msg.count} participant${msg.count === 1 ? '' : 's'} on ${msg.project}.`
    showDialog.value = false
    // Reset pagination to show the newly created team
    currentPage.value = 1
    await Promise.all([loadMyTeams(), loadCounts()])
    // Clear notice after 5 seconds so it doesn't obscure the new team
    setTimeout(() => {
      notice.value = ''
    }, 5000)
  } catch (err) {
    console.error('Failed to create team', err)
    error.value = extractFrappeError(err)
  } finally {
    saving.value = false
  }
}

// Refresh the per-project team counts shown in the dialog dropdown.
const loadCounts = async () => {
  if (!employeeFunction.value) return
  try {
    const fresh = await call('get_function_projects', {
      employee_function: employeeFunction.value
    })
    const f = functions.value.find((x) => x.name === employeeFunction.value)
    if (f) f.projects = fresh
  } catch (err) {
    console.error('Failed to refresh project counts', err)
  }
}

watch(employeeFunction, () => {
  project.value = ''
  selected.value = new Set()
  loadSegmentsAndCostCenters()
})

// Arriving from the Experiment form's "Set up a team for this project" link,
// which sends create=1 plus the pair it had already resolved. Seeding them here
// is what lets that form drop its own copy of this dialog: the user lands on the
// same one, already filled in, instead of retyping what the other page knew.
//
// employeeFunction is set first and the project a tick later: the watcher above
// clears the project whenever the function changes, so setting both at once
// would wipe the one that arrived in the URL.
const applyCreateIntent = async () => {
  if (!route.query.create) return

  const fn = route.query.employee_function
  if (fn && functions.value.some((f) => f.name === fn)) {
    employeeFunction.value = fn
    await nextTick()
    await loadSegmentsAndCostCenters()
  }

  openDialog()
  if (route.query.project) {
    await nextTick()
    project.value = route.query.project
  }
}

onMounted(async () => {
  // === DYNAMIC-PERMS-START ===
  // // Doctype-level: no record exists yet on a list page. Fetched alongside the
  // // context rather than after it so the create affordance settles in one paint.
  // await Promise.all([loadContext(), permStore.fetchAndCache('Experiment Team')])
  // === DYNAMIC-PERMS-END ===
  await loadContext()
  await loadSegmentsAndCostCenters()
  await applyCreateIntent()
})
</script>

<template>
  <div class="team-setup-container">
    <!-- === DYNAMIC-PERMS-START ===
    <PageHeader
      :breadcrumbs="[{ label: 'Home', href: '/' }, { label: 'Elab Notebook' }]"
      title="Elab Notebook"
      subtitle="Decide, project by project, who may create experiments."
      :action="canCreateTeam ? { label: 'Create Team', onClick: openDialog } : null"
    />
    === DYNAMIC-PERMS-END === -->
    <PageHeader
      :breadcrumbs="[{ label: 'Home', href: '/' }, { label: 'Elab Notebook' }]"
      title="Elab Notebook"
      subtitle="Decide, project by project, who may create experiments."
      :action="isHead ? { label: 'Create Team', onClick: openDialog } : null"
    />

    <div v-if="error && !showDialog" class="form-error-banner">
      <strong>Something went wrong</strong>
      <span class="form-error-text">{{ error }}</span>
      <button class="form-error-close" @click="error = ''">×</button>
    </div>

    <p v-if="notice" class="save-notice standalone">{{ notice }}</p>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading...</p>
    </div>

    <!-- Neither a head nor a participant anywhere -->
    <!-- === DYNAMIC-PERMS-START ===
    <div v-else-if="!canCreateTeam && !filteredMyTeams.length" class="empty-state">
    === DYNAMIC-PERMS-END === -->
    <div v-else-if="!isHead && !filteredMyTeams.length" class="empty-state">
      <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <rect x="3" y="11" width="18" height="11" rx="2" />
        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
      </svg>
      <h3>Head access only</h3>
      <p>
        This page is for Employee Function heads and their team members. You head no
        Employee Function and are not on any team.
      </p>
    </div>

    <div v-else class="team-layout">
      <!-- YOUR TEAMS -->
      <section class="meta-card">
        <div class="table-actions">
          <div>
            <h3 class="section-title no-margin">Your Teams</h3>
            <!-- === DYNAMIC-PERMS-START ===
            <p class="section-sub">
              {{ canCreateTeam ? 'Teams you have set up, plus any you take part in.' : 'Teams you take part in.' }}
            </p>
            === DYNAMIC-PERMS-END === -->
            <p class="section-sub">
              {{ isHead ? 'Teams you have set up, plus any you take part in.' : 'Teams you take part in.' }}
            </p>
          </div>
          <span v-if="filteredMyTeams.length" class="selected-pill">{{ filteredMyTeams.length }} total</span>
        </div>

        <div v-if="!filteredMyTeams.length" class="grid-empty standalone">
          <div class="empty-state-content">
            <p class="empty-state-text">No teams yet</p>
            <!-- === DYNAMIC-PERMS-START ===
            <button v-if="canCreateTeam" class="btn btn-primary btn-lg" @click="openDialog">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="btn-icon-svg"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              Create Team
            </button>
            === DYNAMIC-PERMS-END === -->
            <button v-if="isHead" class="btn btn-primary btn-lg" @click="openDialog">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="btn-icon-svg"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              Create Team
            </button>
            <p v-else class="empty-state-subtext">You are not a team lead yet. Team leads can create teams.</p>
          </div>
        </div>

        <div v-else class="table-container">
          <table class="teams-table">
            <thead>
              <tr>
                <th>TEAM ID</th>
                <th>TEAM NAME</th>
                <th>PROJECT</th>
                <th>PARTICIPANTS</th>
                <th>EXPERIMENTS</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in paginatedMyTeams" :key="t.name" @click="$router.push(`/elab-notebook/${encodeURIComponent(t.name)}`)" class="team-table-row">
                <td class="font-mono text-accent"><strong>{{ t.name }}</strong></td>
                <td>
                  {{ t.team_name }}
                  <span class="role-tag" :class="t.role">{{ t.role }}</span>
                  <!-- Only ever appears on a head's row: get_my_teams drops an
                       archived team from a participant's list entirely, so
                       nobody else has one to mark. Same tag convention as the
                       role beside it. -->
                  <span v-if="t.is_archived" class="role-tag archived">archived</span>
                </td>
                <td>{{ t.project_id || t.project }}</td>
                <td class="count-col">
                  <span class="count-badge">{{ t.participant_count }} {{ t.participant_count === 1 ? 'participant' : 'participants' }}</span>
                </td>
                <td class="count-col">
                  <span class="count-badge">{{ teamExperimentCounts[t.name] || 0 }} Exp. / {{ teamSampleCounts[t.name] || 0 }} Samples</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination Controls -->
        <div v-if="totalPages > 1" class="pagination-controls" style="display: flex; align-items: center; justify-content: center; gap: 1rem; margin-top: 1.5rem; padding-bottom: 0.5rem;">
          <button 
            class="btn btn-secondary btn-sm" 
            :disabled="currentPage === 1" 
            @click="currentPage--"
          >
            Previous
          </button>
          <span class="pagination-info" style="font-size: var(--fs-lg); color: var(--text-muted); font-weight: var(--fw-medium);">
            Page {{ currentPage }} of {{ totalPages }}
          </span>
          <button 
            class="btn btn-secondary btn-sm" 
            :disabled="currentPage === totalPages" 
            @click="currentPage++"
          >
            Next
          </button>
        </div>
      </section>
    </div>

    <!-- CREATE TEAM DIALOG -->
    <div v-if="showDialog" class="modal-overlay" @click.self="closeDialog">
      <div class="modal-card wide">
        <div class="modal-header">
          <h3>Create Team</h3>
          <button class="modal-close-btn" @click="closeDialog">×</button>
        </div>

        <div class="modal-body">
          <div v-if="error" class="form-error-banner">
            <strong>Could not create</strong>
            <span class="form-error-text">{{ error }}</span>
            <button class="form-error-close" @click="error = ''">×</button>
          </div>

          <div class="form-group">
            <label class="form-label">Team Name *</label>
            <input
              v-model="teamName"
              type="text"
              class="form-control"
              placeholder="e.g. R&D Team Alpha"
            />
          </div>

          <div class="form-row">
            <div class="form-group col">
              <label class="form-label">Employee Function</label>
              <select v-if="functions.length > 1" v-model="employeeFunction" class="form-control">
                <option v-for="f in functions" :key="f.name" :value="f.name">
                  {{ f.name }} - {{ f.function_name }}
                </option>
              </select>
              <input v-else type="text" :value="employeeFunction" class="form-control readonly" readonly />
            </div>

            <div class="form-group col">
              <label class="form-label">Head Name</label>
              <input type="text" :value="headName" class="form-control readonly" readonly />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Project *</label>
            <select v-model="project" class="form-control">
              <option value="">Select a project...</option>
              <option v-for="p in projects" :key="p.name" :value="p.name">
                {{ p.name }} - {{ p.project_name }}{{ p.team_count ? `  (${p.team_count} team${p.team_count === 1 ? '' : 's'})` : '' }}
              </option>
            </select>
          </div>

          <div class="form-row">
            <div class="form-group col">
              <label class="form-label">Segment *</label>
              <select v-model="segment" class="form-control form-select attractive-select">
                <option value="">Select Segment...</option>
                <option v-for="seg in segments" :key="seg" :value="seg">{{ seg }}</option>
              </select>
            </div>

            <div class="form-group col">
              <label class="form-label">Cost Centre *</label>
              <select v-model="costCenter" class="form-control form-select attractive-select">
                <option value="">Select Cost Centre...</option>
                <option v-for="cc in costCenters" :key="cc" :value="cc">{{ cc }}</option>
              </select>
            </div>
          </div>


          <div class="form-group">
            <label class="form-label">Team Members</label>
            <input
              v-model="search"
              type="text"
              class="member-search"
              placeholder="Filter by name or email..."
            />
            <div v-if="!members.length" class="grid-empty standalone">
              No active employees are mapped to this Employee Function.
            </div>
            <ul v-else class="candidate-list dialog-list">
              <li
                v-for="m in filteredMembers"
                :key="m.user"
                class="candidate"
                :class="{ picked: selected.has(m.user) }"
                @click="toggle(m.user)"
              >
                <input type="checkbox" :checked="selected.has(m.user)" @click.stop="toggle(m.user)" />
                <div class="candidate-text">
                  <span class="candidate-name">{{ m.full_name || m.user }}</span>
                  <span class="candidate-user">{{ m.user }}</span>
                </div>
              </li>
              <li v-if="!filteredMembers.length" class="candidate muted">
                No one matches "{{ search }}".
              </li>
            </ul>
          </div>
        </div>

        <div class="modal-footer">
          <span class="selected-pill">{{ selected.size }} selected</span>
          <button class="btn btn-secondary" @click="closeDialog">Cancel</button>
          <button class="btn btn-primary" @click="save" :disabled="!canSave">
            <span v-if="saving" class="spinner btn-spinner"></span>
            {{ saving ? 'Creating...' : 'Save' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
