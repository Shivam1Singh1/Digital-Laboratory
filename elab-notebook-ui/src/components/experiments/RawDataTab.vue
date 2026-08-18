<script setup>
/**
 * The Lab Experiment "Raw Data" tab, shared by the create form and the detail
 * page so the two cannot drift.
 *
 * Field order, labels and per-field visibility come from the doctype's own
 * `attachments_tab` section - see utils/rawData.js for the depends_on
 * expressions this mirrors. Nothing here decides what a field means; it decides
 * how it is typed into.
 *
 * `experiment` is mutated in place rather than emitted back: both callers own a
 * single reactive run object that they post whole, and threading twenty fields
 * through v-model would only give the parents twenty things to forward.
 */
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import RichTextEditor from '../common/RichTextEditor.vue'
import { showsNatureOfSample, showsQualityMetrics } from '../../utils/rawData'
import './RawDataTab.css'

const props = defineProps({
  experiment: { type: Object, required: true },
  readonly: { type: Boolean, default: false },
})

const showNature = computed(() => showsNatureOfSample(props.experiment.experiment_category))
const showMetrics = computed(() => showsQualityMetrics(props.experiment.nature_of_sample))

// Link targets. Small, closed lists, so they load once and render as selects
// rather than as another search widget.
const natureOptions = ref([])
const parameterOptions = ref([])
// Open-ended ones stay text inputs backed by a datalist: Item and Warehouse run
// to thousands of rows on this site, and a select would have to load all of
// them to be honest about what is pickable.
const itemOptions = ref([])
const warehouseOptions = ref([])
const employeeOptions = ref([])

const loadOptions = async (doctype, target, extra = {}) => {
  try {
    const res = await axios.get('/api/method/frappe.client.get_list', {
      params: {
        doctype,
        fields: JSON.stringify(['name']),
        limit_page_length: 0,
        ...extra,
      },
    })
    target.value = (res.data.message || []).map((r) => r.name)
  } catch (err) {
    // A missing option list must not take the tab down with it - the field
    // stays typeable, it just loses its suggestions.
    console.error(`Failed to load ${doctype} options:`, err)
    target.value = []
  }
}

onMounted(() => {
  loadOptions('Nature of sample', natureOptions)
  loadOptions('Parameter', parameterOptions)
  loadOptions('Item', itemOptions, { limit_page_length: 500 })
  loadOptions('Warehouse', warehouseOptions, { limit_page_length: 500 })
  loadOptions('Employee', employeeOptions, { limit_page_length: 500 })
})

// Child tables arrive absent on a new run and as arrays on a saved one; the
// grids below write into them either way.
const rows = (fieldname) => {
  if (!Array.isArray(props.experiment[fieldname])) props.experiment[fieldname] = []
  return props.experiment[fieldname]
}

const addRow = (fieldname, blank) => rows(fieldname).push({ ...blank })
const removeRow = (fieldname, index) => rows(fieldname).splice(index, 1)

const BLANK_ATTACHMENT = { name1: '', file: '' }
const BLANK_METRIC = { quality_metrics: '', value: '', unit: '' }
const BLANK_SAMPLE = {
  sample_id: '', sample: '', sample_name: '', batch_no: '', warehouse: '',
  sample_vol: '', sample_detailsstage: '', remarks: '', item: '', qty: '',
  uom: '', attach: '', transfered_to: '', sampling_date: '', date_of_analysis: '',
  results: '',
}

// Mirrors the doctype's fetch_from on uom (item.stock_uom). Frappe fills it
// server-side on save either way; doing it here means the row does not sit
// blank until then.
const onSampleItem = async (row) => {
  if (!row.item) {
    row.uom = ''
    return
  }
  try {
    const res = await axios.get('/api/method/frappe.client.get_value', {
      params: { doctype: 'Item', filters: JSON.stringify({ name: row.item }), fieldname: 'stock_uom' },
    })
    row.uom = res.data.message?.stock_uom || ''
  } catch (err) {
    console.error('Failed to fetch stock UOM:', err)
  }
}
</script>

<template>
  <div class="raw-data-pane">
    <!-- Result attachment ------------------------------------------------ -->
    <div class="rd-block">
      <div class="rd-block-head">
        <h3 class="rd-block-title">Result Attachment</h3>
        <button v-if="!readonly" class="btn btn-secondary btn-sm" @click="addRow('result_attachment', BLANK_ATTACHMENT)">
          + Add Row
        </button>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th class="rd-num">No.</th>
              <th>Name</th>
              <th>File</th>
              <th v-if="!readonly" class="actions-col"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in rows('result_attachment')" :key="i">
              <td class="rd-num">{{ i + 1 }}</td>
              <td><input v-model="row.name1" type="text" class="form-control table-input" :readonly="readonly" /></td>
              <td><input v-model="row.file" type="text" class="form-control table-input" placeholder="/files/…" :readonly="readonly" /></td>
              <td v-if="!readonly" class="actions-col">
                <button class="rd-remove" title="Remove row" @click="removeRow('result_attachment', i)">×</button>
              </td>
            </tr>
            <tr v-if="!rows('result_attachment').length">
              <td :colspan="readonly ? 3 : 4" class="rd-empty">No attachments yet.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Sample details --------------------------------------------------- -->
    <div class="form-group">
      <label class="form-label">Sample details</label>
      <textarea v-model="experiment.sample_details" class="form-control" rows="3" :readonly="readonly"></textarea>
    </div>

    <div class="form-group">
      <label class="form-label">Sample details(generated)</label>
      <RichTextEditor v-model="experiment.sample_detailsgenerated" placeholder="Generated sample details…" :readonly="readonly" />
    </div>

    <div class="form-group-row two-columns">
      <label class="rd-check">
        <input v-model="experiment.sample_generated" type="checkbox" :true-value="1" :false-value="0" :disabled="readonly" />
        Sample Generated
      </label>
      <label class="rd-check">
        <input v-model="experiment.sample_not_generated" type="checkbox" :true-value="1" :false-value="0" :disabled="readonly" />
        Sample Not Generated
      </label>
    </div>

    <!-- section_break_kogm: the two-column batch block ------------------- -->
    <div class="rd-section">
      <div class="form-group-row two-columns">
        <div class="form-group">
          <label class="form-label">TRF No.</label>
          <input v-model="experiment.trf_no" type="text" class="form-control" :readonly="readonly" />
        </div>
        <div class="form-group">
          <label class="form-label">Batch Volume</label>
          <input v-model="experiment.batch_volume" type="text" class="form-control" :readonly="readonly" />
        </div>
      </div>
      <div class="form-group-row two-columns">
        <div class="form-group">
          <label class="form-label">Batch Manufacturing Date</label>
          <input v-model="experiment.batch_manufacturing_date" type="date" class="form-control" :readonly="readonly" />
        </div>
        <div class="form-group">
          <label class="form-label">Batch No.</label>
          <input v-model="experiment.batch_no" type="text" class="form-control" :readonly="readonly" />
        </div>
      </div>
      <div class="form-group-row two-columns">
        <div class="form-group">
          <!-- Labelled "Date" on the doctype; the fieldname is handover_date and
               that is what it means, so the hint says so rather than leaving a
               bare "Date" between two batch fields. -->
          <label class="form-label">Date</label>
          <input v-model="experiment.handover_date" type="date" class="form-control" :readonly="readonly" />
          <span class="field-hint">Handover date.</span>
        </div>
        <div class="form-group">
          <label class="form-label">Storage Condition</label>
          <input v-model="experiment.storage_condition" type="text" class="form-control" :readonly="readonly" />
        </div>
      </div>
      <div class="form-group-row two-columns">
        <div class="form-group">
          <label class="form-label">Project Code (sample)</label>
          <input v-model="experiment.project_code_sample" type="text" class="form-control" :readonly="readonly" />
        </div>
        <!-- Hidden on a Sub Sub Experiment - see utils/rawData.js. -->
        <div v-if="showNature" class="form-group">
          <label class="form-label">Nature of Sample</label>
          <select v-model="experiment.nature_of_sample" class="form-control" :disabled="readonly">
            <option value="">Select…</option>
            <option v-for="n in natureOptions" :key="n" :value="n">{{ n }}</option>
          </select>
        </div>
      </div>
    </div>

    <!-- section_break_aqhn: Quality Metrics, shown once a nature is named -->
    <div v-if="showMetrics" class="rd-block">
      <div class="rd-block-head">
        <h3 class="rd-block-title">Quality Metrics</h3>
        <button v-if="!readonly" class="btn btn-secondary btn-sm" @click="addRow('quality_metrics', BLANK_METRIC)">
          + Add Row
        </button>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th class="rd-num">No.</th>
              <th>Quality Metrics</th>
              <th>Value</th>
              <th>Unit</th>
              <th v-if="!readonly" class="actions-col"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in rows('quality_metrics')" :key="i">
              <td class="rd-num">{{ i + 1 }}</td>
              <td>
                <select v-model="row.quality_metrics" class="form-control table-input" :disabled="readonly">
                  <option value="">Select…</option>
                  <option v-for="p in parameterOptions" :key="p" :value="p">{{ p }}</option>
                </select>
              </td>
              <td><input v-model="row.value" type="text" class="form-control table-input" :readonly="readonly" /></td>
              <td><input v-model="row.unit" type="text" class="form-control table-input" :readonly="readonly" /></td>
              <td v-if="!readonly" class="actions-col">
                <button class="rd-remove" title="Remove row" @click="removeRow('quality_metrics', i)">×</button>
              </td>
            </tr>
            <tr v-if="!rows('quality_metrics').length">
              <td :colspan="readonly ? 4 : 5" class="rd-empty">No metrics recorded yet.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- section_break_vwvz: Sample ------------------------------------- -->
    <div class="rd-block">
      <div class="rd-block-head">
        <h3 class="rd-block-title">Sample</h3>
        <button v-if="!readonly" class="btn btn-secondary btn-sm" @click="addRow('sample', BLANK_SAMPLE)">
          + Add Row
        </button>
      </div>
      <!-- Sixteen columns: wider than the pane, so the container scrolls
           sideways rather than the row wrapping into an unreadable block. -->
      <div class="table-container rd-wide">
        <table>
          <thead>
            <tr>
              <th class="rd-num">No.</th>
              <th>Sample ID</th>
              <th>Sample</th>
              <th>Sample Name</th>
              <th>Batch no.</th>
              <th>Warehouse</th>
              <th>Sample Vol</th>
              <th>Sample Details/Stage</th>
              <th>Remarks</th>
              <th>Item</th>
              <th>Qty</th>
              <th>UOM</th>
              <th>Attach</th>
              <th>Transfered To</th>
              <th>Sampling Date</th>
              <th>Date of Analysis</th>
              <th>Results</th>
              <th v-if="!readonly" class="actions-col"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in rows('sample')" :key="i">
              <td class="rd-num">{{ i + 1 }}</td>
              <td><input v-model="row.sample_id" type="text" class="form-control table-input" :readonly="readonly" /></td>
              <td><input v-model="row.sample" type="text" class="form-control table-input" :readonly="readonly" /></td>
              <td><input v-model="row.sample_name" type="text" class="form-control table-input" :readonly="readonly" /></td>
              <td><input v-model="row.batch_no" type="text" class="form-control table-input" :readonly="readonly" /></td>
              <td>
                <input v-model="row.warehouse" type="text" list="rd-warehouses" class="form-control table-input" :readonly="readonly" />
              </td>
              <td>
                <input v-model="row.sample_vol" type="text" class="form-control table-input" placeholder="(μl) X Vials" :readonly="readonly" />
              </td>
              <td><input v-model="row.sample_detailsstage" type="text" class="form-control table-input" :readonly="readonly" /></td>
              <td><input v-model="row.remarks" type="text" class="form-control table-input" :readonly="readonly" /></td>
              <td>
                <input v-model="row.item" type="text" list="rd-items" class="form-control table-input" :readonly="readonly" @change="onSampleItem(row)" />
              </td>
              <td><input v-model="row.qty" type="text" class="form-control table-input" :readonly="readonly" /></td>
              <!-- Fetched from the Item, like the doctype's fetch_from. -->
              <td><input v-model="row.uom" type="text" class="form-control table-input readonly" readonly /></td>
              <td><input v-model="row.attach" type="text" class="form-control table-input" placeholder="/files/…" :readonly="readonly" /></td>
              <td>
                <input v-model="row.transfered_to" type="text" list="rd-employees" class="form-control table-input" :readonly="readonly" />
              </td>
              <td><input v-model="row.sampling_date" type="date" class="form-control table-input" :readonly="readonly" /></td>
              <td><input v-model="row.date_of_analysis" type="date" class="form-control table-input" :readonly="readonly" /></td>
              <td><input v-model="row.results" type="text" class="form-control table-input" :readonly="readonly" /></td>
              <td v-if="!readonly" class="actions-col">
                <button class="rd-remove" title="Remove row" @click="removeRow('sample', i)">×</button>
              </td>
            </tr>
            <tr v-if="!rows('sample').length">
              <td :colspan="readonly ? 17 : 18" class="rd-empty">No samples recorded yet.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- One datalist per open-ended Link, shared by every row of the grid. -->
    <datalist id="rd-items"><option v-for="o in itemOptions" :key="o" :value="o" /></datalist>
    <datalist id="rd-warehouses"><option v-for="o in warehouseOptions" :key="o" :value="o" /></datalist>
    <datalist id="rd-employees"><option v-for="o in employeeOptions" :key="o" :value="o" /></datalist>
  </div>
</template>
