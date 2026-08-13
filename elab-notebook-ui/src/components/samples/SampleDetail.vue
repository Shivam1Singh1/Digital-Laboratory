<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { formatAuditDate } from '../../utils/dateFormatter'
import { readServerError } from '../../utils/serverError'
import './SampleDetail.css'

const API = 'elab_notebook.elab_notebook.api.sample'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const error = ref('')
const notice = ref('')

const sample = ref(null)
const parent = ref({})
const statusLabel = ref('Draft')
const commentsLocked = ref(false)
const canEditComments = ref(false)

const commentDraft = ref('')
const savingComments = ref(false)

const statusClass = computed(() => {
  const s = (statusLabel.value || '').toLowerCase()
  if (s === 'submitted') return 'status-approved'
  if (s === 'cancelled') return 'status-rejected'
  return 'status-draft'
})

const runStateClass = computed(() => {
  const s = (parent.value.workflow_state || '').toLowerCase()
  if (s.includes('approved')) return 'status-approved'
  if (s.includes('rejected')) return 'status-rejected'
  if (s.includes('pending')) return 'status-pending'
  return 'status-draft'
})

const commentsDirty = computed(
  () => commentDraft.value.trim() !== (sample.value?.comments || '').trim()
)

const runUrl = computed(() =>
  parent.value.name
    ? { path: `/experiments/${encodeURIComponent(parent.value.name)}`, query: { tab: 'samples' } }
    : null
)

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await axios.get(`/api/method/${API}.get_sample_detail`, {
      params: { name: route.params.id }
    })
    const data = res.data.message || {}
    sample.value = data.sample || null
    parent.value = data.parent || {}
    statusLabel.value = data.status_label || 'Draft'
    commentsLocked.value = Boolean(data.comments_locked)
    canEditComments.value = Boolean(data.can_edit_comments)
    commentDraft.value = sample.value?.comments || ''
  } catch (err) {
    console.error('Failed to load sample:', err)
    error.value = readServerError(err, 'Could not load this sample. It may not exist or you lack permission.')
    sample.value = null
  } finally {
    loading.value = false
  }
}

const saveComments = async () => {
  savingComments.value = true
  error.value = ''
  notice.value = ''
  try {
    await axios.put(`/api/resource/Sample/${encodeURIComponent(sample.value.name)}`, {
      comments: commentDraft.value
    })
    notice.value = 'Comments saved.'
    setTimeout(() => { notice.value = '' }, 4000)
    await load()
  } catch (err) {
    console.error('Failed to save comments:', err)
    error.value = readServerError(err, 'Could not save the comments for this sample.')
  } finally {
    savingComments.value = false
  }
}

// Same reuse trap as ExperimentDetail: only the :id param changes when moving
// between samples, so the component is kept alive and would otherwise keep
// showing the previous one.
watch(
  () => route.params.id,
  (next, previous) => {
    if (!next || next === previous) return
    sample.value = null
    parent.value = {}
    notice.value = ''
    load()
  }
)

onMounted(load)
</script>

<template>
  <div class="sample-detail-container">
    <div class="page-header">
      <div class="page-header-left">
        <nav class="breadcrumb-nav">
          <router-link to="/" class="breadcrumb-link">Home</router-link>
          <span class="breadcrumb-separator">&gt;</span>
          <router-link to="/samples" class="breadcrumb-link">Samples</router-link>
          <span class="breadcrumb-separator">&gt;</span>
          <span class="breadcrumb-current">{{ route.params.id }}</span>
        </nav>
        <h1 class="page-title">{{ sample?.name_of_sample || 'Sample' }}</h1>
        <p class="page-subtitle">
          Status:
          <span class="status-pill" :class="statusClass">{{ statusLabel }}</span>
          <template v-if="parent.workflow_state">
            <span class="subtitle-sep">·</span>
            Parent run:
            <span class="status-pill" :class="runStateClass">{{ parent.workflow_state }}</span>
          </template>
        </p>
      </div>
      <div class="page-header-right">
        <router-link v-if="runUrl" :to="runUrl" class="btn btn-secondary">Open Parent Run</router-link>
        <button class="btn btn-secondary" @click="router.push('/samples')">Back to Samples</button>
      </div>
    </div>

    <div v-if="error" class="sample-detail-alert sample-detail-alert-error">{{ error }}</div>
    <div v-if="notice" class="sample-detail-alert sample-detail-alert-ok">{{ notice }}</div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading sample…</p>
    </div>

    <template v-else-if="sample">
      <!-- Every stored field on the Sample doctype. -->
      <section class="card sample-card">
        <h3 class="sample-card-title">Sample</h3>
        <dl class="sample-grid">
          <div class="sample-field">
            <dt>Sample ID</dt>
            <dd class="font-mono">{{ sample.name }}</dd>
          </div>
          <div class="sample-field">
            <dt>Series</dt>
            <dd class="font-mono">{{ sample.series || '—' }}</dd>
          </div>
          <div class="sample-field">
            <dt>Elab No.</dt>
            <dd class="font-mono">{{ sample.elab_no || '—' }}</dd>
          </div>
          <div class="sample-field">
            <dt>Name of Sample</dt>
            <dd>{{ sample.name_of_sample || '—' }}</dd>
          </div>
          <div class="sample-field">
            <dt>Item</dt>
            <dd class="font-mono">{{ sample.item || '—' }}</dd>
          </div>
          <div class="sample-field">
            <dt>Quantity</dt>
            <dd class="font-mono">{{ sample.qty }} <span class="text-muted">{{ sample.uom || '' }}</span></dd>
          </div>
          <div class="sample-field">
            <dt>UOM</dt>
            <dd>{{ sample.uom || '—' }}</dd>
          </div>
          <div class="sample-field">
            <dt>Document Status</dt>
            <dd><span class="status-pill" :class="statusClass">{{ statusLabel }}</span></dd>
          </div>
          <div class="sample-field" v-if="sample.amended_from">
            <dt>Amended From</dt>
            <dd class="font-mono">{{ sample.amended_from }}</dd>
          </div>
        </dl>
      </section>

      <!-- Comments: the one field that stays writable after creation. -->
      <section class="card sample-card">
        <div class="sample-card-head">
          <h3 class="sample-card-title">Comments</h3>
          <span v-if="commentsLocked" class="sample-lock-pill">Locked</span>
        </div>

        <textarea
          v-model="commentDraft"
          class="form-control textarea"
          :class="{ readonly: !canEditComments }"
          :readonly="!canEditComments"
          rows="4"
          :placeholder="canEditComments ? 'Notes on this sample…' : 'No comments recorded.'"
        ></textarea>

        <div class="sample-comments-foot">
          <span class="field-hint">
            <template v-if="commentsLocked">
              Frozen because the parent run is {{ parent.workflow_state }}. Comments lock
              when the run is sent for approval — for everyone, System Managers included.
            </template>
            <template v-else-if="!canEditComments">
              This sample is cancelled, or you do not have write access to it.
            </template>
            <template v-else>
              Editable until the parent run is sent for approval.
            </template>
          </span>
          <button
            v-if="canEditComments"
            class="btn btn-secondary btn-sm"
            :disabled="savingComments || !commentsDirty"
            @click="saveComments"
          >
            {{ savingComments ? 'Saving…' : 'Save Comments' }}
          </button>
        </div>
      </section>

      <!-- Parent run context: a sample on its own says very little. -->
      <section class="card sample-card">
        <h3 class="sample-card-title">Parent Run</h3>
        <dl class="sample-grid" v-if="parent.name">
          <div class="sample-field">
            <dt>Run ID</dt>
            <dd>
              <router-link :to="runUrl" class="sample-link font-mono">{{ parent.name }}</router-link>
            </dd>
          </div>
          <div class="sample-field">
            <dt>Title</dt>
            <dd>{{ parent.title || '—' }}</dd>
          </div>
          <div class="sample-field sample-field-wide">
            <dt>Aim</dt>
            <dd>{{ parent.aim || '—' }}</dd>
          </div>
          <div class="sample-field">
            <dt>Project</dt>
            <dd class="font-mono">{{ parent.project || '—' }}</dd>
          </div>
          <div class="sample-field">
            <dt>Employee Function</dt>
            <dd class="font-mono">{{ parent.employee_function || '—' }}</dd>
          </div>
          <div class="sample-field">
            <dt>Experiment Team</dt>
            <dd class="font-mono">{{ parent.experiment_team || '—' }}</dd>
          </div>
          <div class="sample-field">
            <dt>Lead Scientist</dt>
            <dd>{{ parent.employee_name || '—' }}</dd>
          </div>
          <div class="sample-field">
            <dt>Category</dt>
            <dd>{{ parent.experiment_category || '—' }}</dd>
          </div>
          <div class="sample-field">
            <dt>Workflow State</dt>
            <dd><span class="status-pill" :class="runStateClass">{{ parent.workflow_state || 'Draft' }}</span></dd>
          </div>
        </dl>
        <p v-else class="field-hint">This sample is not linked to a run.</p>
      </section>

      <section class="card sample-card">
        <h3 class="sample-card-title">Record</h3>
        <dl class="sample-grid">
          <div class="sample-field">
            <dt>Created By</dt>
            <dd>{{ sample.owner }}</dd>
          </div>
          <div class="sample-field">
            <dt>Created</dt>
            <dd>{{ formatAuditDate(sample.creation) }}</dd>
          </div>
          <div class="sample-field">
            <dt>Last Modified By</dt>
            <dd>{{ sample.modified_by }}</dd>
          </div>
          <div class="sample-field">
            <dt>Last Modified</dt>
            <dd>{{ formatAuditDate(sample.modified) }}</dd>
          </div>
        </dl>
      </section>
    </template>

    <div v-else class="empty-state">
      <h3>Sample not found</h3>
      <p>{{ error || 'This sample does not exist, or you do not have access to it.' }}</p>
      <router-link to="/samples" class="btn btn-secondary mt-3">Back to Samples</router-link>
    </div>
  </div>
</template>
