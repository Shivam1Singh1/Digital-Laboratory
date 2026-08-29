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
  /* Was 'Inter', sans-serif - naming Inter without the fallback chain meant
     that until the woff2 arrived this screen rendered in the browser's generic
     sans, which is the one moment in the app where a font swap is visible. */
  font-family: var(--sans);
  font-size: var(--fs-lg);
  font-weight: var(--fw-medium);
  letter-spacing: var(--ls-normal);
}
/* Scoped to the loading screen, NOT a bare `.spinner`.
 *
 * This block is global - App.vue's <style> is not scoped - and it is bundled
 * after styles/list-page.css, where the app's real .spinner and its .btn-spinner
 * modifier live. Declared bare, these four properties therefore won on source
 * order and every *button* spinner in the app came out at 40px with a 1rem
 * bottom margin, which is what burst the buttons on Settings, Team Setup, Team
 * Detail and Template Detail. .btn-spinner never stood a chance: same
 * specificity, earlier in the file.
 *
 * The one place this splash spinner appears is the div below, so that is what it
 * is attached to. See the note at the top of list-page.css, which asks for
 * exactly this: a page that needs to differ scopes its override to its own
 * container rather than redeclaring the bare class. */
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
