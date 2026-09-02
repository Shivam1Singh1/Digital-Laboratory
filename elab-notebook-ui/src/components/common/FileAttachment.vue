<script setup>

import { computed, ref } from 'vue'
import { fileUrl } from '../../utils/frappeUrl'
import { fileNameFromUrl, isImagePath } from '../../utils/attachment'
import ImageLightbox from './ImageLightbox.vue'

const props = defineProps({

  modelValue: { type: String, default: '' },


  disabled: { type: Boolean, default: false },
  label: { type: String, default: 'Attach' },


  name: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

const uploading = ref(false)
const uploadError = ref('')
const lightboxSrc = ref('')

const href = computed(() => fileUrl(props.modelValue))

const isImage = computed(() => isImagePath(props.name || props.modelValue))
const fileName = computed(() => props.name || fileNameFromUrl(props.modelValue))

async function pickFile() {
  if (props.disabled || uploading.value) return

  const input = document.createElement('input')
  input.type = 'file'
  input.addEventListener('change', async () => {
    const file = input.files && input.files[0]
    if (!file) return

    uploading.value = true
    uploadError.value = ''

    const form = new FormData()
    form.append('file', file, file.name)
    form.append('is_private', '1')

    try {
      const res = await fetch('/api/method/upload_file', {
        method: 'POST',
        body: form,

        credentials: 'same-origin',
        headers: { 'X-Frappe-CSRF-Token': window.csrf_token || '' },
      })
      const data = await res.json()
      const url = data?.message?.file_url
      if (!url) throw new Error(data?.message || 'no file_url in response')
      emit('update:modelValue', url)
    } catch (err) {
      console.error('Attachment upload failed', err)
      uploadError.value = `Could not attach ${file.name}.`
    } finally {
      uploading.value = false
    }
  })
  input.click()
}

const clear = () => {
  if (props.disabled) return
  uploadError.value = ''
  emit('update:modelValue', '')
}
</script>

<template>
  <div class="file-attach">
    <template v-if="modelValue">
      <button
        v-if="isImage"
        type="button"
        class="file-attach-thumb"
        :title="`Open ${fileName}`"
        @click="lightboxSrc = href"
      >
        <img :src="href" :alt="fileName" />
      </button>
      <svg
        v-else
        class="file-attach-icon"
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        stroke-width="1.4"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path d="M9.5 1.5H4a1.5 1.5 0 0 0-1.5 1.5v10A1.5 1.5 0 0 0 4 14.5h8a1.5 1.5 0 0 0 1.5-1.5V5.5z" />
        <path d="M9.5 1.5v4h4" />
      </svg>

      <a :href="href" target="_blank" rel="noopener" class="file-attach-name" :title="fileName">
        {{ fileName }}
      </a>

      <button
        v-if="!disabled"
        type="button"
        class="file-attach-remove"
        :title="`Remove ${fileName}`"
        @click="clear"
      >×</button>
    </template>

    <!-- Nothing attached and nothing to be done about it: a dash, so a locked
         row reads as empty rather than as a button that refuses to work. -->
    <span v-else-if="disabled" class="file-attach-blank">—</span>

    <button
      v-else
      type="button"
      class="file-attach-btn"
      :disabled="uploading"
      @click="pickFile"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
           stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
      </svg>
      <span>{{ uploading ? 'Uploading…' : label }}</span>
    </button>

    <p v-if="uploadError" class="file-attach-error">{{ uploadError }}</p>

    <ImageLightbox :src="lightboxSrc" @close="lightboxSrc = ''" />
  </div>
</template>
