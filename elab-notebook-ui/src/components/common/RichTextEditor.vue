<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'

import './RichTextEditor.css'

/**
 * Backs a Frappe "Text Editor" field, which stores HTML.
 *
 * Two implementations behind one interface, chosen by the `tables` prop:
 *
 *   tables=false (default) - the original dependency-free contenteditable
 *     surface. Every existing call site gets exactly this, unchanged.
 *
 *   tables=true - Quill 2 + quill-better-table, which adds real tables with
 *     merged cells, plus file attachment. Loaded by dynamic import so the
 *     ~300KB of editor never enters the main chunk for the pages that do not
 *     ask for it.
 *
 * WHY THE TWO ARE NOT INTERCHANGEABLE, and why `tables` is opt-in rather than
 * on by default: quill-better-table writes markup that a plain Quill 2 editor
 * destroys outright - fed to one, a table comes back as `<p><br></p>`. Frappe's
 * desk Text Editor is a plain Quill 2, so any field edited with tables=true must
 * be read_only on the doctype or the desk will silently wipe the table on its
 * next save. Only Lab Experiment's results / observation_and_conclusion /
 * conclusion are set up that way today.
 */
const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  minHeight: { type: String, default: '120px' },
  // The detail page passes this on every editor it renders, to hold a locked run
  // open to System Managers only. It was being passed before it was declared, so
  // it landed on the wrapper as a stray attribute and the surface below stayed
  // editable: `contenteditable` was the literal `true`, not a binding.
  readonly: { type: Boolean, default: false },
  // Opt-in. See the note above before turning this on for a new field.
  tables: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue'])

const editor = ref(null)

// ---------------------------------------------------------------------------
// Plain contenteditable path (tables=false) - unchanged
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Quill path (tables=true)
// ---------------------------------------------------------------------------

const quillHost = ref(null)
const quillLoading = ref(false)
const quillError = ref('')
let quill = null
// Set while Quill itself is writing into the document, so the text-change
// handler can tell an edit the user made from one this component pushed in.
let applyingExternal = false

// Unique per instance: Quill binds a toolbar by selector, so two editors on one
// page sharing an id would both drive the first one's buttons.
const toolbarId = `rte-toolbar-${Math.random().toString(36).slice(2, 9)}`

const FONT_SIZES = ['12px', '14px', '16px', '18px', '24px', '32px']

// ---------------------------------------------------------------------------
// Attachments (non-image files)
// ---------------------------------------------------------------------------
// Images go inline at the cursor; everything else collects in a list under the
// editor. The list has to survive a save, and these fields are a single HTML
// column with no room for a second one, so it is stored as a marker-delimited
// block appended to the field's own HTML:
//
//   <quill content><!--rte-attachments-->[{...}]<!--/rte-attachments-->
//
// Quill only ever receives the part before the marker, so the block cannot be
// edited or deleted from inside the editor - which is the point of moving these
// out of the content in the first place. An HTML comment is used rather than a
// <div> so nothing renders it if the field is displayed raw somewhere else.
const ATTACH_OPEN = '<!--rte-attachments-->'
const ATTACH_CLOSE = '<!--/rte-attachments-->'

const attachments = ref([])

const splitStored = (raw) => {
  const value = raw || ''
  const start = value.indexOf(ATTACH_OPEN)
  if (start === -1) return { body: value, files: [] }
  const end = value.indexOf(ATTACH_CLOSE, start)
  if (end === -1) return { body: value.slice(0, start), files: [] }
  const json = value.slice(start + ATTACH_OPEN.length, end)
  let files = []
  try {
    files = JSON.parse(json) || []
  } catch {
    // A hand-edited or truncated block is dropped rather than thrown: losing
    // the list is recoverable, losing the write-up above it is not.
    console.warn('Unreadable attachment block; ignoring it.')
  }
  return { body: value.slice(0, start), files }
}

const joinStored = (body, files) =>
  files && files.length
    ? `${body}${ATTACH_OPEN}${JSON.stringify(files)}${ATTACH_CLOSE}`
    : body

// The single place the parent is told about a change, so the body and the list
// can never be emitted out of step with each other.
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
    // Dynamic, so Rollup splits these into their own chunk. A page with no
    // tables-enabled editor never downloads them.
    const [{ default: Quill }, qbtModule] = await Promise.all([
      import('quill'),
      import('quill-better-table'),
      import('quill/dist/quill.snow.css'),
      import('quill-better-table/dist/quill-better-table.css')
    ])
    const QuillBetterTable = qbtModule.default ?? qbtModule

    // Sizes in px. Quill's default `size` is a CLASS attributor with em-ish
    // named buckets (small/large/huge), which cannot express "14px" and writes
    // ql-size-* classes that mean nothing outside Quill's own stylesheet. The
    // style attributor writes `style="font-size:14px"` instead - inline CSS that
    // survives into the stored HTML and renders anywhere, including the desk's
    // read-only view of these fields.
    const SizeStyle = Quill.import('attributors/style/size')
    SizeStyle.whitelist = FONT_SIZES
    Quill.register(SizeStyle, true)

    // Same reasoning for colour: the style attributors write inline
    // color/background-color rather than Quill-specific classes.
    Quill.register(Quill.import('attributors/style/color'), true)
    Quill.register(Quill.import('attributors/style/background'), true)

    // `true` overwrites a previous registration, which matters because more
    // than one editor can mount over the life of the page.
    Quill.register({ 'modules/better-table': QuillBetterTable }, true)

    await nextTick()
    if (!quillHost.value) return

    quill = new Quill(quillHost.value, {
      theme: 'snow',
      readOnly: props.readonly,
      placeholder: props.placeholder,
      modules: {
        // Quill's own table module has to be off: it and better-table both
        // claim the table blots, and the built-in one wins if left on.
        table: false,
        'better-table': {
          operationMenu: {
            items: {
              unmergeCells: { text: 'Unmerge cells' }
            }
          }
        },
        // Without these the table cannot be navigated or deleted from the
        // keyboard - quill-better-table ships the bindings, they are not
        // installed automatically.
        keyboard: { bindings: QuillBetterTable.keyboardBindings },
        toolbar: {
          container: `#${toolbarId}`,
          handlers: {
            'better-table': insertTable,
            'table-menu': openTableMenu,
            attach: attachFile,
            // Wrap the four inline formats so one armed at a collapsed caret
            // inside a table can be re-applied after better-table drops it.
            // Everything else about them is still Quill's own behaviour.
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
      // innerHTML, not getSemanticHTML(): the field stores raw HTML and the
      // round trip has to be byte-identical, which the semantic serialiser is
      // not - it drops the data-row/colspan attributes better-table needs, and
      // the inline font-size/color styles the new toolbar writes.
      emitCombined()
    })

    // quill-better-table mounts its right-click menu on document.body at
    // position:absolute / top:evt.pageY. That is correct for a page where the
    // document scrolls - but here html/body are height:100% and #app is
    // overflow:hidden, so the document never scrolls and the real scroller is
    // .experiment-detail-container. The menu therefore lands in the right place
    // and then stays there while the table scrolls out from under it.
    //
    // Capture phase, because scroll does not bubble.
    window.addEventListener('scroll', dismissTableMenu, true)

    // Capture phase again: Quill's own handlers run on the editor root, and the
    // viewer has to win before the embed is selected.
    quill.root.addEventListener('click', onEditorClick, true)
    window.addEventListener('keydown', onLightboxKey)

    // Border dragging. mousedown is capture so it runs before better-table's own
    // mousedown on this same node; see startResize.
    quill.root.addEventListener('mousemove', armResize)
    quill.root.addEventListener('mouseleave', disarmResize)
    quill.root.addEventListener('mousedown', startResize, true)

    // Drives the enabled state of the table-operations button. selection-change
    // covers clicks and arrow keys; text-change covers typing that moves the
    // caret into or out of a cell.
    quill.on('selection-change', refreshTableState)
    quill.on('text-change', refreshTableState)

    // Registered after the emitting handler above, so the re-applied format is
    // part of the document before its own text-change emits it.
    quill.on('text-change', reapplyArmedFormats)
    quill.on('selection-change', disarmFormats)

    // Whatever the parent sent while the caret was live is applied once focus
    // leaves the editor for good - see the modelValue watcher.
    editorWidget = quill.root.closest('.rich-text-quill')
    editorWidget?.addEventListener('focusout', onEditorFocusOut)
  } catch (err) {
    console.error('Failed to load the table editor', err)
    quillError.value = 'The table editor could not be loaded. Reload the page to try again.'
  } finally {
    quillLoading.value = false
  }
}

/**
 * Removes the right-click menu when the pane scrolls under it.
 *
 * The node is removed rather than the module being asked to close: better-table
 * tears the menu down from its own `click` listener on document, and there is no
 * public handle on the open menu to call. Removing the node is safe with that -
 * its destroy() calls domNode.remove() (a no-op once detached) and unbinds the
 * listener, so the next real click still cleans up after itself.
 */
function dismissTableMenu() {
  document.querySelectorAll('.qlbt-operation-menu').forEach((el) => el.remove())
}

function insertTable() {
  if (props.readonly || !quill) return
  quill.getModule('better-table').insertTable(2, 3)
  // The operations button below only lights up once better-table considers a
  // table active, which it decides on click - so nudge the state after an
  // insert rather than leaving the button dead until the user clicks a cell.
  nextTick(refreshTableState)
}

// The cell the caret is currently in, or null. Read from the DOM selection
// rather than better-table's internals: its tableSelection is only populated
// after a cell has been clicked, and the caret can be in a table without that.
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

/**
 * Opens better-table's own operations menu on the current cell.
 *
 * A synthetic contextmenu event rather than a hand-built menu: every operation -
 * insert row/column either side, delete row/column/table, merge, unmerge - is
 * implemented on that menu's internal context (its boundary, its column tool
 * cells, its table blot). Rebuilding those call sites here would be a second
 * copy of logic that already exists and would rot the moment the library moved.
 *
 * The listener is on quill.root and reads the composed path, so the event has
 * to bubble from the cell itself and carry client coordinates.
 */
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
      // Just inside the cell's top-left, so the menu opens against the cell it
      // will act on rather than wherever the pointer happens to be.
      clientX: Math.round(r.left + 8),
      clientY: Math.round(r.top + 8)
    })
  )
}

// ---------------------------------------------------------------------------
// Inline formats armed at a collapsed caret inside a table
// ---------------------------------------------------------------------------
// Choosing bold, italic, underline or a font size with nothing selected is meant
// to arm that format for whatever is typed next. Quill implements it by parking
// a Cursor blot at the caret carrying the format; the next character is inserted
// into that blot and comes out formatted.
//
// Inside a table cell the blot does not survive long enough. better-table's
// TableCellLine.optimize re-wraps the line in its required container on the next
// optimize pass, and the pending format is discarded along with the node it was
// attached to - so the first character typed arrives unformatted and the toolbar
// button springs back off, while everything typed after it behaves. That is what
// makes the format look like it "restarts" on the first letter, and only in a
// table.
//
// So the format is remembered here and applied again to the characters that
// actually arrive. Only for a collapsed caret in a cell: with a selection, or
// anywhere outside a table, Quill's own handling is correct and is left alone.
const ARMABLE_FORMATS = ['bold', 'italic', 'underline', 'size']

let armedFormats = {}
let armedAt = -1

// Read from Quill's model rather than the DOM selection: by the time a toolbar
// handler runs, focus may have moved to the button. TableCellLine.formats
// reports the cell's identity attributes, so their presence is what says the
// range is inside a table.
function rangeInTable(range) {
  if (!range) return false
  const formats = quill.getFormat(range)
  return formats.cell != null || formats.row != null
}

function armableHandler(name) {
  // The toolbar has already resolved the value - false for a button being
  // switched off, the chosen option for a select, true for a button going on -
  // so this only has to decide whether it also needs remembering.
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

// Where a delta makes its first insertion, or null if it inserts nothing.
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
  // A delta that inserts nothing - a deletion, a format applied elsewhere - is
  // not the moment to act on. The caret moving away is what disarms; see the
  // selection-change handler.
  if (!inserted) return
  if (inserted.index !== armedAt) {
    armedFormats = {}
    armedAt = -1
    return
  }
  const formats = armedFormats
  // Cleared before formatText, whose own text-change would otherwise re-enter
  // this handler with the same state.
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

// ---------------------------------------------------------------------------
// Resizing rows and columns
// ---------------------------------------------------------------------------
// better-table's own resizer lives in the strip above the table
// (.qlbt-col-tool), which RichTextEditor.css hides: one bordered cell per column
// floating above the grid read as a stray second table. This replaces it with
// the affordance a spreadsheet trains people to expect - drag the border itself.
// Near a cell's vertical border the cursor becomes col-resize and the drag sets
// the column width; near a horizontal one it becomes row-resize and sets the row
// height, which better-table never offered at all.
//
// Where each size is stored, and why it survives a save:
//   column - the `width` attribute on the matching <col> in the table's
//     <colgroup>. table-layout is fixed, so that attribute is what actually
//     decides the width; TableCol.format('width') does nothing more than set the
//     same attribute, so it is set directly.
//   row - style="height:Npx" on the <tr>. No blot models it, so it is written
//     straight to the DOM. Both round-trip because the field is stored as
//     root.innerHTML rather than serialised from Quill's model.
//
// Neither is a delta change, so no text-change fires and the save has to be
// emitted by hand when the drag ends.

// How close to a border the pointer has to be to grab it.
const RESIZE_GRAB = 5
const MIN_COL_WIDTH = 40
const MIN_ROW_HEIGHT = 24

// The border under the pointer, or null. Set on mousemove so mousedown only has
// to decide whether to act, not where.
let armedResize = null
let activeResize = null

/**
 * The <col> governing a cell's right-hand border.
 *
 * Walks the row summing colspans rather than using cellIndex, so a merged cell
 * resizes the last column it covers - the one its right border actually is.
 * A cell displaced by a rowspan from an earlier row is counted from its own
 * row, so a table mixing rowspan and colspan can pick the neighbouring column;
 * dragging from an unmerged row gets the intended one.
 */
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

// Which border the pointer is on, if any. Either side of a border works: with
// border-collapse the two cells share one line, so requiring the correct half
// would make the grab depend on a pixel the user cannot see.
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

// The line drawn over the border under the pointer. Appended to .ql-container
// rather than the editable root - a node inside root would be serialised into
// the field by emitCombined. better-table parks its column tool in the same
// place for the same reason.
let resizeGuide = null
let resizeReadout = null

/**
 * Draws the guide over a border, optionally with a readout.
 *
 * `readout` is the arrow-and-size caption shown during a drag; hovering passes
 * nothing, leaving the caption empty and hidden by CSS while the arrowheads on
 * the line still say which axis the border moves on.
 */
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
  // Offsets are container-relative and add the scroll, because the guide is
  // absolutely positioned inside a container that scrolls under it.
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

// A class rather than an inline style, because the pointer is a data-URI SVG
// with a hotspot and a keyword fallback - too much to assemble in JS, and it
// belongs with the rest of the look. Set on quill.root, whose own attributes are
// not part of root.innerHTML and so never reach the stored field.
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

/**
 * Capture phase, and both default and propagation stopped: better-table starts a
 * cell selection from its own mousedown on quill.root and Quill places the caret
 * from the native default. Dragging a border should do neither.
 */
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
    // The cell or row the guide is drawn against; `target` is the <col> for a
    // column drag, which has no box of its own to measure.
    anchor: armedResize.cell || armedResize.row,
    origin: armedResize.type === 'col' ? evt.clientX : evt.clientY,
    // The attribute where there is one, the rendered size otherwise - a table
    // that has never been resized carries no width, and a row no height.
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
    // A height on a row is a floor, not a cap: a row whose text needs more space
    // keeps it. Dragging up therefore stops where the content does.
    const height = Math.max(MIN_ROW_HEIGHT, start + evt.clientY - origin)
    target.style.height = `${height}px`
    activeResize.applied = height
  }
  // Redrawn from the live geometry, so the line tracks the border it is moving.
  // The arrow is measured against the size the drag started from, not against
  // the previous frame: a jittering hand would otherwise flip it every few
  // pixels, when what is being asked is "am I making this bigger or smaller".
  const delta = activeResize.applied - start
  const arrows = type === 'col' ? ['←', '↔', '→'] : ['↑', '↕', '↓']
  const arrow = arrows[Math.sign(delta) + 1]
  // Excel's own wording for the same readout, with the travel arrow in front -
  // the pointer says which axis, this says which way along it.
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
  // A drag that never moved changed nothing worth saving.
  if (finished && finished.applied !== null) emitCombined()
}

/**
 * Frappe's own upload endpoint, so the file lands in the File doctype and obeys
 * the same size and permission rules as a desk upload.
 *
 * An image goes inline at the cursor. Anything else joins the list under the
 * editor instead of being dropped into the prose - a PDF has nothing to render
 * mid-sentence, and a run's attachments are easier to find as a list than
 * scattered through three write-ups.
 *
 * Uploads stay private. They serve fine to a signed-in session (verified: 200
 * image/png authenticated, 403 anonymous); what was breaking the inline image
 * was the dev server not proxying /private, which vite.config.js now does.
 */
async function attachFile() {
  if (props.readonly || !quill) return

  const input = document.createElement('input')
  input.type = 'file'
  input.addEventListener('change', async () => {
    const file = input.files && input.files[0]
    if (!file) return

    // Read before awaiting: the upload takes long enough for the caret to move,
    // and inserting at a stale index would drop the image somewhere else.
    const range = quill.getSelection(true)
    const at = range ? range.index : quill.getLength()

    const form = new FormData()
    form.append('file', file, file.name)
    form.append('is_private', '1')

    try {
      const res = await fetch('/api/method/upload_file', {
        method: 'POST',
        body: form,
        // Frappe authenticates the SPA by session cookie.
        credentials: 'same-origin',
        headers: { 'X-Frappe-CSRF-Token': window.csrf_token || '' }
      })
      const data = await res.json()
      const url = data?.message?.file_url
      if (!url) throw new Error(data?.message || 'no file_url in response')

      if ((file.type || '').startsWith('image/')) {
        quill.insertEmbed(at, 'image', url, 'user')
        quill.setSelection(at + 1, 0, 'user')
        // text-change fires from the insert and emits for us.
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

// ---------------------------------------------------------------------------
// Image lightbox
// ---------------------------------------------------------------------------
// Inline images render as thumbnails so a screenshot does not swallow the whole
// field; clicking one opens it full size.
//
// Delegated off quill.root rather than bound per image, because images arrive
// and leave as the document is edited and there is nothing to re-bind against.
const lightboxSrc = ref('')

const onEditorClick = (evt) => {
  const img = evt.target
  if (!img || img.tagName !== 'IMG') return
  // Quill selects an embed on click. Opening the viewer instead is the point of
  // the handler, but it does mean click no longer selects the image - Backspace
  // with the caret just after it still deletes, which is the usual way anyway.
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

// ---------------------------------------------------------------------------
// Shared lifecycle
// ---------------------------------------------------------------------------

// Writing innerHTML on every keystroke would reset the caret to the start, so
// only push in values that came from somewhere other than this editor.
// An external value that arrived while the user was typing, held until the
// editor loses focus. See the watcher below for why it cannot be applied
// immediately.
let pendingExternal = null
let editorWidget = null

/**
 * Applies a held external value, once focus has left the editor as a whole.
 *
 * focusout on the widget rather than Quill's own null-range blur: the toolbar's
 * picker labels carry tabindex, so opening the font-size or colour dropdown
 * blurs the editable root while the user is still very much editing. Replacing
 * the document there would destroy the range Quill is about to format - the
 * chosen size would land on nothing. A relatedTarget still inside the widget is
 * therefore not a departure.
 */
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
      // Compared against the combined value, not the body alone: emitCombined
      // sends body+attachments, so comparing the body would see every one of
      // our own emits as an external change and reset the caret.
      const current = joinStored(quill.root.innerHTML, attachments.value)
      if ((val || '') === current) return

      // The guard above is necessary but not sufficient, and rewriting the
      // document while the caret is in it is destructive - it collapses the
      // selection and throws away whatever was just applied.
      //
      // The two sides of that comparison are read at different moments:
      // emitCombined serialises on text-change, this watcher re-serialises when
      // Vue flushes. In between, the DOM moves on its own - Quill optimises
      // after a change (adjacent format nodes merge, empty ones go) and
      // better-table writes <col width> from a setTimeout. So `current` can
      // differ from a value nothing external ever touched, and the reset then
      // restores the document to how it looked one edit ago. Applying bold and
      // then italic was enough to hit it: the second click's reset carried the
      // first click's formatting away with it.
      //
      // Deferring to blur keeps genuinely external updates - a save that comes
      // back sanitised, a switch to another experiment - without ever pulling
      // the document out from under someone mid-edit.
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
  // Unmounting mid-drag would strand these on window, where they outlive the
  // component that owns the row they are moving.
  window.removeEventListener('mousemove', onResizeMove, true)
  window.removeEventListener('mouseup', endResize, true)
  // The menu lives on document.body, outside this component's tree, so Vue does
  // not take it down with the rest of the editor. Leaving it would strand a menu
  // on screen after navigating away from the run.
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
