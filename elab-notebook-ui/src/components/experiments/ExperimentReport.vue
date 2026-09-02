<script setup>

import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { readServerError } from '../../utils/serverError'
import { resolveFileUrls } from '../../utils/frappeUrl'
import ImageLightbox from '../common/ImageLightbox.vue'
import RichContent from '../common/RichContent.vue'
import ReportTable from './ReportTable.vue'
import { richHasContent, splitStored, joinStored } from '../../utils/richText'
import './ExperimentReport.css'

const API = 'elab_notebook.elab_notebook.api.hierarchy'

const router = useRouter()

const props = defineProps({
  experimentId: { type: String, required: true },
})

const loading = ref(true)
const error = ref('')
const nodes = ref([])


const lightboxSrc = ref('')

const onReportClick = (evt) => {
  const img = evt.target
  if (!img || img.tagName !== 'IMG') return
  if (!img.closest('.rep-rich')) return
  lightboxSrc.value = img.getAttribute('src') || ''
}

const descendantCount = computed(() => Math.max(nodes.value.length - 1, 0))


const RICH_FIELDS = [
  'procedure',
  'results',
  'observation_and_conclusion',
  'conclusion',
  'methodology_comments',
  'observation_comments',
]


const resolveRich = (raw) => {
  const { body, files } = splitStored(raw)
  return joinStored(resolveFileUrls(body), files)
}

const resolveNodeFileUrls = (node) => {
  for (const field of RICH_FIELDS) {
    if (node[field]) node[field] = resolveRich(node[field])
  }
  for (const row of node.observations || []) {
    if (row.observation) row.observation = resolveRich(row.observation)
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


const CATEGORY_SLUGS = {
  'Master Experiment': 'master',
  Experiment: 'experiment',
  'Sub Experiment': 'sub',
  'Sub Sub Experiment': 'subsub',
}


const categorySlug = (node) => CATEGORY_SLUGS[node.experiment_category] || 'other'


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


const hasText = (value, rich = false) => {
  if (value === null || value === undefined) return false
  if (rich) return richHasContent(String(value))
  return String(value).trim() !== ''
}


const experimentHref = (name) =>
  router.resolve({ name: 'ExperimentDetail', params: { id: name } }).href

const rows = (node, fieldname) => node[fieldname] || []


const showsMaterial = (node) => rows(node, 'material_required').length > 0

const showsMethodology = (node) =>
  rows(node, 'methodology').length > 0 || hasText(node.methodology_comments, true)

const showsObservation = (node) =>
  rows(node, 'observations').length > 0 || hasText(node.observation_comments, true)


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


const ITEM_COLUMNS = [
  { key: 'item', label: 'Item' },
  { key: 'item_name', label: 'Item Name' },
  { key: 'uom', label: 'UOM' },
  { key: 'qty', label: 'Qty' },
  { key: 'make', label: 'Make' },
  { key: 'catalogue_no', label: 'Catalogue No.' },
  { key: 'lot_no', label: 'Lot No' },
  { key: 'expiry_date', label: 'Expiry' },
  { key: 'storage', label: 'Storage' },
  { key: 'remarks', label: 'Remarks' },
]

const EQUIPMENT_COLUMNS = [
  { key: 'equipment_name', label: 'Equipment' },
  { key: 'equipment_id', label: 'Equipment ID' },
  { key: 'equipment_status', label: 'Status' },
  { key: 'qualification', label: 'Qualification Date' },
  { key: 'remarks', label: 'Remarks' },
]

const PROTOCOL_STEP_COLUMNS = [
  { key: 'step_no', label: 'Step' },
  { key: 'instruction', label: 'Instruction' },
  { key: 'expected_duration', label: 'Expected Duration (s)' },
  { key: 'is_critical', label: 'Critical', check: true },
  { key: 'attachment', label: 'Attachment', attach: true },
]

const METRIC_COLUMNS = [
  { key: 'quality_metrics', label: 'Parameter' },
  { key: 'value', label: 'Value' },
  { key: 'unit', label: 'Unit' },
]

const SAMPLE_COLUMNS = [
  { key: 'sample_id', label: 'Sample ID' },
  { key: 'sample_name', label: 'Sample Name' },
  { key: 'batch_no', label: 'Batch No.' },
  { key: 'warehouse', label: 'Warehouse' },
  { key: 'sample_vol', label: 'Volume' },
  { key: 'sample_detailsstage', label: 'Details / Stage' },
  { key: 'item', label: 'Item' },
  { key: 'qty', label: 'Qty' },
  { key: 'uom', label: 'UOM' },
  { key: 'results', label: 'Results' },
  { key: 'sampling_date', label: 'Sampled' },
  { key: 'date_of_analysis', label: 'Analysed' },
  { key: 'transfered_to', label: 'Transferred To' },
  { key: 'remarks', label: 'Remarks' },
  { key: 'attach', label: 'Attachment', attach: true },
]

const RESULT_ATTACHMENT_COLUMNS = [
  { key: 'name1', label: 'Name' },
  { key: 'file', label: 'File', attach: true },
]


const showsResult = (node) =>
  hasText(node.results, true) ||
  hasText(node.result) ||
  hasText(node.observation_and_conclusion, true) ||
  rows(node, 'result_attachment').length > 0


const resultClass = (value) => {
  const v = String(value || '').toLowerCase()
  if (v === 'pass') return 'rep-result-pass'
  if (v === 'fail') return 'rep-result-fail'
  return ''
}
</script>

<template>
  <!-- One delegated click for every image in every write-up below; see
       onReportClick for why it cannot be bound per image. -->
  <div class="experiment-report" @click="onReportClick">
    <ImageLightbox :src="lightboxSrc" @close="lightboxSrc = ''" />

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

              <!-- PROCEDURE + PRECAUTION. The doctype's Procedure section, which
                   the report did not carry at all until now. Section-hidden like
                   Conclusion: procedure holds figures, and a dash where a figure
                   would be reads as a failed render. -->
              <div v-if="hasText(node.procedure, true)" class="rep-field">
                <span class="rep-field-label">Procedure</span>
                <RichContent class="rep-field-value rep-rich" :value="node.procedure" />
              </div>

              <!-- Small Text, so interpolated rather than rendered as markup. -->
              <div v-if="hasText(node.precaution)" class="rep-field">
                <span class="rep-field-label">Precaution</span>
                <p class="rep-field-value">{{ node.precaution }}</p>
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

              <!-- The rest of what was consumed and used. ReportTable hides
                   itself when its table is empty, so these cost nothing on a
                   node that never recorded any. -->
              <ReportTable label="Items" :rows="rows(node, 'items')" :columns="ITEM_COLUMNS" />
              <ReportTable
                label="Equipment"
                :rows="rows(node, 'equipment_details')"
                :columns="EQUIPMENT_COLUMNS"
              />

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
                  <RichContent class="rep-field-value rep-rich" :value="node.methodology_comments" />
                </div>
              </template>

              <!-- PROTOCOL STEPS. The run's own numbered step list, which is
                   where a step's attachment lives - printed as a thumbnail that
                   opens full size, same as everywhere else. -->
              <ReportTable
                label="Protocol Steps"
                :rows="rows(node, 'protocol_steps')"
                :columns="PROTOCOL_STEP_COLUMNS"
              />

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
                            <RichContent
                              v-if="col.rich && hasText(row[col.key], true)"
                              class="rep-rich"
                              :value="row[col.key]"
                            />
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
                <RichContent class="rep-field-value rep-rich" :value="node.observation_comments" />
              </div>
              </template>

              <!-- The measured output of the run. Two separate grids on the
                   doctype, kept separate here. -->
              <ReportTable
                label="Quality Metrics"
                :rows="rows(node, 'quality_metrics')"
                :columns="METRIC_COLUMNS"
              />
              <ReportTable
                label="Sub Experiment Metrics"
                :rows="rows(node, 'sub_metrics')"
                :columns="METRIC_COLUMNS"
              />
              <ReportTable label="Samples" :rows="rows(node, 'sample')" :columns="SAMPLE_COLUMNS" />

              <!-- RESULT. The doctype's whole Result tab, which the report did
                   not carry at all - a Master Experiment that had been written
                   up showed its aim and its conclusion and nothing of what it
                   found. Gated as one section, like Methodology and Observation:
                   any one part justifies the heading. -->
              <template v-if="showsResult(node)">
                <div v-if="hasText(node.result)" class="rep-field">
                  <span class="rep-field-label">Result</span>
                  <p class="rep-field-value">
                    <span class="rep-result" :class="resultClass(node.result)">{{ node.result }}</span>
                  </p>
                </div>

                <div v-if="hasText(node.results, true)" class="rep-field">
                  <span class="rep-field-label">Results</span>
                  <RichContent class="rep-field-value rep-rich" :value="node.results" />
                </div>

                <ReportTable
                  label="Result Attachments"
                  :rows="rows(node, 'result_attachment')"
                  :columns="RESULT_ATTACHMENT_COLUMNS"
                />

                <div v-if="hasText(node.observation_and_conclusion, true)" class="rep-field">
                  <span class="rep-field-label">Observation &amp; Conclusion</span>
                  <RichContent class="rep-field-value rep-rich" :value="node.observation_and_conclusion" />
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
                <RichContent class="rep-field-value rep-rich" :value="node.conclusion" />
              </div>

              <!-- How the science came out, as opposed to where the paperwork
                   got to - the workflow state is already on the card header. -->
              <div v-if="hasText(node.experiment_status)" class="rep-field">
                <span class="rep-field-label">Experiment Status</span>
                <p class="rep-field-value">
                  {{ node.experiment_status }}
                  <span v-if="node.is_successful" class="rep-result rep-result-pass">Successful</span>
                </p>
              </div>
            </div>
          </div>
        </section>
      </div>
    </template>

    <div v-else class="rep-alert">Could not load the report for this run.</div>
  </div>
</template>
