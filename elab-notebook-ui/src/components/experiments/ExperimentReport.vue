<script setup>
/**
 * Read-only roll-up of a run and everything linked below it.
 *
 * The record's own content first, then a nested card per descendant, in
 * parent/child order. Depth is not capped: the four-level rule is a property of
 * today's categories, not of this view, and a report that silently stopped at
 * level three would be wrong the moment the hierarchy grew.
 *
 * Loading matches the Experiment Hierarchy tab beside it - one eager call, whole
 * subtree, no expand-on-demand (see api/hierarchy._descendants, which recurses
 * with limit_page_length=0). Nesting deeper than the handful of levels the
 * shading covers keeps the deepest card style rather than inventing new ones.
 */
import { ref, computed, watch, onMounted } from 'vue'
import axios from 'axios'
import { readServerError } from '../../utils/serverError'
import './ExperimentReport.css'

const API = 'elab_notebook.elab_notebook.api.hierarchy'

const props = defineProps({
  experimentId: { type: String, required: true },
})

const loading = ref(true)
const error = ref('')
const node = ref(null)
const ancestors = ref([])
const nodeCount = ref(0)

// The scientific body of a run, in the order it reads. `html` marks the Text
// Editor fields, which carry markup and are rendered as such - the rest are
// plain text and are interpolated, never injected.
const SECTIONS = [
  { key: 'aim', label: 'Aim / Hypothesis' },
  { key: 'sub_aim', label: 'Sub Aim' },
  { key: 'rationale', label: 'Rationale' },
  { key: 'procedure', label: 'Procedure', html: true },
  { key: 'precaution', label: 'Precaution' },
  { key: 'observation', label: 'Observation', html: true },
  { key: 'results', label: 'Results', html: true },
  { key: 'observation_and_conclusion', label: 'Observation & Conclusion' },
  { key: 'sample_details', label: 'Sample Details' },
]

const descendantCount = computed(() => Math.max(nodeCount.value - 1, 0))

// Report scope. 'full' is every descendant; 'successful' follows only runs
// flagged Successful / Include in Report, and prunes an unflagged branch whole -
// see api/hierarchy.get_successful_subtree, which gates the branch rather than
// the row. Kept as a scope switch rather than a filter applied to loaded data:
// the pruning decision is the server's, and re-deriving it here would be a
// second implementation of the same rule.
const SCOPES = [
  { key: 'full', label: 'Full hierarchy' },
  { key: 'successful', label: 'Successful sub-tree only' },
]
const scope = ref('full')
const scopedToSuccessful = computed(() => scope.value === 'successful')

const filled = (n) => SECTIONS.filter((s) => String(n[s.key] ?? '').trim())

const stateClass = (state) => {
  const s = (state || '').toLowerCase()
  if (s.includes('approved')) return 'rep-state-approved'
  if (s.includes('rejected')) return 'rep-state-rejected'
  if (s.includes('pending')) return 'rep-state-pending'
  if (s.includes('running')) return 'rep-state-running'
  if (s.includes('completed')) return 'rep-state-completed'
  return 'rep-state-draft'
}

/**
 * The tree arrives nested and is flattened once, the same way ExperimentTree
 * does it and for the same reason: a self-recursive component buys nothing here,
 * and one flat v-for keeps the depth handling in a single place.
 */
const flatten = (n, depth = 0, out = []) => {
  out.push({ node: n, depth })
  for (const child of n.children || []) flatten(child, depth + 1, out)
  return out
}

const cards = computed(() => (node.value ? flatten(node.value) : []))

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await axios.get(`/api/method/${API}.get_experiment_report`, {
      params: {
        experiment: props.experimentId,
        // 1/0 rather than true/false: it crosses as a query string either way,
        // and the endpoint reads it with cint.
        successful_only: scopedToSuccessful.value ? 1 : 0,
      },
    })
    const data = res.data.message || {}
    node.value = data.node || null
    ancestors.value = data.ancestors || []
    nodeCount.value = data.node_count || 0
  } catch (err) {
    console.error('Failed to load experiment report:', err)
    error.value = readServerError(err, 'Could not load the report for this run.')
    node.value = null
  } finally {
    loading.value = false
  }
}

watch(() => props.experimentId, load)
// Reloads rather than filters in place, for the reason given on SCOPES above.
watch(scope, load)
onMounted(load)
</script>

<template>
  <div class="experiment-report">
    <!-- Outside the loading branch so the scope stays switchable while the next
         one loads - moving it inside made the control vanish on every change,
         which is exactly when someone wants to change it back. -->
    <div class="rep-scope-row">
      <span class="rep-scope-label">Scope</span>
      <div class="rep-scope-options">
        <button
          v-for="s in SCOPES"
          :key="s.key"
          type="button"
          class="rep-scope-btn"
          :class="{ active: scope === s.key }"
          :disabled="loading"
          @click="scope = s.key"
        >
          {{ s.label }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="rep-status">Building the report…</div>

    <template v-else-if="node">
      <div class="rep-head">
        <div>
          <h3 class="rep-title">Report</h3>
          <p class="rep-sub">
            <template v-if="descendantCount">
              {{ node.name }} and {{ descendantCount }} experiment{{ descendantCount === 1 ? '' : 's' }}
              linked below it.
            </template>
            <template v-else-if="scopedToSuccessful">
              {{ node.name }} — no run below this one is flagged for reporting.
            </template>
            <template v-else>
              {{ node.name }} — nothing is linked below this run.
            </template>
          </p>
          <!-- Said out loud, because a pruned report and a full one look the
               same: the reader cannot see the branches that are missing. -->
          <p v-if="scopedToSuccessful" class="rep-scope-note">
            Showing only runs flagged <strong>Successful / Include in Report</strong>.
            An unflagged run is left out together with everything beneath it.
          </p>
        </div>
        <p v-if="ancestors.length" class="rep-ancestry">
          Under
          <span v-for="a in ancestors" :key="a.name" class="font-mono rep-ancestor">{{ a.name }}</span>
        </p>
      </div>

      <!-- One card per node. `depth` drives the indent and the shading, and is
           clamped for the style only - the nesting itself is unbounded. -->
      <div
        v-for="card in cards"
        :key="card.node.name"
        class="rep-card"
        :class="`rep-card-l${Math.min(card.depth, 4)}`"
        :style="{ marginLeft: `${Math.min(card.depth, 8) * 1.5}rem` }"
      >
        <div class="rep-card-head">
          <span class="rep-cat">{{ card.node.experiment_category || 'Uncategorised' }}</span>
          <span class="rep-id font-mono">{{ card.node.name }}</span>
          <span class="rep-state" :class="stateClass(card.node.workflow_state)">
            {{ card.node.workflow_state || 'Draft' }}
          </span>
          <span v-if="card.depth === 0" class="rep-current">This run</span>
        </div>

        <p class="rep-card-title">{{ card.node.title || card.node.aim || 'Untitled run' }}</p>

        <dl class="rep-meta">
          <div v-if="card.node.employee_name" class="rep-meta-item">
            <dt>Created by</dt>
            <dd>{{ card.node.employee_name }}</dd>
          </div>
          <div v-if="card.node.experiment_status" class="rep-meta-item">
            <dt>Status</dt>
            <dd>{{ card.node.experiment_status }}</dd>
          </div>
          <div v-if="card.node.template" class="rep-meta-item">
            <dt>Template</dt>
            <dd class="font-mono">{{ card.node.template }}</dd>
          </div>
        </dl>

        <div v-if="filled(card.node).length" class="rep-fields">
          <div v-for="s in filled(card.node)" :key="s.key" class="rep-field">
            <span class="rep-field-label">{{ s.label }}</span>
            <!-- eslint-disable-next-line vue/no-v-html -->
            <div v-if="s.html" class="rep-field-value rep-rich" v-html="card.node[s.key]"></div>
            <p v-else class="rep-field-value">{{ card.node[s.key] }}</p>
          </div>
        </div>
        <p v-else class="rep-empty-body">
          No aim, observations or results recorded on this run yet.
        </p>
      </div>
    </template>

    <div v-else class="rep-alert">
      {{ error || 'Could not load the report for this run.' }}
    </div>
  </div>
</template>
