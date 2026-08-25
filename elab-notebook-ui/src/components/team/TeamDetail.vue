<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { useUserStore } from '../../stores/user'
import { extractFrappeError } from '../../utils/frappeError'
import './TeamSetup.css'
// === DYNAMIC-PERMS-START ===
// import { usePermissionStore } from '../../stores/permissions'
// === DYNAMIC-PERMS-END ===

const API = 'elab_notebook.elab_notebook.api.experiment_team'
const route = useRoute()
const userStore = useUserStore()
// === DYNAMIC-PERMS-START ===
// const permStore = usePermissionStore()
//
// // Record-level, so Frappe does run has_team_permission here - but verified
// // that the hook can only restrict, never grant, so the owner of this very team
// // still reads write=0 from the role table. ORed with the server's own can_edit
// // for that reason: the dict may add access, it must never subtract it.
// const canEditTeam = computed(
//   () =>
//     Boolean(team.value?.can_edit) ||
//     permStore.can('Experiment Team', 'write', route.params.id)
// )
// === DYNAMIC-PERMS-END ===

const loading = ref(true)
const saving = ref(false)
const editing = ref(false)
const error = ref('')
const notice = ref('')

const team = ref(null)
const segments = ref([])
const costCenters = ref([])

const loadSegmentsAndCostCenters = async () => {
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.experiment_team.get_segments_and_cost_centers', {
      params: { employee_function: team.value?.employee_function || undefined }
    })
    segments.value = res.data.message.segments || []
    costCenters.value = res.data.message.cost_centers || []
  } catch (err) {
    console.error('Failed to load segments/cost centers', err)
  }
}
const selected = ref(new Set())
const search = ref('')

const candidates = computed(() => team.value?.candidates || [])

const filteredCandidates = computed(() => {
  const term = search.value.trim().toLowerCase()
  if (!term) return candidates.value
  return candidates.value.filter(
    (c) =>
      c.user.toLowerCase().includes(term) ||
      String(c.full_name || '').toLowerCase().includes(term)
  )
})

const participants = computed(() => team.value?.participants || [])

const canCreate = computed(() => !!team.value?.can_create_experiment)

const createReason = computed(() => {
  if (!team.value) return ''
  if (canCreate.value) return ''
  return 'You are not on this team, so you cannot create experiments for this project. Add yourself to the participants list, or ask the function head to.'
})

// createExperimentUrl was removed here. It was unreferenced - the Create
// Experiment button above calls userStore.openCreateExperimentModal - and it
// pointed at /app/experiment/new, the legacy Stock-module `Experiment` desk
// form. That is a different doctype from the `Lab Experiment` this app creates,
// so wiring it back up would have silently produced records in the wrong table.

const initials = (row) =>
  String(row.full_name || row.user || '')
    .split(/[\s.@]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join('')

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await axios.get(`/api/method/${API}.get_team_detail`, {
      params: { team_name: route.params.id }
    })
    team.value = res.data.message
    selected.value = new Set((team.value.participants || []).map((p) => p.user))
    await fetchExperimentCount()
  } catch (err) {
    console.error('Failed to load team', err)
    error.value = extractFrappeError(err)
    team.value = null
  } finally {
    loading.value = false
  }
}

const experimentCount = ref(0)
const fetchExperimentCount = async () => {
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.dashboard.get_team_experiment_counts')
    const counts = res.data.message || []
    const match = counts.find((c) => c.team === route.params.id)
    experimentCount.value = match ? match.count : 0
  } catch (err) {
    console.error('Failed to fetch experiment count', err)
  }
}

const startEdit = () => {
  selected.value = new Set(participants.value.map((p) => p.user))
  search.value = ''
  notice.value = ''
  editing.value = true
}

const cancelEdit = () => {
  selected.value = new Set(participants.value.map((p) => p.user))
  editing.value = false
}

const toggle = (user) => {
  // Sets are not deeply reactive in Vue 3, so replace it to trigger updates.
  const next = new Set(selected.value)
  next.has(user) ? next.delete(user) : next.add(user)
  selected.value = next
}

const save = async () => {
  error.value = ''
  notice.value = ''
  saving.value = true
  try {
    // Use update_team for editing existing team (roster, team_name, segment, cost_center)
    const res = await axios.post(`/api/method/${API}.update_team`, {
      team_id: team.value.name,
      team_name: team.value.team_name,
      participants: Array.from(selected.value).map((user) => ({ user })),
      segment: team.value.segment,
      cost_center: team.value.cost_center
    })
    const msg = res.data.message || {}
    notice.value = `Saved — "${msg.team_name}" with ${msg.count} participant${msg.count === 1 ? '' : 's'}.`
    editing.value = false
    await load()
  } catch (err) {
    console.error('Failed to save team', err)
    error.value = extractFrappeError(err)
  } finally {
    saving.value = false
  }
}

const getDocstatusLabel = (statusNum) => {
  if (statusNum === 0) return 'Saved'
  return 'Unknown'
}

watch(() => route.params.id, async () => {
  // === DYNAMIC-PERMS-START ===
  // // The previous record's answer is not this record's. Dropped before the
  // // refetch so a stale dict cannot gate the incoming team for a frame.
  // permStore.invalidate('Experiment Team', route.params.id)
  // await Promise.all([load(), permStore.fetchAndCache('Experiment Team', route.params.id)])
  // === DYNAMIC-PERMS-END ===
  await load()
  await loadSegmentsAndCostCenters()
})
onMounted(async () => {
  // === DYNAMIC-PERMS-START ===
  // await Promise.all([load(), permStore.fetchAndCache('Experiment Team', route.params.id)])
  // === DYNAMIC-PERMS-END ===
  await load()
  await loadSegmentsAndCostCenters()
})
</script>

<template>
  <div class="team-setup-container">
    <div class="page-header">
      <div class="page-header-left">
        <nav class="breadcrumb-nav">
          <router-link to="/" class="breadcrumb-link">Home</router-link>
          <span class="breadcrumb-separator">&gt;</span>
          <router-link to="/elab-notebook" class="breadcrumb-link">Elab Notebook</router-link>
          <span class="breadcrumb-separator">&gt;</span>
          <span class="breadcrumb-current">{{ route.params.id }}</span>
        </nav>
        <h1 class="page-title">
          {{ team?.team_name || team?.project_name || team?.project || 'Team' }}
        </h1>
        <p class="page-subtitle" v-if="team" style="display: flex; align-items: center; gap: 0.5rem;">
          <span
            class="status-badge status-draft"
            style="padding: 0.15rem 0.5rem; font-size: 0.75rem; border-radius: 50px; font-weight: 600;"
          >
            Saved
          </span>
          <span class="badge badge-count" style="background-color: var(--bg-elevated); color: var(--accent); border: 1px solid var(--border); font-size: 0.75rem; font-weight: 500; padding: 0.15rem 0.5rem; border-radius: 50px;">
            {{ experimentCount }} Experiments · {{ experimentCount }} Samples
          </span>
        </p>
      </div>

      <div class="page-header-right" v-if="team">
        <button
          v-if="canCreate"
          class="btn btn-primary"
          @click="userStore.openCreateExperimentModal(team.project, team.employee_function, team.project_name, team.name)"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="btn-icon-svg"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Create Experiment
        </button>
        <button v-else class="btn btn-primary" disabled :title="createReason">
          Create Experiment
        </button>
      </div>
    </div>

    <div v-if="error" class="form-error-banner">
      <strong>Something went wrong</strong>
      <span class="form-error-text">{{ error }}</span>
      <button class="form-error-close" @click="error = ''">×</button>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading team…</p>
    </div>

    <div v-else-if="!team" class="empty-state">
      <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <rect x="3" y="11" width="18" height="11" rx="2" />
        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
      </svg>
      <h3>Team not available</h3>
      <p>
        This team either does not exist, or you are neither its Employee Function head
        nor one of its participants.
      </p>
    </div>

    <div v-else class="team-layout">
      <!-- EDITABLE / READ-ONLY SCOPE -->
      <section class="meta-card">
        <h3 class="section-title">Scope</h3>
        <div class="scope-grid">
          <div class="form-group">
            <label class="form-label">Team Name *</label>
            <!-- === DYNAMIC-PERMS-START ===
            <input
              v-if="canEditTeam && editing"
              v-model="team.team_name"
              type="text"
              class="form-control"
              placeholder="e.g. R&D Team Alpha"
            />
            === DYNAMIC-PERMS-END === -->
            <input
              v-if="team.can_edit && editing"
              v-model="team.team_name"
              type="text"
              class="form-control"
              placeholder="e.g. R&D Team Alpha"
            />
            <input
              v-else
              type="text"
              :value="team.team_name"
              class="form-control readonly"
              readonly
            />
          </div>
          <div class="form-group">
            <label class="form-label">Employee Function</label>
            <input type="text" :value="team.employee_function" class="form-control readonly" readonly />
          </div>
          <div class="form-group">
            <label class="form-label">Head Name</label>
            <input type="text" :value="team.head_name" class="form-control readonly" readonly />
          </div>
          <div class="form-group">
            <label class="form-label">Project ID</label>
            <input type="text" :value="team.project" class="form-control readonly" readonly />
          </div>
          <div class="form-group">
            <label class="form-label">Project Name</label>
            <input type="text" :value="team.project_name || team.project_id" class="form-control readonly" readonly />
          </div>
          <div class="form-group">
            <label class="form-label">Segment *</label>
            <select 
              v-if="editing" 
              v-model="team.segment" 
              class="form-control form-select attractive-select"
            >
              <option value="">Select Segment...</option>
              <option v-for="seg in segments" :key="seg" :value="seg">{{ seg }}</option>
            </select>
            <input 
              v-else 
              type="text" 
              :value="team.segment || 'None'" 
              class="form-control readonly" 
              readonly 
            />
          </div>
          <div class="form-group">
            <label class="form-label">Cost Centre *</label>
            <select 
              v-if="editing" 
              v-model="team.cost_center" 
              class="form-control form-select attractive-select"
            >
              <option value="">Select Cost Centre...</option>
              <option v-for="cc in costCenters" :key="cc" :value="cc">{{ cc }}</option>
            </select>
            <input 
              v-else 
              type="text" 
              :value="team.cost_center || 'None'" 
              class="form-control readonly" 
              readonly 
            />
          </div>
        </div>

        <!-- === DYNAMIC-PERMS-START ===
        <p v-if="!canEditTeam" class="field-hint readonly-note">
          You are a participant on this team. Only {{ team.head_name || 'the function head' }}
          can change who is on it.
        </p>
        === DYNAMIC-PERMS-END === -->
        <p v-if="!team.can_edit" class="field-hint readonly-note">
          You are a participant on this team. Only {{ team.head_name || 'the function head' }}
          can change who is on it.
        </p>
        <p v-if="!canCreate" class="field-hint warn create-warning">{{ createReason }}</p>
      </section>

      <!-- PARTICIPANTS -->
      <section class="meta-card">
        <div class="table-actions">
          <div>
            <h3 class="section-title no-margin">Participants</h3>
            <p class="section-sub">
              {{ participants.length }} authorized ·
              <span class="team-ref">{{ team.name }}</span>
            </p>
          </div>
          <!-- === DYNAMIC-PERMS-START ===
          <div class="header-actions" v-if="canEditTeam">
          === DYNAMIC-PERMS-END === -->
          <div class="header-actions" v-if="team.can_edit">
            <button v-if="!editing" class="btn btn-secondary btn-sm" @click="startEdit">
              Edit participants
            </button>
            <template v-else>
              <span class="selected-pill">{{ selected.size }} selected</span>
              <button class="btn btn-secondary btn-sm" @click="cancelEdit">Cancel</button>
              <button class="btn btn-primary btn-sm" @click="save" :disabled="saving || !team.segment || !team.cost_center">
                <span v-if="saving" class="spinner btn-spinner"></span>
                {{ saving ? 'Saving…' : 'Save' }}
              </button>
            </template>
          </div>
        </div>

        <p v-if="notice" class="save-notice standalone">{{ notice }}</p>

        <!-- View mode -->
        <template v-if="!editing">
          <div v-if="!participants.length" class="grid-empty standalone">
            No participants yet. Nobody can create experiments for this project.
          </div>
          <ul v-else class="avatar-list">
            <li v-for="p in participants" :key="p.user" class="avatar-row">
              <span class="avatar">{{ initials(p) }}</span>
              <div class="candidate-text">
                <span class="candidate-name">{{ p.full_name || p.user }}</span>
                <span class="candidate-user">{{ p.user }}</span>
              </div>
              <span class="candidate-emp">{{ p.employee }}</span>
            </li>
          </ul>
        </template>

        <!-- Edit mode -->
        <template v-else>
          <input
            v-model="search"
            type="text"
            class="member-search"
            placeholder="Filter by name or email…"
          />
          <div v-if="!candidates.length" class="grid-empty standalone">
            No active employees are mapped to this Employee Function.
          </div>
          <ul v-else class="candidate-list">
            <li
              v-for="c in filteredCandidates"
              :key="c.user"
              class="candidate"
              :class="{ picked: selected.has(c.user) }"
              @click="toggle(c.user)"
            >
              <input type="checkbox" :checked="selected.has(c.user)" @click.stop="toggle(c.user)" />
              <div class="candidate-text">
                <span class="candidate-name">{{ c.full_name || c.user }}</span>
                <span class="candidate-user">{{ c.user }}</span>
              </div>
              <span class="candidate-emp">{{ c.employee }}</span>
            </li>
            <li v-if="!filteredCandidates.length" class="candidate muted">
              No one matches “{{ search }}”.
            </li>
          </ul>
        </template>
      </section>
    </div>
    
  </div>
</template>
