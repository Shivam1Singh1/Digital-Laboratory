<script setup>

import { computed } from 'vue'
import { splitStored } from '../../utils/richText'
import FileAttachment from './FileAttachment.vue'

const props = defineProps({

  value: { type: String, default: '' },
})

const parsed = computed(() => splitStored(props.value))
const body = computed(() => parsed.value.body)
const files = computed(() => parsed.value.files)


const hasBody = computed(() => {
  const raw = body.value || ''
  const text = raw.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim()
  return text !== '' || /<(img|table)\b/i.test(raw)
})

const prettySize = (bytes) => {
  if (!bytes && bytes !== 0) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<template>
  <div>
    <!-- eslint-disable-next-line vue/no-v-html -->
    <div v-if="hasBody" v-html="body"></div>

    <!-- Not a <ul>: the host's own `.rep-rich :where(ul)` rule would indent and
         bullet this list as though a scientist had typed it. -->
    <div v-if="files.length" class="rich-files">
      <div class="rich-files-head">
        Attachments <span class="rich-files-count">{{ files.length }}</span>
      </div>
      <div v-for="(f, idx) in files" :key="`${f.url}-${idx}`" class="rich-file">
        <FileAttachment :model-value="f.url" :name="f.name" disabled />
        <span v-if="f.size" class="rich-file-size">{{ prettySize(f.size) }}</span>
      </div>
    </div>
  </div>
</template>
