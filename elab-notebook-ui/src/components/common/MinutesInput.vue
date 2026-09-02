<script setup>


defineProps({
  modelValue: { type: [Number, String], default: 0 },
  disabled: { type: Boolean, default: false },
  inputClass: { type: String, default: 'grid-input' }
})

const emit = defineEmits(['update:modelValue'])

const onInput = (e) => {
  const n = Math.max(0, Math.floor(Number(e.target.value) || 0))
  emit('update:modelValue', n)
}
</script>

<template>
  <div class="minutes-input">
    <input
      type="number"
      min="0"
      step="1"
      :class="inputClass"
      :value="modelValue"
      :disabled="disabled"
      placeholder="0"
      @input="onInput"
    />
    <span class="minutes-unit">min</span>
  </div>
</template>
