<script setup>
import { useUserStore } from './stores/user'

const userStore = useUserStore()
</script>

<template>
  <router-view v-if="!userStore.loading" />
  <div v-else class="loading-screen">
    <div class="spinner"></div>
    <p>Loading Enterprise Lab OS...</p>
  </div>
</template>

<style>
.loading-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100vw;
  height: 100vh;
  background-color: #0b1329;
  color: #9fb3d9;

  font-family: var(--sans);
  font-size: var(--fs-lg);
  font-weight: var(--fw-medium);
  letter-spacing: var(--ls-normal);
}

.loading-screen .spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(255, 255, 255, 0.1);
  border-left-color: #4c8dff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
