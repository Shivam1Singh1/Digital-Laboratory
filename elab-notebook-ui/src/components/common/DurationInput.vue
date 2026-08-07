<script setup>
import { ref, watch } from 'vue'
import { splitDuration, toSeconds } from '../../utils/duration'

const props = defineProps({
  // Frappe's Duration fieldtype is stored as an integer number of seconds.
  modelValue: { type: [Number, String], default: 0 },
  disabled: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue'])

const days = ref(0)
const hours = ref(0)
const minutes = ref(0)

const syncFromModel = (val) => {
  const parts = splitDuration(val)
  days.value = parts.days
  hours.value = parts.hours
  minutes.value = parts.minutes
}

syncFromModel(props.modelValue)

watch(
  () => props.modelValue,
  (val) => {
    if (toSeconds(days.value, hours.value, minutes.value) !== Number(val || 0)) {
      syncFromModel(val)
    }
  }
)

const emitChange = () => {
  emit('update:modelValue', toSeconds(days.value, hours.value, minutes.value))
}
</script>

<template>
  <div class="duration-input">
    <label class="duration-part">
      <input
        type="number"
        min="0"
        class="grid-input duration-num"
        v-model.number="days"
        :disabled="disabled"
        @input="emitChange"
      />
      <span class="duration-unit">d</span>
    </label>
    <label class="duration-part">
      <input
        type="number"
        min="0"
        max="23"
        class="grid-input duration-num"
        v-model.number="hours"
        :disabled="disabled"
        @input="emitChange"
      />
      <span class="duration-unit">h</span>
    </label>
    <label class="duration-part">
      <input
        type="number"
        min="0"
        max="59"
        class="grid-input duration-num"
        v-model.number="minutes"
        :disabled="disabled"
        @input="emitChange"
      />
      <span class="duration-unit">m</span>
    </label>
  </div>
</template>
