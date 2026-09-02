<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'

import { splitStored, joinStored } from '../../utils/richText'
import './RichTextEditor.css'


const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  minHeight: { type: String, default: '120px' },


  readonly: { type: Boolean, default: false },

  tables: { type: Boolean, default: false }
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
  if (props.readonly) return
  editor.value?.focus()
  document.execCommand(cmd, false, null)
  emit('update:modelValue', editor.value?.innerHTML || '')
}

const onInput = () => {
  if (props.readonly) return
  emit('update:modelValue', editor.value?.innerHTML || '')
}


const quillHost = ref(null)
const quillLoading = ref(false)
const quillError = ref('')
let quill = null


let applyingExternal = false


const toolbarId = `rte-toolbar-${Math.random().toString(36).slice(2, 9)}`

const FONT_SIZES = ['12px', '14px', '16px', '18px', '24px', '32px']


const attachments = ref([])


const emitCombined = () => {
  const body = quill ? quill.root.innerHTML : ''
  emit('update:modelValue', joinStored(body, attachments.value))
}

const removeAttachment = (idx) => {
  if (props.readonly) return
  attachments.value.splice(idx, 1)
  emitCombined()
}

const loadQuill = async () => {
  quillLoading.value = true
  quillError.value = ''
  try {


    const [{ default: Quill }, qbtModule] = await Promise.all([
      import('quill'),
      import('quill-better-table'),
      import('quill/dist/quill.snow.css'),
      import('quill-better-table/dist/quill-better-table.css')
    ])
    const QuillBetterTable = qbtModule.default ?? qbtModule


    const SizeStyle = Quill.import('attributors/style/size')
    SizeStyle.whitelist = FONT_SIZES
    Quill.register(SizeStyle, true)


    Quill.register(Quill.import('attributors/style/color'), true)
    Quill.register(Quill.import('attributors/style/background'), true)


    Quill.register({ 'modules/better-table': QuillBetterTable }, true)

    await nextTick()
    if (!quillHost.value) return

    quill = new Quill(quillHost.value, {
      theme: 'snow',
      readOnly: props.readonly,
      placeholder: props.placeholder,
      modules: {


        table: false,
        'better-table': {
          operationMenu: {
            items: {
              unmergeCells: { text: 'Unmerge cells' }
            }
          }
        },


        keyboard: { bindings: QuillBetterTable.keyboardBindings },
        toolbar: {
          container: `#${toolbarId}`,
          handlers: {
            'better-table': insertTable,
            'table-menu': openTableMenu,
            attach: attachFile,


            ...Object.fromEntries(ARMABLE_FORMATS.map((n) => [n, armableHandler(n)]))
          }
        }
      }
    })

    const initial = splitStored(props.modelValue)
    attachments.value = initial.files
    applyingExternal = true
    quill.root.innerHTML = initial.body
    applyingExternal = false

    quill.on('text-change', () => {
      if (applyingExternal || props.readonly) return


      emitCombined()
    })


    window.addEventListener('scroll', dismissTableMenu, true)


    quill.root.addEventListener('click', onEditorClick, true)
    window.addEventListener('keydown', onLightboxKey)


    quill.root.addEventListener('mousemove', armResize)
    quill.root.addEventListener('mouseleave', disarmResize)
    quill.root.addEventListener('mousedown', startResize, true)


    quill.on('selection-change', refreshTableState)
    quill.on('text-change', refreshTableState)


    quill.on('text-change', reapplyArmedFormats)
    quill.on('selection-change', disarmFormats)


    editorWidget = quill.root.closest('.rich-text-quill')
    editorWidget?.addEventListener('focusout', onEditorFocusOut)
  } catch (err) {
    console.error('Failed to load the table editor', err)
    quillError.value = 'The table editor could not be loaded. Reload the page to try again.'
  } finally {
    quillLoading.value = false
  }
}


function dismissTableMenu() {
  document.querySelectorAll('.qlbt-operation-menu').forEach((el) => el.remove())
}

function insertTable() {
  if (props.readonly || !quill) return
  quill.getModule('better-table').insertTable(2, 3)


  nextTick(refreshTableState)
}


function currentCell() {
  const sel = window.getSelection()
  let node = sel && sel.anchorNode
  if (!node) return null
  if (node.nodeType === 3) node = node.parentNode
  while (node && node !== quill?.root) {
    if (node.tagName === 'TD') return node
    node = node.parentNode
  }
  return null
}

const inTable = ref(false)

function refreshTableState() {
  inTable.value = Boolean(currentCell())
}


function openTableMenu() {
  if (props.readonly || !quill) return
  const cell = currentCell()
  if (!cell) return
  const r = cell.getBoundingClientRect()
  cell.dispatchEvent(
    new MouseEvent('contextmenu', {
      bubbles: true,
      cancelable: true,
      composed: true,
      view: window,


      clientX: Math.round(r.left + 8),
      clientY: Math.round(r.top + 8)
    })
  )
}


const ARMABLE_FORMATS = ['bold', 'italic', 'underline', 'size']

let armedFormats = {}
let armedAt = -1


function rangeInTable(range) {
  if (!range) return false
  const formats = quill.getFormat(range)
  return formats.cell != null || formats.row != null
}

function armableHandler(name) {


  return (value) => {
    if (!quill) return
    const range = quill.getSelection(true)
    if (!range) return
    quill.format(name, value, 'user')
    if (range.length === 0 && rangeInTable(range)) {
      armedFormats = { ...armedFormats, [name]: value }
      armedAt = range.index
    }
  }
}


function insertionOf(delta) {
  let index = 0
  for (const op of delta.ops || []) {
    if (op.retain != null) {
      index += typeof op.retain === 'number' ? op.retain : 1
    } else if (op.insert != null) {
      return { index, length: typeof op.insert === 'string' ? op.insert.length : 1 }
    } else {
      return null
    }
  }
  return null
}

function reapplyArmedFormats(delta, oldDelta, source) {
  if (armedAt < 0 || source !== 'user') return
  const inserted = insertionOf(delta)


  if (!inserted) return
  if (inserted.index !== armedAt) {
    armedFormats = {}
    armedAt = -1
    return
  }
  const formats = armedFormats


  armedFormats = {}
  armedAt = -1
  quill.formatText(inserted.index, inserted.length, formats, 'user')
  quill.setSelection(inserted.index + inserted.length, 0, 'silent')
}

function disarmFormats(range) {
  if (armedAt < 0) return
  if (!range || range.index !== armedAt) {
    armedFormats = {}
    armedAt = -1
  }
}


const RESIZE_GRAB = 5
const MIN_COL_WIDTH = 40
const MIN_ROW_HEIGHT = 24


let armedResize = null
let activeResize = null


function colNodeFor(cell) {
  const table = cell.closest('table')
  const cols = table ? table.querySelectorAll('colgroup > col') : []
  if (!cols.length) return null
  let index = 0
  for (const sibling of cell.parentNode.children) {
    if (sibling === cell) break
    index += parseInt(sibling.getAttribute('colspan'), 10) || 1
  }
  index += (parseInt(cell.getAttribute('colspan'), 10) || 1) - 1
  return cols[index] || null
}


function borderUnder(cell, evt) {
  const r = cell.getBoundingClientRect()
  const row = cell.parentNode
  if (r.right - evt.clientX <= RESIZE_GRAB) return { type: 'col', cell }
  if (evt.clientX - r.left <= RESIZE_GRAB && cell.previousElementSibling) {
    return { type: 'col', cell: cell.previousElementSibling }
  }
  if (r.bottom - evt.clientY <= RESIZE_GRAB) return { type: 'row', row }
  if (evt.clientY - r.top <= RESIZE_GRAB && row.previousElementSibling) {
    return { type: 'row', row: row.previousElementSibling }
  }
  return null
}


let resizeGuide = null
let resizeReadout = null


function showGuide(type, anchor, readout = '') {
  if (!quill) return
  const table = anchor.closest('table')
  if (!table) return
  const parent = quill.root.parentNode
  if (!resizeGuide) {
    resizeGuide = document.createElement('div')
    resizeGuide.className = 'rte-resize-guide'
    resizeReadout = document.createElement('span')
    resizeReadout.className = 'rte-resize-readout'
    resizeGuide.appendChild(resizeReadout)
    parent.appendChild(resizeGuide)
  }
  resizeGuide.classList.toggle('is-col', type === 'col')
  resizeGuide.classList.toggle('is-row', type === 'row')
  resizeReadout.textContent = readout


  const base = parent.getBoundingClientRect()
  const t = table.getBoundingClientRect()
  const a = anchor.getBoundingClientRect()
  const style =
    type === 'col'
      ? {
          left: `${a.right - base.left + parent.scrollLeft - 1}px`,
          top: `${t.top - base.top + parent.scrollTop}px`,
          width: '2px',
          height: `${t.height}px`
        }
      : {
          left: `${t.left - base.left + parent.scrollLeft}px`,
          top: `${a.bottom - base.top + parent.scrollTop - 1}px`,
          width: `${t.width}px`,
          height: '2px'
        }
  Object.assign(resizeGuide.style, style, { display: 'block' })
}

function hideGuide() {
  if (resizeGuide) resizeGuide.style.display = 'none'
}


function setResizeCursor(type) {
  if (!quill) return
  quill.root.classList.toggle('rte-col-resize', type === 'col')
  quill.root.classList.toggle('rte-row-resize', type === 'row')
}

function armResize(evt) {
  if (props.readonly || activeResize || evt.buttons) return
  const cell = evt.target?.closest?.('td')
  armedResize = cell ? borderUnder(cell, evt) : null
  setResizeCursor(armedResize?.type)
  if (armedResize) showGuide(armedResize.type, armedResize.cell || armedResize.row)
  else hideGuide()
}

function disarmResize() {
  if (activeResize) return
  armedResize = null
  hideGuide()
  setResizeCursor(null)
}


function startResize(evt) {
  if (props.readonly || !armedResize || evt.button !== 0) return
  const target =
    armedResize.type === 'col' ? colNodeFor(armedResize.cell) : armedResize.row
  if (!target) return
  evt.preventDefault()
  evt.stopPropagation()

  activeResize = {
    type: armedResize.type,
    target,


    anchor: armedResize.cell || armedResize.row,
    origin: armedResize.type === 'col' ? evt.clientX : evt.clientY,


    start:
      armedResize.type === 'col'
        ? parseInt(target.getAttribute('width'), 10) ||
          Math.round(armedResize.cell.getBoundingClientRect().width)
        : Math.round(target.getBoundingClientRect().height),
    applied: null
  }
  window.addEventListener('mousemove', onResizeMove, true)
  window.addEventListener('mouseup', endResize, true)
}

function onResizeMove(evt) {
  if (!activeResize) return
  const { type, target, origin, start } = activeResize
  if (type === 'col') {
    const width = Math.max(MIN_COL_WIDTH, start + evt.clientX - origin)
    target.setAttribute('width', width)
    activeResize.applied = width
  } else {


    const height = Math.max(MIN_ROW_HEIGHT, start + evt.clientY - origin)
    target.style.height = `${height}px`
    activeResize.applied = height
  }


  const delta = activeResize.applied - start
  const arrows = type === 'col' ? ['←', '↔', '→'] : ['↑', '↕', '↓']
  const arrow = arrows[Math.sign(delta) + 1]


  const label = type === 'col' ? 'Width' : 'Height'
  showGuide(type, activeResize.anchor, `${arrow} ${label}: ${activeResize.applied} pixels`)
}

function endResize() {
  window.removeEventListener('mousemove', onResizeMove, true)
  window.removeEventListener('mouseup', endResize, true)
  editorWidget?.removeEventListener('focusout', onEditorFocusOut)
  editorWidget = null
  resizeGuide?.remove()
  resizeGuide = null
  resizeReadout = null
  const finished = activeResize
  activeResize = null
  armedResize = null
  hideGuide()
  setResizeCursor(null)

  if (finished && finished.applied !== null) emitCombined()
}


async function attachFile() {
  if (props.readonly || !quill) return

  const input = document.createElement('input')
  input.type = 'file'
  input.addEventListener('change', async () => {
    const file = input.files && input.files[0]
    if (!file) return


    const range = quill.getSelection(true)
    const at = range ? range.index : quill.getLength()

    const form = new FormData()
    form.append('file', file, file.name)
    form.append('is_private', '1')

    try {
      const res = await fetch('/api/method/upload_file', {
        method: 'POST',
        body: form,

        credentials: 'same-origin',
        headers: { 'X-Frappe-CSRF-Token': window.csrf_token || '' }
      })
      const data = await res.json()
      const url = data?.message?.file_url
      if (!url) throw new Error(data?.message || 'no file_url in response')

      if ((file.type || '').startsWith('image/')) {
        quill.insertEmbed(at, 'image', url, 'user')
        quill.setSelection(at + 1, 0, 'user')

      } else {
        attachments.value.push({
          name: data.message.file_name || file.name,
          url,
          size: file.size
        })
        emitCombined()
      }
    } catch (err) {
      console.error('Attachment upload failed', err)
      quillError.value = `Could not attach ${file.name}.`
    }
  })
  input.click()
}


const lightboxSrc = ref('')

const onEditorClick = (evt) => {
  const img = evt.target
  if (!img || img.tagName !== 'IMG') return


  evt.preventDefault()
  evt.stopPropagation()
  lightboxSrc.value = img.getAttribute('src') || ''
}

const closeLightbox = () => {
  lightboxSrc.value = ''
}

const onLightboxKey = (evt) => {
  if (evt.key === 'Escape') closeLightbox()
}

const prettySize = (bytes) => {
  if (!bytes && bytes !== 0) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}


let pendingExternal = null
let editorWidget = null


function onEditorFocusOut(evt) {
  if (pendingExternal === null || !quill) return
  if (evt.relatedTarget && evt.currentTarget.contains(evt.relatedTarget)) return
  const val = pendingExternal
  pendingExternal = null
  if ((val || '') !== joinStored(quill.root.innerHTML, attachments.value)) {
    applyExternal(val)
  }
}

function applyExternal(val) {
  const next = splitStored(val)
  attachments.value = next.files
  applyingExternal = true
  quill.root.innerHTML = next.body
  applyingExternal = false
}

watch(
  () => props.modelValue,
  (val) => {
    if (props.tables) {
      if (!quill) return


      const current = joinStored(quill.root.innerHTML, attachments.value)
      if ((val || '') === current) return


      if (quill.hasFocus()) {
        pendingExternal = val
        return
      }
      applyExternal(val)
      return
    }
    if (editor.value && (val || '') !== editor.value.innerHTML) {
      editor.value.innerHTML = val || ''
    }
  }
)

watch(
  () => props.readonly,
  (ro) => {
    if (quill) quill.enable(!ro)
  }
)

onMounted(() => {
  if (props.tables) {
    loadQuill()
    return
  }
  if (editor.value) editor.value.innerHTML = props.modelValue || ''
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', dismissTableMenu, true)
  window.removeEventListener('keydown', onLightboxKey)
  if (quill) {
    quill.root.removeEventListener('click', onEditorClick, true)
    quill.root.removeEventListener('mousemove', armResize)
    quill.root.removeEventListener('mouseleave', disarmResize)
    quill.root.removeEventListener('mousedown', startResize, true)
  }


  window.removeEventListener('mousemove', onResizeMove, true)
  window.removeEventListener('mouseup', endResize, true)


  dismissTableMenu()
  quill = null
})
</script>

<template>
  <!-- Quill path -->
  <div v-if="tables" class="rich-text rich-text-quill" :class="{ 'rich-text-readonly': readonly }">
    <div v-if="quillError" class="rich-text-error">{{ quillError }}</div>

    <!-- Rendered even while loading so Quill has its container to attach to on
         the tick it becomes available. Hidden until then rather than absent. -->
    <div v-show="!readonly" :id="toolbarId" class="rich-text-quill-toolbar">
      <span class="ql-formats">
        <button class="ql-bold" type="button" title="Bold"></button>
        <button class="ql-italic" type="button" title="Italic"></button>
        <button class="ql-underline" type="button" title="Underline"></button>
      </span>
      <span class="ql-formats">
        <button class="ql-list" value="bullet" type="button" title="Bulleted list"></button>
        <button class="ql-list" value="ordered" type="button" title="Numbered list"></button>
      </span>
      <span class="ql-formats">
        <!-- Quill fills these from the registered attributor's whitelist. The
             blank first option is "default size", which is how a run of text
             gets its explicit font-size removed again. -->
        <select class="ql-size" title="Font size">
          <option selected></option>
          <option v-for="s in FONT_SIZES" :key="s" :value="s">{{ s }}</option>
        </select>
        <select class="ql-color" title="Text colour"></select>
        <select class="ql-background" title="Highlight colour"></select>
      </span>
      <span class="ql-formats">
        <!-- Named for the module so Quill routes it to the handler above.
             Inline SVG rather than emoji: emoji render at the platform's own
             size and colour, so they sat larger than Quill's own icons and
             ignored the toolbar tint. These inherit currentColor and line up. -->
        <button class="ql-better-table" type="button" title="Insert a 2×3 table">
          <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.6">
            <rect x="2.5" y="3.5" width="13" height="11" rx="1" />
            <line x1="2.5" y1="7" x2="15.5" y2="7" />
            <line x1="2.5" y1="11" x2="15.5" y2="11" />
            <line x1="7" y1="3.5" x2="7" y2="14.5" />
            <line x1="11" y1="3.5" x2="11" y2="14.5" />
          </svg>
        </button>
        <!-- Opens better-table's own operations menu: insert row/column either
             side, delete row/column/table, merge, unmerge. Right-clicking a
             cell does the same thing, but nothing on screen said so - this is
             the discoverable route to it. Disabled outside a table, so it never
             opens an empty menu. -->
        <button
          class="ql-table-menu"
          type="button"
          :disabled="!inTable"
          :title="inTable
            ? 'Table options — insert, delete, merge'
            : 'Put the cursor in a table to use this'"
        >
          <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.6"
               stroke-linecap="round">
            <rect x="2.5" y="3.5" width="13" height="11" rx="1" />
            <line x1="2.5" y1="7" x2="15.5" y2="7" />
            <line x1="7" y1="3.5" x2="7" y2="14.5" />
            <circle cx="11.6" cy="10.6" r="0.9" fill="currentColor" stroke="none" />
            <circle cx="13.9" cy="10.6" r="0.9" fill="currentColor" stroke="none" />
            <circle cx="9.3" cy="10.6" r="0.9" fill="currentColor" stroke="none" />
          </svg>
        </button>
        <button class="ql-attach" type="button" title="Attach a file or image">
          <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.6"
               stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 8.5 8.7 13.8a3 3 0 0 1-4.2-4.2l5.8-5.8a2 2 0 0 1 2.8 2.8l-5.8 5.8a1 1 0 0 1-1.4-1.4l5.3-5.3" />
          </svg>
        </button>
      </span>
    </div>

    <div v-if="quillLoading" class="rich-text-loading">Loading the editor…</div>
    <div ref="quillHost" class="rich-text-quill-host" :style="{ minHeight }"></div>

    <!-- Non-image attachments. Outside the Quill container on purpose: they are
         a property of the field, not part of the prose, and keeping them out
         means they cannot be half-deleted by a stray backspace. -->
    <div v-if="attachments.length" class="rte-attachments">
      <div class="rte-attachments-head">
        Attachments <span class="rte-attachments-count">{{ attachments.length }}</span>
      </div>
      <ul class="rte-attachments-list">
        <li v-for="(f, idx) in attachments" :key="`${f.url}-${idx}`" class="rte-attachment">
          <svg class="rte-attachment-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor"
               stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M9.5 1.5H4a1.5 1.5 0 0 0-1.5 1.5v10A1.5 1.5 0 0 0 4 14.5h8a1.5 1.5 0 0 0 1.5-1.5V5.5z" />
            <path d="M9.5 1.5v4h4" />
          </svg>
          <a :href="f.url" target="_blank" rel="noopener" class="rte-attachment-name">{{ f.name }}</a>
          <span v-if="f.size" class="rte-attachment-size">{{ prettySize(f.size) }}</span>
          <button
            v-if="!readonly"
            type="button"
            class="rte-attachment-remove"
            :title="`Remove ${f.name}`"
            @click="removeAttachment(idx)"
          >×</button>
        </li>
      </ul>
    </div>

    <!-- Full-size viewer. Teleported to body so it is not clipped by the tab
         pane's overflow and does not inherit the editor's stacking context -
         the same reason better-table's right-click menu lives there. -->
    <Teleport to="body">
      <div v-if="lightboxSrc" class="rte-lightbox" @click="closeLightbox">
        <!-- Stops a click on the picture itself from closing, so it can be
             pointed at without dismissing. -->
        <img :src="lightboxSrc" class="rte-lightbox-img" alt="" @click.stop />
        <button type="button" class="rte-lightbox-close" title="Close (Esc)" @click="closeLightbox">×</button>
      </div>
    </Teleport>
  </div>

  <!-- Original contenteditable path, untouched -->
  <div v-else class="rich-text" :class="{ 'rich-text-readonly': readonly }">
    <div v-if="!readonly" class="rich-text-toolbar">
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
      :contenteditable="readonly ? 'false' : 'true'"
      :data-placeholder="placeholder"
      :style="{ minHeight }"
      @input="onInput"
    ></div>
  </div>
</template>
