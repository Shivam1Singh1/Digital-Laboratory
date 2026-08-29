<script setup>
/**
 * Full-subtree detail report: a run and everything linked below it, in full.
 *
 * The nodes arrive flat from api/hierarchy.get_full_subtree_report, each already
 * carrying its `parent_experiment` and a `depth` (root = 0), and are rendered in
 * the order the server returned them - parent immediately before its children.
 * The hierarchy is drawn from `depth` alone: one indent step and one guide rail
 * per level, using the same --tree-indent step ExperimentTree.css uses, so a
 * level sits at the same x in both views.
 *
 * Emptiness is handled at two scales, which is deliberate. The three short
 * scalar fields - Aim, Sub Aim, Rationale - still render when blank, with a
 * muted dash: they cost one line each, and "nobody recorded an aim" is itself a
 * finding that hiding the row would make indistinguishable from a field this
 * view forgot to ask for. The four heavy sections are dropped instead when they
 * have nothing in them - see showsMaterial / showsMethodology / showsObservation
 * and the Conclusion block - because a heading with a single dash under it is
 * not a finding, it is furniture, and four of them per node across a deep report
 * is most of the page.
 *
 * The rich-text fields have their file references made absolute on arrival, or
 * every embedded figure 404s when the report is read from the Vite dev server -
 * see resolveFileUrls in utils/frappeUrl.js.
 *
 * Level is encoded twice over: once as position (indent + guide rails, at the
 * same x as ExperimentTree's) and once as identity (the card's coloured,
 * textured left rail and its matching badge). Position answers "where does this
 * sit", identity answers "what is it" - in a branch that skips a level those are
 * different questions.
 *
 * Only offered at Master Experiment and Experiment (utils/reportTab.js). The
 * endpoint enforces the same rule itself and throws for any other level.
 */
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { readServerError } from '../../utils/serverError'
import { resolveFileUrls } from '../../utils/frappeUrl'
import './ExperimentReport.css'

const API = 'elab_notebook.elab_notebook.api.hierarchy'

const router = useRouter()

const props = defineProps({
  experimentId: { type: String, required: true },
})

const loading = ref(true)
const error = ref('')
const nodes = ref([])

const descendantCount = computed(() => Math.max(nodes.value.length - 1, 0))

// Every Text Editor field this view renders through v-html. Their file
// references are made absolute once, on arrival, rather than on each render -
// see resolveFileUrls. `observations[].observation` is the odd one out because
// it is a column inside a child table rather than a field on the node.
const RICH_FIELDS = ['conclusion', 'methodology_comments', 'observation_comments']

const resolveNodeFileUrls = (node) => {
  for (const field of RICH_FIELDS) {
    if (node[field]) node[field] = resolveFileUrls(node[field])
  }
  for (const row of node.observations || []) {
    if (row.observation) row.observation = resolveFileUrls(row.observation)
  }
  return node
}

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await axios.get(`/api/method/${API}.get_full_subtree_report`, {
      params: { experiment_name: props.experimentId },
    })
    nodes.value = (res.data.message?.nodes || []).map(resolveNodeFileUrls)
  } catch (err) {
    console.error('Failed to load experiment report:', err)
    error.value = readServerError(err, 'Could not load the report for this run.')
    nodes.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.experimentId, load)
onMounted(load)

// ---------------------------------------------------------------------------
// Presentation
// ---------------------------------------------------------------------------

const CATEGORY_SLUGS = {
  'Master Experiment': 'master',
  Experiment: 'experiment',
  'Sub Experiment': 'sub',
  'Sub Sub Experiment': 'subsub',
}

// Same slugs ExperimentTree uses, so a level is the same colour in both views.
// The slug picks a .rep-cat-* class in ExperimentReport.css, which is where the
// level's colour and its rail texture are defined - one class per level, set on
// the card, read by both the rail and the badge inside it.
const categorySlug = (node) => CATEGORY_SLUGS[node.experiment_category] || 'other'

// Exact names from the "Lab Experiment Workflow" record, with a substring pass
// beneath them for states written by its predecessor, which still appear on runs
// that have not moved since.
const STATE_CLASSES = {
  Start: 'rep-state-draft',
  'In Progress': 'rep-state-running',
  Completed: 'rep-state-completed',
  'Sent for Approval': 'rep-state-pending',
  'Edit Completed': 'rep-state-pending',
  Approved: 'rep-state-approved',
  Rejected: 'rep-state-rejected',
}

const stateClass = (node) => {
  const state = node.workflow_state || ''
  if (STATE_CLASSES[state]) return STATE_CLASSES[state]
  const s = state.toLowerCase()
  if (s.includes('approved')) return 'rep-state-approved'
  if (s.includes('rejected')) return 'rep-state-rejected'
  if (s.includes('pending')) return 'rep-state-pending'
  if (s.includes('running')) return 'rep-state-running'
  if (s.includes('completed')) return 'rep-state-completed'
  return 'rep-state-draft'
}

/**
 * Whether a value is worth printing, so the dash placeholder can stand in when
 * it is not.
 *
 * Rich fields need more than a truthiness test: an emptied Quill editor stores
 * "<p><br></p>", a non-empty string describing nothing. Tags are stripped before
 * measuring, but only for the decision - what renders is the original markup.
 * Mirrors `_has_text` in api/hierarchy.py, which makes the same call server-side
 * when it chooses between a run's observation and its template's.
 */
const hasText = (value, rich = false) => {
  if (value === null || value === undefined) return false
  const raw = String(value)
  if (!rich) return raw.trim() !== ''
  const text = raw.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim()
  // A field holding only an image or a table has no text but is not empty.
  return text !== '' || /<(img|table)\b/i.test(raw)
}

/**
 * The run's own page, as a real href so the id can open in a new tab.
 *
 * Resolved through the router rather than assembled as a string: that is what
 * applies the router's base, so the link is correct wherever the SPA is mounted.
 * It has to be an href on an <a> and not a router-link click handler, because
 * ctrl/cmd-click, middle-click and "Open in new tab" are the browser's to
 * handle - a handler that calls router.push intercepts all three and drops the
 * reader back onto the same page they were reading.
 */
const experimentHref = (name) =>
  router.resolve({ name: 'ExperimentDetail', params: { id: name } }).href

const rows = (node, fieldname) => node[fieldname] || []

/**
 * Whether a table-backed section is worth a heading on this node.
 *
 * The dash placeholder is right for a one-line field - it says "nobody recorded
 * this", which is a finding. A whole section reduced to a heading and a dash is
 * not: three of them stacked on a node that only ever carried an aim is noise,
 * multiplied by every node in a deep report.
 *
 * A section is shown when *any* of its parts has content - the comments alone
 * are enough to justify the heading, which is why Methodology and Observation
 * test both halves rather than only their table. Conclusion applies the same
 * rule inline, in the template, having only one part to test.
 */
const showsMaterial = (node) => rows(node, 'material_required').length > 0

const showsMethodology = (node) =>
  rows(node, 'methodology').length > 0 || hasText(node.methodology_comments, true)

const showsObservation = (node) =>
  rows(node, 'observations').length > 0 || hasText(node.observation_comments, true)

// Column order and labels per table, taken from the child doctypes. `rich` marks
// the one column that holds markup - the observation row's Description, which is
// a Text Editor. Every other column is interpolated as text and cannot inject.
//
// The columns the endpoint fetches are listed in _REPORT_TABLES in
// api/hierarchy.py; a column added there also needs a line here to be printed.
const MATERIAL_COLUMNS = [
  { key: 'item_code', label: 'Item Code' },
  { key: 'item_name', label: 'Item Name' },
  { key: 'uom', label: 'UOM' },
  { key: 'qty', label: 'Qty' },
]

const METHODOLOGY_COLUMNS = [
  { key: 'method', label: 'Method' },
  { key: 'time_to_complete', label: 'Time to Complete (min)' },
]

const OBSERVATION_COLUMNS = [
  { key: 'parameter', label: 'Parameter' },
  { key: 'unit', label: 'Unit' },
  { key: 'expected_range', label: 'Expected Range' },
  { key: 'observation', label: 'Description', rich: true },
  { key: 'remarks', label: 'Remarks' },
  { key: 'observed_by', label: 'Observed By' },
  { key: 'observed_on', label: 'Observed On' },
]
</script>

<template>
  <div class="experiment-report">
    <div v-if="loading" class="rep-status">Building the report…</div>

    <div v-else-if="error" class="rep-alert">{{ error }}</div>

    <template v-else-if="nodes.length">
      <div class="rep-head">
        <div>
          <h3 class="rep-title">Report</h3>
          <p class="rep-sub">
            <template v-if="descendantCount">
              {{ nodes[0].name }} and {{ descendantCount }} experiment{{ descendantCount === 1 ? '' : 's' }}
              linked below it, in full.
            </template>
            <template v-else>
              {{ nodes[0].name }} — nothing is linked below this run, so the report is
              this run alone.
            </template>
          </p>
        </div>
      </div>

      <div class="rep-nodes">
        <section
          v-for="node in nodes"
          :key="node.name"
          class="rep-node"
          :class="[`rep-node-d${Math.min(node.depth, 4)}`, `rep-cat-${categorySlug(node)}`]"
          :style="{ '--rep-depth': Math.min(node.depth, 4) }"
        >
          <!-- One rail per level above this node, at the same x as the tree's
               guides. Drawn as siblings of the card rather than as its border so
               the run of cards under one parent reads as a single branch. -->
          <span
            v-for="i in Math.min(node.depth, 4)"
            :key="`guide-${i}`"
            class="rep-guide"
            :style="{ '--rep-guide-index': i - 1 }"
            aria-hidden="true"
          ></span>

          <div class="rep-card">
            <div class="rep-card-head">
              <div class="rep-card-titles">
                <h4 class="rep-card-title">{{ node.title || node.name }}</h4>
                <a
                  :href="experimentHref(node.name)"
                  target="_blank"
                  rel="noopener"
                  class="rep-card-id font-mono"
                  :title="`Open ${node.name} in a new tab`"
                >{{ node.name }}</a>
              </div>
              <div class="rep-card-badges">
                <!-- depth 0 is the run whose page this is: the report is rooted
                     at it. It reads like any other card otherwise, and in a deep
                     report it is easy to lose track of which one you came from. -->
                <span v-if="node.depth === 0" class="rep-badge rep-badge-current">Current Document</span>
                <!-- Colour comes from the --rep-cat token the .rep-cat-* class
                     on the section sets, so the badge and the card's rail cannot
                     drift apart - they are one definition, used twice. -->
                <span v-if="node.experiment_category" class="rep-badge rep-badge-category">
                  {{ node.experiment_category }}
                </span>
                <span
                  v-if="node.workflow_state"
                  class="rep-badge rep-badge-state"
                  :class="stateClass(node)"
                >
                  {{ node.workflow_state }}
                </span>
                <span v-if="node.parent_experiment" class="rep-card-parent font-mono">
                  under {{ node.parent_experiment }}
                </span>
              </div>
            </div>

            <div class="rep-fields">
              <!-- AIM -->
              <div class="rep-field">
                <span class="rep-field-label">Aim</span>
                <p v-if="hasText(node.aim)" class="rep-field-value">{{ node.aim }}</p>
                <p v-else class="rep-field-value rep-blank">—</p>
              </div>

              <!-- SUB AIM -->
              <div class="rep-field">
                <span class="rep-field-label">Sub Aim</span>
                <p v-if="hasText(node.sub_aim)" class="rep-field-value">{{ node.sub_aim }}</p>
                <p v-else class="rep-field-value rep-blank">—</p>
              </div>

              <!-- RATIONALE. Plain Text on the doctype and edited as plain text,
                   so it is interpolated rather than rendered as markup - through
                   v-html a literal "<" a scientist typed would disappear into a
                   tag that was never opened. -->
              <div class="rep-field">
                <span class="rep-field-label">Rationale</span>
                <p v-if="hasText(node.rationale)" class="rep-field-value">{{ node.rationale }}</p>
                <p v-else class="rep-field-value rep-blank">—</p>
              </div>

              <!-- MATERIAL REQUIRED. Dropped entirely when the table is empty -
                   see showsMaterial: a heading over a dash is not a finding. -->
              <div v-if="showsMaterial(node)" class="rep-field">
                <span class="rep-field-label">Material Required</span>
                <div class="rep-table-wrap">
                  <table class="rep-table">
                    <thead>
                      <tr>
                        <th class="rep-table-idx">#</th>
                        <th v-for="col in MATERIAL_COLUMNS" :key="col.key">{{ col.label }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="row in rows(node, 'material_required')" :key="row.idx">
                        <td class="rep-table-idx">{{ row.idx }}</td>
                        <td v-for="col in MATERIAL_COLUMNS" :key="col.key">
                          <template v-if="hasText(row[col.key])">{{ row[col.key] }}</template>
                          <span v-else class="rep-blank">—</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <!-- METHODOLOGY + its comments. One section, so the pair is gated
                   together: the comments alone justify the heading, which is why
                   showsMethodology tests both halves. Inside it each half is
                   still conditioned on its own content, so a run with commentary
                   but no steps does not show an empty table. -->
              <template v-if="showsMethodology(node)">
                <div v-if="rows(node, 'methodology').length" class="rep-field">
                  <span class="rep-field-label">Methodology</span>
                  <div class="rep-table-wrap">
                    <table class="rep-table">
                      <thead>
                        <tr>
                          <th class="rep-table-idx">#</th>
                          <th v-for="col in METHODOLOGY_COLUMNS" :key="col.key">{{ col.label }}</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="row in rows(node, 'methodology')" :key="row.idx">
                          <td class="rep-table-idx">{{ row.idx }}</td>
                          <td v-for="col in METHODOLOGY_COLUMNS" :key="col.key">
                            <template v-if="hasText(row[col.key])">{{ row[col.key] }}</template>
                            <span v-else class="rep-blank">—</span>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <!-- METHODOLOGY COMMENTS. Lab Experiment has no such field; this is
                     the template's, which is why it is labelled as the template's -
                     the same text appears on every run built from that template. -->
                <div v-if="hasText(node.methodology_comments, true)" class="rep-field">
                  <span class="rep-field-label">
                    Methodology Comments
                    <span class="rep-field-source">from template {{ node.template }}</span>
                  </span>
                  <!-- eslint-disable-next-line vue/no-v-html -->
                  <div class="rep-field-value rep-rich" v-html="node.methodology_comments"></div>
                </div>
              </template>

              <!-- OBSERVATION + its comments, gated as one section for the same
                   reason as Methodology above. -->
              <template v-if="showsObservation(node)">
                <div v-if="rows(node, 'observations').length" class="rep-field">
                  <span class="rep-field-label">Observation</span>
                  <div class="rep-table-wrap">
                    <table class="rep-table">
                      <thead>
                        <tr>
                          <th class="rep-table-idx">#</th>
                          <th v-for="col in OBSERVATION_COLUMNS" :key="col.key">{{ col.label }}</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="row in rows(node, 'observations')" :key="row.idx">
                          <td class="rep-table-idx">{{ row.idx }}</td>
                          <td v-for="col in OBSERVATION_COLUMNS" :key="col.key">
                            <!-- eslint-disable-next-line vue/no-v-html -->
                            <div
                              v-if="col.rich && hasText(row[col.key], true)"
                              class="rep-rich"
                              v-html="row[col.key]"
                            ></div>
                            <template v-else-if="!col.rich && hasText(row[col.key])">
                              {{ row[col.key] }}
                          </template>
                          <span v-else class="rep-blank">—</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <!-- OBSERVATION COMMENTS. The run's own write-up when it has one,
                   the template's otherwise - said out loud either way, because a
                   reader has to be able to tell a template's boilerplate from an
                   observation somebody actually made. -->
              <div v-if="hasText(node.observation_comments, true)" class="rep-field">
                <span class="rep-field-label">
                  Observation Comments
                  <span v-if="node.observation_comments_from_template" class="rep-field-source">
                    from template {{ node.template }}
                  </span>
                </span>
                <!-- eslint-disable-next-line vue/no-v-html -->
                <div class="rep-field-value rep-rich" v-html="node.observation_comments"></div>
              </div>
              </template>

              <!-- CONCLUSION. Section-hidden rather than dashed, like the three
                   above it: this one carries images and tables, so the gap
                   between "a scientist wrote nothing" and "a scientist wrote a
                   figure" is the whole height of the card, and a dash sitting
                   where a figure would be reads as a failed render. hasText
                   treats an emptied editor's "<p><br></p>" as blank, and an
                   image or a table with no words around it as content. -->
              <div v-if="hasText(node.conclusion, true)" class="rep-field">
                <span class="rep-field-label">Conclusion</span>
                <!-- eslint-disable-next-line vue/no-v-html -->
                <div class="rep-field-value rep-rich" v-html="node.conclusion"></div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </template>

    <div v-else class="rep-alert">Could not load the report for this run.</div>
  </div>
</template>
