<script setup>
/**
 * One card in the report, plus its children.
 *
 * Self-recursive, unlike ExperimentTree which flattens: the tree draws one row
 * per node and can hold depth in a number, while a report card *contains* its
 * children - a bordered card with the next level nested inside it. Flattening
 * would mean re-deriving the containment from an indent level, which is the
 * information a recursive component already has for free.
 *
 * Expansion state is per-node and lives here rather than in a shared Set: a
 * card's children are its own, and nothing outside needs to know whether they
 * are showing.
 */
import { ref, computed } from 'vue'

const props = defineProps({
  node: { type: Object, required: true },
  depth: { type: Number, default: 0 }
})

// Root and its direct children open; everything deeper starts closed. A Master
// with four levels under it would otherwise dump the whole programme on screen
// at once, which is the thing a report is meant to make readable.
const expanded = ref(props.depth < 1)

const children = computed(() => props.node.children || [])

const CATEGORY_SLUGS = {
  'Master Experiment': 'master',
  Experiment: 'experiment',
  'Sub Experiment': 'sub',
  'Sub Sub Experiment': 'subsub'
}

// Same slugs ExperimentTree uses, so a category is the same colour in both
// views. The colours themselves are the --tree-dot-* tokens; only the class
// prefix differs, because these are pills rather than dots.
const categorySlug = computed(() => CATEGORY_SLUGS[props.node.experiment_category] || 'other')

const stateClass = computed(() => {
  const s = (props.node.workflow_state || '').toLowerCase()
  if (s.includes('approved')) return 'rep-state-approved'
  if (s.includes('rejected')) return 'rep-state-rejected'
  if (s.includes('pending')) return 'rep-state-pending'
  if (s.includes('running')) return 'rep-state-running'
  if (s.includes('completed')) return 'rep-state-completed'
  return 'rep-state-draft'
})

/**
 * The record's body, in reading order.
 *
 * `rich` marks the fields that hold HTML - they are rendered as markup so the
 * tables, colours and images written by the Result-tab editors survive into the
 * report. Everything else is interpolated as text and can never inject.
 */
const SECTIONS = [
  { key: 'aim', label: 'Aim / Hypothesis' },
  { key: 'sub_aim', label: 'Sub Aim' },
  // Not rich, unlike the write-ups below it. `rationale` is a plain Text field
  // on the doctype and is edited as plain text, so rendering it through v-html
  // only meant a literal "<" a scientist typed would disappear into a tag that
  // was never opened - and it was the one plain-typed field that could inject.
  { key: 'rationale', label: 'Rationale' },
  { key: 'procedure', label: 'Procedure', rich: true },
  { key: 'precaution', label: 'Precaution' },
  { key: 'observation', label: 'Observation', rich: true },
  { key: 'results', label: 'Results', rich: true },
  { key: 'observation_and_conclusion', label: 'Observation & Conclusion', rich: true },
  { key: 'conclusion', label: 'Conclusion', rich: true },
  { key: 'sample_details', label: 'Sample Details' },
  { key: 'result', label: 'Result' },
  { key: 'experiment_status', label: 'Status' },
  { key: 'employee_name', label: 'Scientist' },
  { key: 'experiment_start_date', label: 'Start Date' },
  { key: 'experiment_end_date', label: 'End Date' },
  { key: 'template', label: 'Template' }
]

/**
 * Only the filled fields. A blank row carries no information and, multiplied by
 * every node in a deep tree, is most of the page.
 *
 * Rich fields need more than a truthiness test: an emptied Quill editor stores
 * "<p><br></p>", which is a non-empty string describing nothing. Tags are
 * stripped before measuring, but only for the decision - what renders is still
 * the original markup.
 */
const hasContent = (section) => {
  const raw = props.node[section.key]
  if (raw === null || raw === undefined) return false
  const value = String(raw)
  if (!section.rich) return value.trim() !== ''
  const text = value
    .replace(/<[^>]*>/g, '')
    .replace(/&nbsp;/g, ' ')
    .trim()
  // A field holding only an image or a table has no text but is not empty.
  return text !== '' || /<(img|table)\b/i.test(value)
}

const filled = computed(() => SECTIONS.filter(hasContent))
</script>

<template>
  <div class="rep-node" :class="`rep-node-d${Math.min(depth, 4)}`">
    <div class="rep-card">
      <div class="rep-card-head">
        <div class="rep-card-titles">
          <h4 class="rep-card-title">{{ node.title || node.name }}</h4>
          <span class="rep-card-id font-mono">{{ node.name }}</span>
        </div>
        <div class="rep-card-badges">
          <!-- depth 0 is the run whose page this is: the report is built from
               get_experiment_report(experiment) with that run as the root. It
               reads like any other card otherwise, and in a deep tree it is easy
               to lose track of which one you came from. -->
          <span v-if="depth === 0" class="rep-badge rep-badge-current">Current Document</span>
          <span v-if="node.experiment_category"
                class="rep-badge" :class="`rep-badge-${categorySlug}`">
            {{ node.experiment_category }}
          </span>
          <span v-if="node.workflow_state" class="rep-badge rep-badge-state" :class="stateClass">
            {{ node.workflow_state }}
          </span>
          <!-- Only worth a pill when true: every node in a successful-only
               report carries it, and a row of identical badges says nothing. -->
          <span v-if="node.is_successful" class="rep-badge rep-badge-success">Successful</span>
        </div>
      </div>

      <!-- Reuses .rep-fields / .rep-field-label / .rep-field-value / .rep-rich,
           which already existed for the flat renderer this replaced - the rows
           look the same, only their container changed. -->
      <div v-if="filled.length" class="rep-fields">
        <div v-for="s in filled" :key="s.key" class="rep-field">
          <span class="rep-field-label">{{ s.label }}</span>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <div v-if="s.rich" class="rep-field-value rep-rich" v-html="node[s.key]"></div>
          <p v-else class="rep-field-value">{{ node[s.key] }}</p>
        </div>
      </div>
      <p v-else class="rep-empty-body">No details recorded on this run.</p>

      <button
        v-if="children.length"
        type="button"
        class="rep-children-toggle"
        :aria-expanded="expanded ? 'true' : 'false'"
        @click="expanded = !expanded"
      >
        <span class="rep-chevron" :class="{ open: expanded }" aria-hidden="true">›</span>
        Linked Experiments
        <span class="rep-children-count">{{ children.length }}</span>
      </button>
    </div>

    <!-- Recursion. v-if rather than v-show: a collapsed branch of a deep tree
         should not be built at all, which is the point of collapsing it. -->
    <div v-if="children.length && expanded" class="rep-children">
      <ReportNode
        v-for="child in children"
        :key="child.name"
        :node="child"
        :depth="depth + 1"
      />
    </div>
  </div>
</template>
