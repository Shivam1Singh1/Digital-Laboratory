<script setup>

import { onBeforeUnmount, onMounted } from 'vue'

defineProps({

  src: { type: String, default: '' },
})

const emit = defineEmits(['close'])


const onKey = (evt) => {
  if (evt.key === 'Escape') emit('close')
}

onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <div v-if="src" class="img-lightbox" @click="$emit('close')">
      <!-- Stops a click on the picture itself from dismissing, so it can be
           pointed at and read without closing. -->
      <img :src="src" class="img-lightbox-img" alt="" @click.stop />
      <button type="button" class="img-lightbox-close" title="Close (Esc)" @click="$emit('close')">×</button>
    </div>
  </Teleport>
</template>
