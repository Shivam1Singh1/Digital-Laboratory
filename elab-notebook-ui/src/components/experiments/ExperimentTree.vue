<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import axios from 'axios'
import { readServerError } from '../../utils/serverError'
import './ExperimentTree.css'

const API = 'elab_notebook.elab_notebook.api.hierarchy'

const props = defineProps({
  experimentId: { type: String, required: true },
})

const loading = ref(true)
const error = ref('')
const notice = ref('')

const node = ref(null)
const ancestors = ref([])
const childCategory = ref('')
const canLink = ref(false)

// Attach-children picker
const picking = ref(false)
const loadingCandidates = ref(false)
const candidates = ref([])
const selected = ref(new Set())
const candidateFilter = ref('')
const linking = ref(false)
const unlinkingId = ref('')

// Navigating from the tree keeps you on the tree: ?tab=tree is what
// ExperimentDetail reads to pick the open tab, so clicking a node lands on that
// run's own tree rather than dropping back to General.
const experimentUrl = (name) => ({
  path: `/experiments/${encodeURIComponent(name)}`,
  query: { tab: 'tree' },
})

/**
 * The subtree arrives nested, which is the honest shape for the relationship,
 * but it renders as a flat list of rows carrying their own connector geometry.
 * Flattening once here keeps the template a plain v-for: a self-recursive
 * component would need its own name resolution and gives nothing back at a
 * maximum depth of four.
 *
 * Each row carries what it needs to draw its own share of the trunk:
 *   `hasNext`          - a sibling follows, so this row's elbow is a tee, not a
 *                        corner, and the trunk continues past it.
 *   `ancestorHasNext`  - one flag per ancestor column, true where that ancestor
 *                        still has siblings pending and its vertical line must
 *                        keep running down through this row. Without it, a
 *                        deep branch draws lines through columns that have
 *                        already closed.
 */
const flatten = (node, depth = 0, ancestorHasNext = [], hasNext = false, out = []) => {
  out.push({ node, depth, ancestorHasNext, hasNext })
  const kids = node.children || []
  kids.forEach((child, index) =>
    flatten(
      child,
      depth + 1,
      depth === 0 ? [] : [...ancestorHasNext, hasNext],
      index < kids.length - 1,
      out
    )
  )
  return out
}

const rows = computed(() => (node.value ? flatten(node.value) : []))

const descendantCount = computed(() => Math.max(rows.value.length - 1, 0))

// Only the run being viewed can adopt from here, so Unlink is offered on its
// direct children alone. A grandchild's own picker lives on its own page.
const directChildNames = computed(
  () => new Set((node.value?.children || []).map((c) => c.name))
)

const filteredCandidates = computed(() => {
  const needle = candidateFilter.value.trim().toLowerCase()
  if (!needle) return candidates.value
  return candidates.value.filter((c) =>
    [c.name, c.title, c.aim].some((v) => (v || '').toLowerCase().includes(needle))
  )
})

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await axios.get(`/api/method/${API}.get_experiment_subtree`, {
      params: { experiment: props.experimentId },
    })
    const data = res.data.message || {}
    node.value = data.node || null
    ancestors.value = data.ancestors || []
    childCategory.value = data.child_category || ''
    canLink.value = Boolean(data.can_link)
  } catch (err) {
    console.error('Failed to load experiment tree:', err)
    error.value = readServerError(err, 'Could not load the experiment tree for this run.')
    node.value = null
  } finally {
    loading.value = false
  }
}

const loadCandidates = async () => {
  if (!node.value) return
  loadingCandidates.value = true
  error.value = ''
  try {
    const res = await axios.get(`/api/method/${API}.get_available_children`, {
      params: {
        project: node.value.project || '',
        employee_function: node.value.employee_function || '',
        parent_category: node.value.experiment_category || '',
        parent: node.value.name,
      },
    })
    candidates.value = res.data.message || []
  } catch (err) {
    console.error('Failed to load available children:', err)
    error.value = readServerError(err, 'Could not load the experiments available to link.')
    candidates.value = []
  } finally {
    loadingCandidates.value = false
  }
}

const openPicker = async () => {
  picking.value = true
  notice.value = ''
  selected.value = new Set()
  candidateFilter.value = ''
  await loadCandidates()
}

const closePicker = () => {
  picking.value = false
  selected.value = new Set()
}

const toggle = (name) => {
  // Reassigning is what Vue tracks; mutating the Set in place does not re-render.
  const next = new Set(selected.value)
  next.has(name) ? next.delete(name) : next.add(name)
  selected.value = next
}

const linkSelected = async () => {
  if (!selected.value.size) return
  linking.value = true
  error.value = ''
  try {
    const res = await axios.post(`/api/method/${API}.link_child_experiments`, {
      parent: node.value.name,
      children: Array.from(selected.value),
    })
    const linked = res.data.message?.linked || []
    notice.value = `Linked ${linked.length} experiment${linked.length === 1 ? '' : 's'} under this run.`
    closePicker()
    await load()
  } catch (err) {
    console.error('Failed to link children:', err)
    // The server rejects the whole batch and names the run at fault, so its own
    // message is worth more here than a generic count.
    error.value = readServerError(err, 'Could not link the selected experiments. Nothing was changed.')
  } finally {
    linking.value = false
  }
}

const unlink = async (child) => {
  if (!confirm(`Unlink ${child.name} from this experiment? It returns to the pool of available runs.`)) {
    return
  }
  unlinkingId.value = child.name
  error.value = ''
  try {
    await axios.post(`/api/method/${API}.unlink_child_experiment`, {
      parent: node.value.name,
      child: child.name,
    })
    notice.value = `Unlinked ${child.name}.`
    await load()
  } catch (err) {
    console.error('Failed to unlink child:', err)
    error.value = readServerError(err, `Could not unlink ${child.name}.`)
  } finally {
    unlinkingId.value = ''
  }
}

const stateClass = (state) => {
  const s = (state || '').toLowerCase()
  if (s.includes('approved')) return 'tree-state-approved'
  if (s.includes('rejected')) return 'tree-state-rejected'
  if (s.includes('pending')) return 'tree-state-pending'
  if (s.includes('running')) return 'tree-state-running'
  if (s.includes('completed')) return 'tree-state-completed'
  return 'tree-state-draft'
}

watch(() => props.experimentId, load)
onMounted(load)
</script>

<template>
  <div class="experiment-tree">
    <div v-if="loading" class="tree-status">Loading the experiment tree…</div>

    <template v-else-if="node">
      <div v-if="error" class="tree-alert tree-alert-error">{{ error }}</div>
      <div v-if="notice" class="tree-alert tree-alert-ok">{{ notice }}</div>

      <!-- Upward view. The tree below only ever descends, so the parent chain is
           the other half of the relationship and has to be reachable from here. -->
      <div class="tree-ancestry">
        <span class="tree-ancestry-label">Parent chain</span>
        <template v-if="ancestors.length">
          <span v-for="a in ancestors" :key="a.name" class="tree-crumb-wrap">
            <router-link :to="experimentUrl(a.name)" class="tree-crumb">
              <span class="tree-crumb-cat">{{ a.experiment_category || 'Uncategorised' }}</span>
              <span class="font-mono">{{ a.name }}</span>
            </router-link>
            <span class="tree-crumb-sep" aria-hidden="true">›</span>
          </span>
          <span class="tree-crumb tree-crumb-current">
            <span class="tree-crumb-cat">{{ node.experiment_category || 'Uncategorised' }}</span>
            <span class="font-mono">{{ node.name }}</span>
          </span>
        </template>
        <span v-else class="tree-ancestry-none">
          This run has no parent — it is the top of its own tree.
        </span>
      </div>

      <div class="tree-toolbar">
        <p class="tree-summary">
          <template v-if="descendantCount">
            {{ descendantCount }} experiment{{ descendantCount === 1 ? '' : 's' }} linked below this run.
          </template>
          <template v-else-if="childCategory">
            Nothing is linked below this run yet.
          </template>
          <template v-else>
            {{ node.experiment_category || 'This run' }} is the lowest level — it has no children.
          </template>
        </p>
        <button v-if="canLink && !picking" class="btn btn-secondary btn-sm" @click="openPicker">
          + Attach {{ childCategory }}
        </button>
      </div>

      <!-- Picker for attaching children after the parent already exists. -->
      <div v-if="picking" class="tree-picker">
        <div class="tree-picker-head">
          <h4 class="tree-picker-title">Available {{ childCategory }}s</h4>
          <span class="tree-selected-pill">{{ selected.size }} selected</span>
        </div>
        <p class="tree-hint">
          Runs one level below, in project {{ node.project }} under
          {{ node.employee_function }}, that are not already linked to a parent.
        </p>
        <input
          v-model="candidateFilter"
          type="text"
          class="tree-filter"
          placeholder="Filter by ID, title or aim…"
        />
        <div v-if="loadingCandidates" class="tree-status">Looking for available experiments…</div>
        <div v-else-if="!candidates.length" class="tree-empty">
          No unlinked {{ childCategory }} exists for this project and Employee Function.
        </div>
        <div v-else-if="!filteredCandidates.length" class="tree-empty">
          No available experiment matches “{{ candidateFilter }}”.
        </div>
        <ul v-else class="tree-candidates">
          <li
            v-for="c in filteredCandidates"
            :key="c.name"
            class="tree-candidate"
            :class="{ picked: selected.has(c.name) }"
            @click="toggle(c.name)"
          >
            <input type="checkbox" :checked="selected.has(c.name)" @click.stop="toggle(c.name)" />
            <div class="tree-candidate-text">
              <span class="tree-candidate-id font-mono">{{ c.name }}</span>
              <span class="tree-candidate-sub">{{ c.title || c.aim || 'Untitled run' }}</span>
            </div>
            <span class="tree-state" :class="stateClass(c.workflow_state)">
              {{ c.workflow_state || 'Draft' }}
            </span>
          </li>
        </ul>
        <div class="tree-picker-actions">
          <button class="btn btn-secondary btn-sm" @click="closePicker" :disabled="linking">Cancel</button>
          <button
            class="btn btn-primary btn-sm"
            @click="linkSelected"
            :disabled="!selected.size || linking"
          >
            {{ linking ? 'Linking…' : `Link ${selected.size} experiment${selected.size === 1 ? '' : 's'}` }}
          </button>
        </div>
      </div>

      <!-- Downward view: this run highlighted as the root of what is shown.
           The whole row is the link, so clicking anywhere on a descendant opens
           it - the Unlink button stops propagation so it stays a button. -->
      <ul class="tree-rows">
        <li
          v-for="row in rows"
          :key="row.node.name"
          class="tree-row"
        >
          <!-- Trunk. One column per ancestor, then this row's own elbow. -->
          <span
            v-for="(running, i) in row.ancestorHasNext"
            :key="`guide-${i}`"
            class="tree-guide"
            :class="{ 'tree-guide-on': running }"
            aria-hidden="true"
          ></span>
          <span
            v-if="row.depth > 0"
            class="tree-elbow"
            :class="{ 'tree-elbow-last': !row.hasNext }"
            aria-hidden="true"
          ></span>

          <component
            :is="row.depth === 0 ? 'span' : 'router-link'"
            :to="row.depth === 0 ? undefined : experimentUrl(row.node.name)"
            class="tree-node"
            :class="{ 'tree-node-current': row.depth === 0 }"
          >
            <span class="tree-cat-badge">{{ row.node.experiment_category || 'Uncategorised' }}</span>
            <span class="tree-row-text">
              <span class="tree-row-id font-mono">{{ row.node.name }}</span>
              <span class="tree-row-title">{{ row.node.title || row.node.aim || 'Untitled run' }}</span>
            </span>
            <span class="tree-state" :class="stateClass(row.node.workflow_state)">
              {{ row.node.workflow_state || 'Draft' }}
            </span>
            <span v-if="row.depth === 0" class="tree-you-are-here">Viewing</span>
          </component>

          <button
            v-if="canLink && directChildNames.has(row.node.name)"
            class="tree-unlink-btn"
            :disabled="unlinkingId === row.node.name"
            :title="`Unlink ${row.node.name} from this experiment`"
            @click.prevent.stop="unlink(row.node)"
          >
            {{ unlinkingId === row.node.name ? '…' : 'Unlink' }}
          </button>
        </li>
      </ul>
    </template>

    <div v-else class="tree-alert tree-alert-error">
      {{ error || 'Could not load the experiment tree for this run.' }}
    </div>
  </div>
</template>
