<script setup>
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../../stores/user'
import { loginUrl } from '../../utils/frappeUrl'
import axios from 'axios'
import './ShellLayout.css'

import CreateExperimentModal from '../experiments/CreateExperimentModal.vue'

const userStore = useUserStore()
const router = useRouter()
const dropdownOpen = ref(false)
const sidebarCollapsed = ref(false)
const avatarFailed = ref(false)

const searchQuery = ref('')
const searchResults = ref([])
const searchLoading = ref(false)
const searchDropdownVisible = ref(false)
const searchInputRef = ref(null)
const searchContainerRef = ref(null)

let searchDebounceTimer = null


const SEARCH_MIN_CHARS = 3

const searchTooShort = computed(() => {
  const query = searchQuery.value.trim()
  return query.length > 0 && query.length < SEARCH_MIN_CHARS
})

const performSearch = async () => {
  const query = searchQuery.value.trim()
  if (query.length < SEARCH_MIN_CHARS) {
    searchResults.value = []
    return
  }

  searchLoading.value = true
  try {
    const response = await axios.get('/api/method/elab_notebook.elab_notebook.api.global_search.get_global_search_results', {
      params: { query }
    })
    searchResults.value = response.data.message || []
  } catch (err) {
    console.error('Global search failed:', err)
    searchResults.value = []
  } finally {
    searchLoading.value = false
  }
}

const onSearchInput = () => {
  searchDropdownVisible.value = true
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
  }
  searchDebounceTimer = setTimeout(() => {
    performSearch()
  }, 250)
}

const groupedResults = computed(() => {
  const groups = {
    'Lab Experiment Template': { label: 'Templates', items: [] },
    'Lab Experiment': { label: 'Experiments', items: [] },
    'Experiment Team': { label: 'Teams', items: [] }
  }

  searchResults.value.forEach(item => {
    const group = groups[item.doctype]
    if (group) {
      group.items.push(item)
    }
  })

  return Object.values(groups).filter(g => g.items.length > 0)
})

const selectResult = (result) => {
  router.push(result.route)
  searchDropdownVisible.value = false
  searchQuery.value = ''
  if (searchInputRef.value) {
    searchInputRef.value.blur()
  }
}

const closeSearchDropdown = () => {
  searchDropdownVisible.value = false
}

const handleGlobalKeydown = (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault()
    if (searchInputRef.value) {
      searchInputRef.value.focus()
      searchDropdownVisible.value = true
    }
  } else if (e.key === 'Escape') {
    closeSearchDropdown()
    if (searchInputRef.value) {
      searchInputRef.value.blur()
    }
  }
}

const handleClickOutside = (e) => {
  if (searchContainerRef.value && !searchContainerRef.value.contains(e.target)) {
    closeSearchDropdown()
  }
}


const showAvatarImage = computed(() => !!userStore.user.user_image && !avatarFailed.value)

const userInitials = computed(() => {
  if (userStore.user.initials) return userStore.user.initials
  const parts = (userStore.user.full_name || '').trim().split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return '?'
})

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const toggleDropdown = () => {
  dropdownOpen.value = !dropdownOpen.value
}

const logout = async () => {
  try {
    await axios.post('/api/method/logout')
  } catch (err) {
    console.error('Logout failed', err)
  }


  window.location.href = loginUrl()
}

onMounted(async () => {
  await userStore.fetchEmployeeScope()
  window.addEventListener('keydown', handleGlobalKeydown)
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
  document.removeEventListener('click', handleClickOutside)
})


watch(() => userStore.user.user_image, () => {
  avatarFailed.value = false
})

watch(() => userStore.user.name, async (newVal) => {
  if (newVal && newVal !== 'Guest') {
    await userStore.fetchEmployeeScope()
  }
})
</script>

<template>
  <div class="dashboard-container" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <!-- Left Sidebar -->
    <aside class="left-sidebar">
      <!-- The masthead doubles as the way home, the way a logo does in every
           other app. `to="/"` is the Dashboard route. -->
      <router-link to="/" class="sidebar-header" aria-label="Elab Notebook — go to the dashboard">
        <div class="logo-box">
          <svg class="logo-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M4.5 16.5c-1.5 1.26-2.5 3.19-2.5 5.5h20c0-2.31-1-4.24-2.5-5.5" />
            <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zm0 15c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5z" />
          </svg>
        </div>
        <div class="sidebar-titles">
          <span class="app-name">Elab Notebook</span>
          <span class="app-subtitle">Enterprise Lab OS</span>
        </div>
      </router-link>

      <nav class="sidebar-nav">
        <!-- GROUP 1 -->
        <div class="nav-group">
          <div class="group-label">Workspace</div>

          <router-link to="/" class="nav-item" active-class="active" exact-active-class="active">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
            Dashboard
          </router-link>

          <router-link to="/templates" class="nav-item" active-class="active">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            Experiment Templates
          </router-link>

          <router-link to="/elab-notebook" class="nav-item" active-class="active">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            Elab Notebook
          </router-link>

          <router-link to="/experiments" class="nav-item" active-class="active">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            Experiments
          </router-link>

          <router-link to="/samples" class="nav-item" active-class="active">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 2h6v6l4 9a3 3 0 0 1-2.7 4.3H7.7A3 3 0 0 1 5 17l4-9z"/><line x1="9" y1="2" x2="15" y2="2"/><line x1="7" y1="15" x2="17" y2="15"/></svg>
            Samples
          </router-link>
        </div>

        <!-- GROUP 2 -->
        <div class="nav-group">
          <div class="group-label">Intelligence</div>
          <a href="#" class="nav-item">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
            AI Predictions
            <span class="badge badge-new ml-auto">New</span>
          </a>
          <a href="#" class="nav-item">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/></svg>
            Reports & Analytics
          </a>
        </div>
      </nav>

      <!-- Sidebar Pinned Bottom -->
      <div class="sidebar-bottom">
        <router-link to="/settings" class="nav-item border-top-nav" active-class="active">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.5 1z"/></svg>
          Settings
        </router-link>

        <!-- Pinned User Card -->
        <div class="user-card">
          <div class="user-avatar-wrapper">
            <img
              v-if="showAvatarImage"
              :src="userStore.user.user_image"
              class="avatar-img"
              :alt="userStore.user.full_name"
              @error="avatarFailed = true"
            />
            <div v-else class="avatar-fallback">{{ userInitials }}</div>
          </div>
          <div class="user-meta">
            <span class="user-name">{{ userStore.user.full_name }}</span>
            <span class="user-role">{{ userStore.user.role }}</span>
          </div>
        </div>
      </div>
    </aside>

    <!-- Main Workspace Area -->
    <main class="main-workspace">
      <!-- Top Bar -->
      <header class="top-bar">
        <div class="top-bar-left">
          <button class="top-bar-action-btn sidebar-toggle-btn" @click="toggleSidebar" title="Toggle Sidebar">
            <svg v-if="sidebarCollapsed" class="btn-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
              <line x1="9" y1="3" x2="9" y2="21"/>
              <path d="M12 9l3 3-3 3"/>
            </svg>
            <svg v-else class="btn-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
              <line x1="9" y1="3" x2="9" y2="21"/>
              <path d="M15 15l-3-3 3-3"/>
            </svg>
          </button>

          <!-- Search bar -->
          <div ref="searchContainerRef" class="global-search-wrapper">
            <div class="global-search-box">
              <svg class="global-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              <input
                ref="searchInputRef"
                v-model="searchQuery"
                type="text"
                placeholder="Search experiments, resources..."
                class="global-search-input"
                @input="onSearchInput"
                @focus="searchDropdownVisible = true"
              />
              <kbd class="global-search-kbd">⌘K</kbd>
            </div>

            <!-- Dropdown Results -->
            <div v-if="searchDropdownVisible && searchQuery.trim()" class="global-search-dropdown">
              <div v-if="searchTooShort" class="global-search-dropdown-status">
                Type at least {{ SEARCH_MIN_CHARS }} characters to search
              </div>
              <div v-else-if="searchLoading" class="global-search-dropdown-status">
                <span class="global-search-spinner"></span> Searching...
              </div>
              <template v-else-if="groupedResults.length">
                <div v-for="group in groupedResults" :key="group.label" class="global-search-dropdown-group">
                  <div class="global-search-dropdown-header">{{ group.label }}</div>
                  <div
                    v-for="item in group.items"
                    :key="item.name"
                    class="global-search-dropdown-item"
                    @click="selectResult(item)"
                  >
                    <span class="global-search-dropdown-item-title">{{ item.title || item.subtitle || item.name }}</span>
                    <span class="global-search-dropdown-item-name">{{ item.name }}</span>
                  </div>
                </div>
              </template>
              <div v-else class="global-search-dropdown-status">
                No results found
              </div>
            </div>
          </div>
        </div>

        <!-- Right Side items -->
        <div class="top-bar-right">
          <!-- Project selector -->
          <div class="project-selector">
            <span class="project-label">Active Project:</span>

            <select v-if="userStore.employeeScope.scope === 'no_function'" class="project-select-dropdown" disabled>
              <option value="">No function assigned</option>
            </select>
            <select v-else v-model="userStore.currentProject" class="project-select-dropdown">
              <option value="all">All Projects</option>
              <option v-for="proj in userStore.employeeScope.projects" :key="proj.name" :value="proj.name">
                {{ proj.project_name || proj.name }}
              </option>
            </select>
          </div>

          <!-- Theme Toggle Buttons -->
          <div class="theme-toggle-group">
            <button class="top-bar-action-btn theme-btn" :class="{ active: userStore.theme === 'dark' }" @click="userStore.setTheme('dark')" title="Night Mode">
              <svg class="btn-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
              </svg>
            </button>
            <button class="top-bar-action-btn theme-btn" :class="{ active: userStore.theme === 'light' }" @click="userStore.setTheme('light')" title="Day Mode">
              <svg class="btn-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="5"/>
                <line x1="12" y1="1" x2="12" y2="3"/>
                <line x1="12" y1="21" x2="12" y2="23"/>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                <line x1="1" y1="12" x2="3" y2="12"/>
                <line x1="21" y1="12" x2="23" y2="12"/>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
              </svg>
            </button>
          </div>

          <!-- Notification Bell -->
          <button class="top-bar-action-btn notification-btn" title="Notifications">
            <svg class="btn-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0"/>
            </svg>
            <span class="notification-badge-dot"></span>
          </button>

          <!-- User avatar info dropdown -->
          <div class="top-user-menu-wrapper">
            <div class="top-user-menu" @click="toggleDropdown">
              <div class="top-user-avatar">
                <img
                  v-if="showAvatarImage"
                  :src="userStore.user.user_image"
                  class="avatar-img"
                  :alt="userStore.user.full_name"
                  @error="avatarFailed = true"
                />
                <span v-else class="avatar-initials">{{ userInitials }}</span>
              </div>
              <div class="top-user-info">
                <span class="top-user-name">{{ userStore.user.full_name }}</span>
              </div>
              <svg class="chevron-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
            </div>

            <div v-if="dropdownOpen" class="user-dropdown">
              <div class="dropdown-item header-item">
                <strong>{{ userStore.user.full_name }}</strong>
                <span>{{ userStore.user.email }}</span>
              </div>
              <hr class="dropdown-divider" />
              <div class="dropdown-item" @click="logout">Sign Out</div>
            </div>
          </div>
        </div>
      </header>

      <!-- Viewport child components render here -->
      <router-view />
    </main>
    <CreateExperimentModal />
  </div>
</template>


