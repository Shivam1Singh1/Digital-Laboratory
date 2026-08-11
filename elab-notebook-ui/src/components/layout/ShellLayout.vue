<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../../stores/user'
import axios from 'axios'
import './ShellLayout.css'

import CreateExperimentModal from '../experiments/CreateExperimentModal.vue'

const userStore = useUserStore()
const router = useRouter()
const labSite = ref('Lab 3B - Genomics')
const dropdownOpen = ref(false)
const sidebarCollapsed = ref(false)

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
  // Redirect to Frappe built-in login
  const redirectUrl = '/api/method/elab_notebook.elab_notebook.api.user.login_redirect'
  window.location.href = `http://localhost:8000/login?redirect-to=${encodeURIComponent(redirectUrl)}`
}

onMounted(async () => {
  await userStore.fetchEmployeeScope()
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
      <div class="sidebar-header">
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
      </div>

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
          
          <router-link to="/experiments" class="nav-item" active-class="active">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            Experiments
          </router-link>

          <router-link to="/elab-notebook" class="nav-item" active-class="active">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            Elab Notebook
          </router-link>
          
          <a href="#" class="nav-item">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            Inventory
          </a>
          
          <a href="#" class="nav-item">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>
            Instruments
          </a>
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
        <a href="#" class="nav-item border-top-nav">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.5 1z"/></svg>
          Settings
        </a>
        
        <!-- Pinned User Card -->
        <div class="user-card">
          <div class="user-avatar-wrapper">
            <img v-if="userStore.user.user_image" :src="userStore.user.user_image" class="avatar-img" alt="User Avatar" />
            <div v-else class="avatar-fallback">{{ userStore.user.initials }}</div>
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
        <div class="search-box">
          <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input type="text" placeholder="Search experiments, resources..." class="search-input" />
          <kbd class="search-kbd">⌘K</kbd>
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
                <img v-if="userStore.user.user_image" :src="userStore.user.user_image" class="avatar-img" alt="User Avatar" />
                <template v-else>{{ userStore.user.initials }}</template>
              </div>
              <div class="top-user-info">
                <span class="top-user-name">{{ userStore.user.full_name }}</span>
                <span class="top-user-lab">{{ labSite }}</span>
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


