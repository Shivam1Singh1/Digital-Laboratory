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

// `root` is the top of the whole tree this run belongs to, not the run itself -
// the server walks up `parent_experiment` before it walks down, so opening a Sub
// Sub Experiment still renders its Master and everything under it. `currentName`
// is the run whose page this is, and the only thing that distinguishes it from
// any other row is the highlight.
const root = ref(null)
const currentName = ref('')
const childCategory = ref('')
const canLink = ref(false)

const findNode = (n, name) => {
  if (!n) return null
  if (n.name === name) return n
  for (const child of n.children || []) {
    const hit = findNode(child, name)
    if (hit) return hit
  }
  return null
}

// Everything that acts on "this run" - the Attach picker, Unlink, the summary
// count - reads this, not `root`. Falling back to `root` keeps those controls
// pointed at a real node if the current one is ever missing from the tree.
const currentNode = computed(() => findNode(root.value, currentName.value) || root.value)

const isCurrent = (name) => name === currentName.value

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
 * Create form, seeded to land one level below the run being viewed.
 *
 * Only seeds - it grants nothing. The form re-fetches the legal parents for the
 * seeded category and clears `parent_experiment` if this run is not among them,
 * so a stale or hand-edited URL cannot attach a child where the server would
 * refuse it. Project and Employee Function come along because they are the scope
 * a parent and child must share; the team is left for the author to pick, since
 * a child run does not necessarily belong to the parent's.
 */
const newChildUrl = computed(() => ({
  path: '/experiments/new',
  query: {
    experiment_category: childCategory.value,
    parent_experiment: currentNode.value?.name || '',
    project: currentNode.value?.project || '',
    employee_function: currentNode.value?.employee_function || '',
  },
}))

/* Dot colour per level. The category strings are the server's -- hierarchy.py
 * CATEGORIES is the source of truth for both the names and this top-to-bottom
 * order. A value not in this list is an older or hand-set category and renders
 * grey rather than borrowing the colour of a level it is not. */
const CATEGORY_LEVELS = [
  { category: 'Master Experiment', slug: 'master' },
  { category: 'Experiment', slug: 'experiment' },
  { category: 'Sub Experiment', slug: 'sub' },
  { category: 'Sub Sub Experiment', slug: 'subsub' },
]

const dotClass = (category) =>
  `tree-dot-${CATEGORY_LEVELS.find((l) => l.category === category)?.slug || 'other'}`

/* Which branches are open, by node name. A Set of keys rather than an `expanded`
 * flag written onto the nodes: `load()` replaces the tree wholesale on every
 * link, unlink and route change, and per-node flags would be lost with it. */
const expandedKeys = ref(new Set())

// Only nodes that actually have children can be expanded, so only they are ever
// in the set - Expand All must not leave keys behind for leaves.
const collectExpandable = (n, out = []) => {
  if ((n.child_count || 0) > 0) out.push(n.name)
  ;(n.children || []).forEach((child) => collectExpandable(child, out))
  return out
}

const expandableKeys = computed(() => (root.value ? collectExpandable(root.value) : []))

const isExpanded = (name) => expandedKeys.value.has(name)

// Reassigning is what Vue tracks; mutating the Set in place does not re-render.
const toggleExpand = (name) => {
  const next = new Set(expandedKeys.value)
  next.has(name) ? next.delete(name) : next.add(name)
  expandedKeys.value = next
}

const expandAll = () => {
  expandedKeys.value = new Set(expandableKeys.value)
}

const collapseAll = () => {
  expandedKeys.value = new Set()
}

const allExpanded = computed(
  () => expandableKeys.value.length > 0 && expandableKeys.value.every(isExpanded)
)

/**
 * The subtree arrives nested, which is the honest shape for the relationship,
 * but it renders as a flat list of rows carrying their own connector geometry.
 * Flattening once here keeps the template a plain v-for: a self-recursive
 * component would need its own name resolution and gives nothing back at a
 * maximum depth of four.
 *
 * A collapsed node contributes its own row and stops - its descendants are held
 * in `node`, not dropped, so reopening it costs no round trip.
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
  if (!expandedKeys.value.has(node.name)) return out
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

const rows = computed(() => (root.value ? flatten(root.value) : []))

// Counted off the current run's own branch, not off `rows`: the summary states
// what is linked below *this* run, which is not the whole tree now that the tree
// starts at the root, and does not change when a branch is collapsed from view.
const countDescendants = (n) =>
  (n.children || []).reduce((sum, child) => sum + 1 + countDescendants(child), 0)

const descendantCount = computed(() =>
  currentNode.value ? countDescendants(currentNode.value) : 0
)

// Only the run being viewed can adopt from here, so Unlink is offered on its
// direct children alone. A grandchild's own picker lives on its own page.
const directChildNames = computed(
  () => new Set((currentNode.value?.children || []).map((c) => c.name))
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
    const res = await axios.get(`/api/method/${API}.get_experiment_root_tree`, {
      params: { experiment: props.experimentId },
    })
    const data = res.data.message || {}
    root.value = data.node || null
    currentName.value = data.current || props.experimentId
    childCategory.value = data.child_category || ''
    canLink.value = Boolean(data.can_link)
    // Open by default: the whole subtree is already in hand, and the tab drew it
    // in full before it had controls. Collapsing is the deliberate act, not
    // expanding. A fresh tree also drops stale keys from the run left behind.
    expandAll()
  } catch (err) {
    console.error('Failed to load experiment tree:', err)
    error.value = readServerError(err, 'Could not load the experiment tree for this run.')
    root.value = null
    expandedKeys.value = new Set()
  } finally {
    loading.value = false
  }
}

const loadCandidates = async () => {
  const run = currentNode.value
  if (!run) return
  loadingCandidates.value = true
  error.value = ''
  try {
    const res = await axios.get(`/api/method/${API}.get_available_children`, {
      params: {
        project: run.project || '',
        employee_function: run.employee_function || '',
        parent_category: run.experiment_category || '',
        parent: run.name,
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
      parent: currentNode.value.name,
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
      parent: currentNode.value.name,
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

    <template v-else-if="root">
      <div v-if="error" class="tree-alert tree-alert-error">{{ error }}</div>
      <div v-if="notice" class="tree-alert tree-alert-ok">{{ notice }}</div>

      <!-- No separate parent-chain breadcrumb: the tree starts at the root, so
           the ancestors of the current run are rows in it like any other, and
           clicking upward is the same gesture as clicking downward. -->
      <div class="tree-toolbar">
        <p class="tree-summary">
          <template v-if="descendantCount">
            {{ descendantCount }} experiment{{ descendantCount === 1 ? '' : 's' }} linked below this run.
          </template>
          <template v-else-if="childCategory">
            Nothing is linked below this run yet.
          </template>
          <template v-else>
            {{ currentNode?.experiment_category || 'This run' }} is the lowest level — it has no children.
          </template>
        </p>
        <div class="tree-toolbar-actions">
          <!-- View controls, not create actions, so they stay set off from the
               buttons that make rows. Icon plus its name: icon-only left the two
               unreadable until hovered, and a tooltip is not a label. Both stay
               on screen in every state - the tree is usually part open, where
               either one is a real move, and a single toggle would have to guess
               which. The spent one greys out but stays hoverable on
               `aria-disabled` rather than `disabled`; both handlers are
               idempotent, so the greyed click is a no-op anyway. -->
          <template v-if="expandableKeys.length">
            <div class="tree-view-actions" role="group" aria-label="Tree view">
              <button
                class="tree-view-btn"
                title="Expand every branch"
                :aria-disabled="allExpanded"
                @click="expandAll"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <polyline points="7 6 12 11 17 6" />
                  <polyline points="7 13 12 18 17 13" />
                </svg>
                <span>Expand all</span>
              </button>
              <button
                class="tree-view-btn"
                title="Collapse every branch"
                :aria-disabled="!expandedKeys.size"
                @click="collapseAll"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <polyline points="7 11 12 6 17 11" />
                  <polyline points="7 18 12 13 17 18" />
                </svg>
                <span>Collapse all</span>
              </button>
            </div>
            <span class="tree-toolbar-divider" aria-hidden="true"></span>
          </template>
          <!-- One way down a level now: start a run that does not exist yet.
               This is a plain link into the create form - it seeds the parent and
               scope and nothing else, so every rule still runs where it already
               lives (get_parent_candidates drops the seed if this run may not
               adopt, and LabExperiment.validate() re-checks on save).

               The "+ Attach" button that stood beside it is gone. Adopting an
               already-existing run is no longer offered from this toolbar; the
               picker below it is now unreachable rather than deleted, so putting
               it back is one line here. -->
          <router-link
            v-if="canLink && !picking"
            :to="newChildUrl"
            class="btn btn-secondary btn-sm"
          >
            + New {{ childCategory }}
          </router-link>
        </div>
      </div>

      <!-- Picker for attaching children after the parent already exists. -->
      <div v-if="picking" class="tree-picker">
        <div class="tree-picker-head">
          <h4 class="tree-picker-title">Available {{ childCategory }}s</h4>
          <span class="tree-selected-pill">{{ selected.size }} selected</span>
        </div>
        <p class="tree-hint">
          Runs one level below, in project {{ currentNode?.project }} under
          {{ currentNode?.employee_function }}, that are not already linked to a parent.
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

          <!-- Sits outside .tree-node, like Unlink: the row is a link, and a
               control inside it would navigate on the way to toggling. Leaves
               get a spacer so every node at one depth starts at one x. -->
          <button
            v-if="row.node.child_count > 0"
            class="tree-toggle"
            :aria-expanded="isExpanded(row.node.name)"
            :aria-label="`${isExpanded(row.node.name) ? 'Collapse' : 'Expand'} ${row.node.name}`"
            @click.prevent.stop="toggleExpand(row.node.name)"
          >
            <span
              class="tree-caret"
              :class="{ 'tree-caret-open': isExpanded(row.node.name) }"
              aria-hidden="true"
            ></span>
          </button>
          <span v-else class="tree-toggle-spacer" aria-hidden="true"></span>

          <!-- Every row is a link except the one you are already on, in both
               directions: an ancestor above the current run navigates exactly
               like a descendant below it. -->
          <component
            :is="isCurrent(row.node.name) ? 'span' : 'router-link'"
            :to="isCurrent(row.node.name) ? undefined : experimentUrl(row.node.name)"
            class="tree-node"
            :class="{ 'tree-node-current': isCurrent(row.node.name) }"
          >
            <span
              class="tree-dot"
              :class="dotClass(row.node.experiment_category)"
              aria-hidden="true"
            ></span>
            <span class="tree-cat-badge">{{ row.node.experiment_category || 'Uncategorised' }}</span>
            <span class="tree-row-text">
              <span class="tree-row-id font-mono">{{ row.node.name }}</span>
              <span class="tree-row-title">{{ row.node.title || row.node.aim || 'Untitled run' }}</span>
            </span>
            <span v-if="row.node.child_count > 0" class="tree-child-count">
              {{ row.node.child_count }} child{{ row.node.child_count === 1 ? '' : 'ren' }}
            </span>
            <span class="tree-state" :class="stateClass(row.node.workflow_state)">
              {{ row.node.workflow_state || 'Draft' }}
            </span>
            <span v-if="isCurrent(row.node.name)" class="tree-you-are-here">Viewing</span>
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

      <!-- Reads the dots above. Kept last so it explains a tree the eye has
           already reached, and shows every level, not only the ones present in
           this subtree - a Master with no Sub Sub yet should still say what the
           purple it may later grow would mean. -->
      <div class="tree-legend">
        <span class="tree-legend-label">Legend</span>
        <span v-for="level in CATEGORY_LEVELS" :key="level.slug" class="tree-legend-item">
          <span class="tree-dot" :class="`tree-dot-${level.slug}`" aria-hidden="true"></span>
          {{ level.category }}
        </span>
        <span class="tree-legend-item">
          <span class="tree-dot tree-dot-other" aria-hidden="true"></span>
          Other
        </span>
      </div>
    </template>

    <div v-else class="tree-alert tree-alert-error">
      {{ error || 'Could not load the experiment tree for this run.' }}
    </div>
  </div>
</template>
