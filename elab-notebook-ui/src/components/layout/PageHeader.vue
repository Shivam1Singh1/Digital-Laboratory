<script setup>
import './PageHeader.css'


defineProps({


  breadcrumbs: {
    type: Array,
    default: () => [],
  },
  title: {
    type: String,
    required: true,
  },
  subtitle: {
    type: String,
    default: '',
  },


  action: {
    type: Object,
    default: null,
  },
})
</script>

<template>
  <header class="app-page-header">
    <div class="app-page-header__left">
      <nav v-if="breadcrumbs.length" class="app-page-header__crumbs" aria-label="Breadcrumb">
        <template v-for="(crumb, i) in breadcrumbs" :key="`${crumb.label}-${i}`">
          <router-link
            v-if="crumb.href && i < breadcrumbs.length - 1"
            :to="crumb.href"
            class="app-page-header__crumb-link"
          >
            {{ crumb.label }}
          </router-link>
          <span v-else class="app-page-header__crumb-current" aria-current="page">
            {{ crumb.label }}
          </span>
          <span v-if="i < breadcrumbs.length - 1" class="app-page-header__crumb-sep" aria-hidden="true">
            &gt;
          </span>
        </template>
      </nav>

      <h1 class="app-page-header__title">{{ title }}</h1>
      <p v-if="subtitle" class="app-page-header__subtitle">{{ subtitle }}</p>
    </div>

    <!-- Always rendered, even with no action: an absent right column would let
         the left column re-centre and shift the title. -->
    <div class="app-page-header__right">
      <button
        v-if="action"
        type="button"
        class="app-page-header__action"
        :class="`app-page-header__action--${action.variant || 'primary'}`"
        @click="action.onClick"
      >
        <slot name="action-icon">
          <svg
            v-if="action.icon !== 'none'"
            class="app-page-header__action-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"
          >
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </slot>
        {{ action.label }}
      </button>
    </div>
  </header>
</template>
