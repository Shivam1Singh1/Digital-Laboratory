<script setup>

defineProps({


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
