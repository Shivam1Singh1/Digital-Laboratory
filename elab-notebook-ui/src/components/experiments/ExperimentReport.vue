<script setup>
/**
 * Read-only roll-up of a run and everything linked below it.
 *
 * The tree arrives nested from api/hierarchy.get_experiment_report and is
 * rendered by ReportNode, which recurses into its own children. It used to be
 * flattened here and indented by a margin computed from depth; nesting the
 * cards for real means a branch collapses with its parent, which a flat list
 * cannot do.
 *
 * Only offered at Master Experiment and Experiment - see utils/reportTab.js.
 * Depth is not otherwise capped: the four-level rule is a property of today's
 * categories, not of this view.
 */
import { ref, computed, watch, onMounted } from 'vue'
import axios from 'axios'
import { readServerError } from '../../utils/serverError'
import ReportNode from './ReportNode.vue'
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

const descendantCount = computed(() => Math.max(nodeCount.value - 1, 0))

// Report scope. 'successful' follows only runs flagged Successful / Include in
// Report and prunes an unflagged branch whole - see
// api/hierarchy.get_successful_subtree, which gates the branch rather than the
// row. It is the default because that is what a report is for; the full tree is
// one click away for anyone checking what was left out.
const SCOPES = [
  { key: 'successful', label: 'Successful sub-tree only' },
  { key: 'full', label: 'Full hierarchy' },
]
const scope = ref('successful')
const scopedToSuccessful = computed(() => scope.value === 'successful')

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
// Reloads rather than filters in place: the pruning decision is the server's,
// and re-deriving it here would be a second implementation of the same rule.
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

      <ReportNode :node="node" :depth="0" />
    </template>

    <div v-else class="rep-alert">
      {{ error || 'Could not load the report for this run.' }}
    </div>
  </div>
</template>
