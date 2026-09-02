<script setup>

import FileAttachment from '../common/FileAttachment.vue'
import RichContent from '../common/RichContent.vue'
import { richHasContent } from '../../utils/richText'

defineProps({
  label: { type: String, required: true },
  rows: { type: Array, default: () => [] },

  columns: { type: Array, required: true },
})


const hasText = (value, rich = false) => {
  if (value === null || value === undefined) return false
  if (rich) return richHasContent(String(value))
  return String(value).trim() !== ''
}
</script>

<template>
  <div v-if="rows.length" class="rep-field">
    <span class="rep-field-label">{{ label }}</span>
    <div class="rep-table-wrap">
      <table class="rep-table">
        <thead>
          <tr>
            <th class="rep-table-idx">#</th>
            <th v-for="col in columns" :key="col.key">{{ col.label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.idx">
            <td class="rep-table-idx">{{ row.idx }}</td>
            <td v-for="col in columns" :key="col.key">
              <!-- A Check is 0 or 1, and 0 is a real answer rather than a blank,
                   so it is tested before the emptiness check below. -->
              <template v-if="col.check">
                {{ row[col.key] ? 'Yes' : 'No' }}
              </template>

              <!-- Read-only: the report never edits. FileAttachment in this mode
                   is a thumbnail that opens full size, or a named link. -->
              <FileAttachment
                v-else-if="col.attach"
                :model-value="row[col.key] || ''"
                disabled
              />

              <RichContent
                v-else-if="col.rich && hasText(row[col.key], true)"
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
</template>
