<script setup>
import { ref, watch, onMounted } from 'vue'

// Backs a Frappe "Text Editor" field, which stores HTML. Deliberately
// dependency-free: a contenteditable surface with a minimal toolbar rather than
// pulling a full editor bundle into the app.
const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  minHeight: { type: String, default: '120px' }
})

const emit = defineEmits(['update:modelValue'])

const editor = ref(null)

const TOOLS = [
  { cmd: 'bold', label: 'B', title: 'Bold', class: 'tool-bold' },
  { cmd: 'italic', label: 'I', title: 'Italic', class: 'tool-italic' },
  { cmd: 'underline', label: 'U', title: 'Underline', class: 'tool-underline' },
  { cmd: 'insertUnorderedList', label: '• List', title: 'Bulleted list' },
  { cmd: 'insertOrderedList', label: '1. List', title: 'Numbered list' }
]

const exec = (cmd) => {
  editor.value?.focus()
  document.execCommand(cmd, false, null)
  emit('update:modelValue', editor.value?.innerHTML || '')
}

const onInput = () => {
  emit('update:modelValue', editor.value?.innerHTML || '')
}

// Writing innerHTML on every keystroke would reset the caret to the start, so
// only push in values that came from somewhere other than this editor.
watch(
  () => props.modelValue,
  (val) => {
    if (editor.value && (val || '') !== editor.value.innerHTML) {
      editor.value.innerHTML = val || ''
    }
  }
)

onMounted(() => {
  if (editor.value) editor.value.innerHTML = props.modelValue || ''
})
</script>

<template>
  <div class="rich-text">
    <div class="rich-text-toolbar">
      <button
        v-for="tool in TOOLS"
        :key="tool.cmd"
        type="button"
        class="rich-text-tool"
        :class="tool.class"
        :title="tool.title"
        @mousedown.prevent="exec(tool.cmd)"
      >{{ tool.label }}</button>
    </div>
    <div
      ref="editor"
      class="rich-text-surface"
      contenteditable="true"
      :data-placeholder="placeholder"
      :style="{ minHeight }"
      @input="onInput"
    ></div>
  </div>
</template>
