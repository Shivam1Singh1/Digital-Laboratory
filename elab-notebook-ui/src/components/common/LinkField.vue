<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import axios from 'axios'

const props = defineProps({
  modelValue: { type: [String, Number], default: '' },
  doctype: { type: String, default: '' },

  fields: { type: Array, default: () => [] },

  searchFields: { type: Array, default: () => ['name'] },

  descriptionField: { type: String, default: '' },
  filters: { type: Array, default: () => [] },
  placeholder: { type: String, default: 'Search...' },
  disabled: { type: Boolean, default: false },


  searchFn: { type: Function, default: null },
  emptyHint: { type: String, default: 'No matches found' },
  inputClass: { type: String, default: 'form-control' },
  clearable: { type: Boolean, default: true },


  keepTypedText: { type: Boolean, default: false }
})


const emit = defineEmits(['update:modelValue', 'select', 'search'])

const query = ref(props.modelValue ? String(props.modelValue) : '')
const options = ref([])
const open = ref(false)
const loading = ref(false)
const highlighted = ref(-1)
const inputElement = ref(null)
const dropdownStyle = ref({})

let debounceTimer = null
let blurTimer = null

let requestSeq = 0

const updateDropdownPosition = () => {
  if (!inputElement.value || !open.value) return

  const rect = inputElement.value.getBoundingClientRect()
  dropdownStyle.value = {
    position: 'fixed',
    top: (rect.bottom + 4) + 'px',
    left: rect.left + 'px',
    width: Math.max(rect.width, 350) + 'px',
    zIndex: 9999
  }
}

watch(open, () => {
  if (open.value) {
    setTimeout(updateDropdownPosition, 0)
    window.addEventListener('scroll', updateDropdownPosition)
  } else {
    window.removeEventListener('scroll', updateDropdownPosition)
  }
})

watch(
  () => props.modelValue,
  (val) => {
    const next = val ? String(val) : ''
    if (next !== query.value) query.value = next
  }
)

const defaultSearch = async (txt) => {
  if (!props.doctype) return []

  const params = {
    doctype: props.doctype,
    fields: JSON.stringify([...new Set(['name', ...props.fields])]),
    limit_page_length: 10
  }
  if (props.filters.length) params.filters = JSON.stringify(props.filters)
  if (txt) {
    params.or_filters = JSON.stringify(
      props.searchFields.map((f) => [f, 'like', `%${txt}%`])
    )
  }

  const res = await axios.get('/api/method/frappe.client.get_list', { params })
  return res.data.message || []
}

const runSearch = () => {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(async () => {
    if (props.disabled) return
    const seq = ++requestSeq
    loading.value = true
    try {
      const result = await (props.searchFn || defaultSearch)(query.value)
      if (seq !== requestSeq) return
      options.value = result || []
      highlighted.value = options.value.length ? 0 : -1
    } catch (err) {
      if (seq === requestSeq) {
        console.error(`Link search failed for ${props.doctype}`, err)
        options.value = []
      }
    } finally {
      if (seq === requestSeq) loading.value = false
    }
  }, 250)
}

const onFocus = () => {
  if (props.disabled) return
  clearTimeout(blurTimer)

  document.querySelectorAll('.link-dropdown').forEach(el => {
    el.style.display = 'none'
  })
  open.value = true
  runSearch()
}

const onInput = () => {
  open.value = true
  emit('search', query.value)
  runSearch()
}

const onBlur = () => {

  blurTimer = setTimeout(() => {
    open.value = false


    if (props.keepTypedText) return
    query.value = props.modelValue ? String(props.modelValue) : ''
  }, 150)
}

const pick = (opt) => {
  clearTimeout(blurTimer)
  query.value = opt.name
  open.value = false
  emit('update:modelValue', opt.name)
  emit('select', opt)
}

const clear = () => {
  query.value = ''
  options.value = []
  emit('update:modelValue', '')
  emit('select', null)
}

const onKeydown = (e) => {
  if (!open.value) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    highlighted.value = Math.min(highlighted.value + 1, options.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    highlighted.value = Math.max(highlighted.value - 1, 0)
  } else if (e.key === 'Enter') {
    if (highlighted.value >= 0 && options.value[highlighted.value]) {
      e.preventDefault()
      pick(options.value[highlighted.value])
    }
  } else if (e.key === 'Escape') {
    open.value = false
  }
}

onBeforeUnmount(() => {
  clearTimeout(debounceTimer)
  clearTimeout(blurTimer)
})
</script>

<template>
  <div class="link-field">
    <input
      ref="inputElement"
      type="text"
      :class="inputClass"
      :value="query"
      :placeholder="placeholder"
      :disabled="disabled"
      autocomplete="off"
      @input="query = $event.target.value; onInput()"
      @focus="onFocus"
      @blur="onBlur"
      @keydown="onKeydown"
    />
    <button
      v-if="modelValue && !disabled && clearable"
      type="button"
      class="link-clear-btn"
      title="Clear"
      @mousedown.prevent="clear"
    >×</button>

    <Teleport to="body" v-if="open">
      <ul class="link-dropdown" :style="dropdownStyle">
        <li v-if="loading" class="link-option link-option-muted">Searching…</li>
        <template v-else>
          <li
            v-for="(opt, idx) in options"
            :key="opt.name"
            class="link-option"
            :class="{ highlighted: idx === highlighted }"
            @mousedown.prevent="pick(opt)"
            @mouseenter="highlighted = idx"
          >
            <span class="link-option-name">{{ opt.name }}</span>
            <span v-if="descriptionField && opt[descriptionField]" class="link-option-desc">
              {{ opt[descriptionField] }}
            </span>
          </li>
          <li v-if="!options.length" class="link-option link-option-muted">{{ emptyHint }}</li>
        </template>
      </ul>
    </Teleport>
  </div>
</template>
