<script setup>
/*
 * The single add-row control for every editable child table in the app.
 *
 * It replaces the "+ Add Row" button that used to sit in each table's header,
 * beside the section title. Up there the action read as a property of the
 * section; down here it reads as the next row of the table it appends to, which
 * is where the eye already is after filling the last one.
 *
 * Every table uses this one component, so the border, padding, icon, type scale
 * and hover state cannot drift apart, and a new table gets the pattern for free.
 *
 * In a CSS-grid/flex table (.grid-table) drop it in as the last child. In a real
 * <table>, wrap it in a full-width row:
 *
 *   <tr class="add-row-tr"><td :colspan="5"><AddRow @add="addMaterial" /></td></tr>
 */
defineProps({
  // "Add Row" suits a generic grid; pass "Add Material" and friends where the
  // table is about one specific thing.
  label: { type: String, default: 'Add Row' },
  disabled: { type: Boolean, default: false },
})

defineEmits(['add'])
</script>

<template>
  <button type="button" class="add-row" :disabled="disabled" @click="$emit('add')">
    <svg class="add-row-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
    <span>{{ label }}</span>
  </button>
</template>
