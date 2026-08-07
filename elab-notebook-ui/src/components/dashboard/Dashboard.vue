<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import axios from 'axios'
import { Chart } from 'chart.js/auto'
import { useUserStore } from '../../stores/user'
import './Dashboard.css'

const userStore = useUserStore()

// User info
const labSite = ref('Lab 3B - Genomics')

// Selected date range
const dateRange = ref('Last 30 Days')

// Loading & error states
const loading = ref({
  summary: true,
  monthly: true,
  successRate: true,
  yieldTrend: true,
  chemicals: true,
  recent: true,
  feed: true,
  tasks: true
})

// Data state
const summaryData = ref({ active: 0, completed: 0, pending_approval: 0, running: 0, scientists: 0, instruments: 0 })
const chemicalsData = ref([])
const recentData = ref([])
const feedData = ref([])
const tasksData = ref([])

// Chart references
const monthlyChartRef = ref(null)
const successChartRef = ref(null)
const yieldChartRef = ref(null)

// Fallback data in case the backend server is not reachable
const fallbacks = {
  summary: { active: 12, completed: 148, pending_approval: 5, running: 3, scientists: 8, instruments: 15 },
  monthly: {
    months: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    completed: [15, 20, 18, 25, 30, 22, 28, 35, 32, 27, 24, 19],
    terminated: [2, 4, 1, 3, 5, 2, 4, 3, 2, 5, 3, 1]
  },
  successRate: { passed: 78, failed: 12, inconclusive: 10 },
  yieldTrend: {
    months: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug"],
    yield: [82.4, 84.1, 83.5, 86.2, 88.0, 87.5, 89.1, 91.3]
  },
  chemicals: [
    { name: "Ethanol (99.8%)", volume: 1240, unit: "L" },
    { name: "Hydrochloric Acid (1M)", volume: 450, unit: "L" },
    { name: "Sodium Hydroxide (2M)", volume: 380, unit: "L" },
    { name: "Acetonitrile (HPLC)", volume: 310, unit: "L" },
    { name: "Methanol (Anhydrous)", volume: 280, unit: "L" }
  ],
  recent: [
    { id: "EXP-2026-0089", name: "CRISPR-Cas9 knockout of APP gene in HEK293 cells", owner: "Dr. Sarah Connor", status: "In Review", progress: 85, updated: "2 hours ago" },
    { id: "EXP-2026-0088", "name": "HPLC analysis of synthetic peptide purification", owner: "John Doe", status: "Running", progress: 45, updated: "3 hours ago" },
    { id: "EXP-2026-0087", "name": "Elution kinetics of monoclonal antibody on Protein A column", owner: "Dr. Sarah Connor", status: "Completed", progress: 100, updated: "Yesterday" },
    { id: "EXP-2026-0086", "name": "Buffer preparation and calibration of pH sensors", owner: "Alice Smith", status: "Approved", progress: 100, updated: "2 days ago" }
  ],
  feed: [
    { user: "Dr. Sarah Connor", action: "submitted experiment", target: "EXP-2026-0089", time: "10 mins ago" },
    { user: "System", action: "flagged sensor anomaly on", target: "Bioreactor #4", time: "45 mins ago" },
    { user: "John Doe", action: "started run on", target: "EXP-2026-0088", time: "1 hour ago" },
    { user: "Alice Smith", action: "updated calibration for", target: "Spectrophotometer SP-3", time: "3 hours ago" },
    { user: "Dr. Sarah Connor", action: "signed and approved", target: "EXP-2026-0085", time: "Yesterday" }
  ],
  tasks: [
    { id: 1, text: "Sign off EXP-2026-0089 review documentation", done: false },
    { id: 2, text: "Calibrate pH meters in Lab 3B", done: false },
    { id: 3, text: "Order replenishment of HPLC-grade Acetonitrile", done: true },
    { id: 4, text: "Review weekly instrument utilization logs", done: false }
  ]
}

// Fetch dashboard data
const fetchData = async () => {
  const projParam = userStore.currentProject;

  // 1. Fetch Summary
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.dashboard.get_dashboard_summary', {
      params: { project: projParam }
    })
    summaryData.value = res.data.message || fallbacks.summary
  } catch (e) {
    summaryData.value = fallbacks.summary
  } finally {
    loading.value.summary = false
  }

  // 2. Fetch Chemical Consumption
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.dashboard.get_chemical_consumption', {
      params: { project: projParam }
    })
    chemicalsData.value = res.data.message || fallbacks.chemicals
  } catch (e) {
    chemicalsData.value = fallbacks.chemicals
  } finally {
    loading.value.chemicals = false
  }

  // 3. Fetch Recent Experiments
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.dashboard.get_recent_experiments', {
      params: { project: projParam }
    })
    recentData.value = res.data.message || fallbacks.recent
  } catch (e) {
    recentData.value = fallbacks.recent
  } finally {
    loading.value.recent = false
  }

  // 4. Fetch Activity Feed
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.dashboard.get_activity_feed', {
      params: { project: projParam }
    })
    feedData.value = res.data.message || fallbacks.feed
  } catch (e) {
    feedData.value = fallbacks.feed
  } finally {
    loading.value.feed = false
  }

  // 5. Fetch Upcoming Tasks
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.dashboard.get_upcoming_tasks', {
      params: { project: projParam }
    })
    tasksData.value = res.data.message || fallbacks.tasks
  } catch (e) {
    tasksData.value = fallbacks.tasks
  } finally {
    loading.value.tasks = false
  }

  // Next, render charts after DOM updates
  await nextTick()
  initCharts()
}

// Chart Initializations
let monthlyChart = null
let successChart = null
let yieldChart = null

const initCharts = async () => {
  // Destroy existing charts to allow hot-reloads/re-mounts
  if (monthlyChart) monthlyChart.destroy()
  if (successChart) successChart.destroy()
  if (yieldChart) yieldChart.destroy()

  const isLight = userStore.theme === 'light'
  const textColor = isLight ? '#6C6682' : '#9FB3D9'
  const gridColor = isLight ? 'rgba(124, 58, 237, 0.08)' : 'rgba(255, 255, 255, 0.05)'
  const primaryColor = isLight ? '#7C3AED' : '#4C8DFF'

  // 1. Monthly Experiments Chart
  let monthlyRes = fallbacks.monthly
  try {
    loading.value.monthly = true
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.dashboard.get_monthly_experiments', {
      params: { project: userStore.currentProject }
    })
    if (res.data.message) monthlyRes = res.data.message
  } catch (e) {
    // Keep fallback
  } finally {
    loading.value.monthly = false
  }

  if (monthlyChartRef.value) {
    monthlyChart = new Chart(monthlyChartRef.value, {
      type: 'bar',
      data: {
        labels: monthlyRes.months,
        datasets: [
          {
            label: 'Completed',
            data: monthlyRes.completed,
            backgroundColor: primaryColor,
            borderRadius: 4
          },
          {
            label: 'Terminated',
            data: monthlyRes.terminated,
            backgroundColor: '#F87171',
            borderRadius: 4
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'top',
            labels: { color: textColor, font: { family: 'Inter' } }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: textColor }
          },
          y: {
            grid: { color: gridColor },
            ticks: { color: textColor }
          }
        }
      }
    })
  }

  // 2. Success Rate Donut Chart
  let successRes = fallbacks.successRate
  try {
    loading.value.successRate = true
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.dashboard.get_success_rate', {
      params: { project: userStore.currentProject }
    })
    if (res.data.message) successRes = res.data.message
  } catch (e) {
    // Keep fallback
  } finally {
    loading.value.successRate = false
  }

  if (successChartRef.value) {
    successChart = new Chart(successChartRef.value, {
      type: 'doughnut',
      data: {
        labels: ['Passed', 'Failed', 'Inconclusive'],
        datasets: [{
          data: [successRes.passed, successRes.failed, successRes.inconclusive],
          backgroundColor: ['#34D399', '#F87171', '#FBBF24'],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '70%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: { color: textColor, font: { family: 'Inter' }, padding: 15 }
          }
        }
      }
    })
  }

  // 3. Yield Trend Line Chart
  let yieldRes = fallbacks.yieldTrend
  try {
    loading.value.yieldTrend = true
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.dashboard.get_yield_trend', {
      params: { project: userStore.currentProject }
    })
    if (res.data.message) yieldRes = res.data.message
  } catch (e) {
    // Keep fallback
  } finally {
    loading.value.yieldTrend = false
  }

  if (yieldChartRef.value) {
    yieldChart = new Chart(yieldChartRef.value, {
      type: 'line',
      data: {
        labels: yieldRes.months,
        datasets: [{
          label: 'Average Yield (%)',
          data: yieldRes.yield,
          borderColor: primaryColor,
          borderWidth: 2,
          tension: 0.3,
          fill: true,
          backgroundColor: isLight ? 'rgba(124, 58, 237, 0.05)' : 'rgba(76, 141, 255, 0.05)'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: textColor }
          },
          y: {
            grid: { color: gridColor },
            ticks: { color: textColor }
          }
        }
      }
    })
  }
}

// Toggle Task completion locally for interactive dashboard experience
const toggleTask = (task) => {
  task.done = !task.done
}

watch(() => userStore.currentProject, () => {
  fetchData()
})

watch(() => userStore.theme, () => {
  initCharts()
})

onMounted(() => {
  fetchData()
})
</script>

<template>
  <div class="dashboard-scrollable-content">
        <!-- Page Header -->
        <div class="page-header">
          <div class="page-header-left">
            <!-- Breadcrumbs -->
            <nav class="breadcrumb-nav">
              <span class="breadcrumb-link">Home</span>
              <span class="breadcrumb-separator">&gt;</span>
              <span class="breadcrumb-current">Laboratory Dashboard</span>
            </nav>
            <h1 class="page-title">Good morning, {{ userStore.user.first_name }}</h1>
            <p class="page-subtitle">
              {{ summaryData.running || 0 }} runs live and {{ summaryData.pending_approval || 0 }} records need your signature
            </p>
          </div>

          <div class="page-header-right">
            <!-- Date range selector -->
            <select v-model="dateRange" class="date-select-dropdown">
              <option>Today</option>
              <option>Last 7 Days</option>
              <option>Last 30 Days</option>
              <option>This Quarter</option>
            </select>
            <!-- Export button -->
            <button class="btn btn-secondary">
              <svg class="btn-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              Export
            </button>
          </div>
        </div>

        <!-- Dashboard Content Grid Layout -->
        <div class="dashboard-grid">
          
          <!-- Stat cards row (6 items) -->
          <div class="stats-grid-row">
            <div class="card stat-card" :class="{ 'loading-opacity': loading.summary }">
              <span class="stat-title">Active Experiments</span>
              <div class="stat-value-container">
                <span class="stat-value">{{ summaryData.active }}</span>
                <span class="stat-indicator success">+3 this wk</span>
              </div>
            </div>
            <div class="card stat-card" :class="{ 'loading-opacity': loading.summary }">
              <span class="stat-title">Completed (YTD)</span>
              <div class="stat-value-container">
                <span class="stat-value">{{ summaryData.completed }}</span>
                <span class="stat-indicator success">Target met</span>
              </div>
            </div>
            <div class="card stat-card" :class="{ 'loading-opacity': loading.summary }">
              <span class="stat-title">Pending Approval</span>
              <div class="stat-value-container">
                <span class="stat-value warning-color">{{ summaryData.pending_approval }}</span>
                <span class="stat-indicator warning-color">Requires action</span>
              </div>
            </div>
            <div class="card stat-card" :class="{ 'loading-opacity': loading.summary }">
              <span class="stat-title">Running Now</span>
              <div class="stat-value-container">
                <span class="stat-value info-color">{{ summaryData.running }}</span>
                <span class="stat-indicator info-color">Normal loads</span>
              </div>
            </div>
            <div class="card stat-card" :class="{ 'loading-opacity': loading.summary }">
              <span class="stat-title">Active Scientists</span>
              <div class="stat-value-container">
                <span class="stat-value">{{ summaryData.scientists }}</span>
                <span class="stat-indicator">In 3 labs</span>
              </div>
            </div>
            <div class="card stat-card" :class="{ 'loading-opacity': loading.summary }">
              <span class="stat-title">Instruments Online</span>
              <div class="stat-value-container">
                <span class="stat-value success-color">{{ summaryData.instruments }}</span>
                <span class="stat-indicator success-color">100% health</span>
              </div>
            </div>
          </div>

          <!-- Main content split area -->
          <div class="split-layout">
            <!-- Left main column -->
            <div class="split-left">
              <!-- Monthly Experiments Bar Chart -->
              <div class="card chart-card">
                <h3 class="card-title">Monthly Run Volume</h3>
                <div class="chart-wrapper">
                  <canvas ref="monthlyChartRef"></canvas>
                </div>
              </div>

              <!-- Yield Trend Line Chart -->
              <div class="card chart-card">
                <h3 class="card-title">Average Yield Trend</h3>
                <div class="chart-wrapper">
                  <canvas ref="yieldChartRef"></canvas>
                </div>
              </div>

              <!-- Recent Experiments Table -->
              <div class="card table-card">
                <div class="card-header-row">
                  <h3 class="card-title">Recent Run Records</h3>
                  <a href="#" class="view-all-link">View all experiments &rarr;</a>
                </div>
                <div class="table-container">
                  <table>
                    <thead>
                      <tr>
                        <th>EXP ID</th>
                        <th>Experiment Description</th>
                        <th>Lead Scientist</th>
                        <th>Status</th>
                        <th>Progress</th>
                        <th>Last Modified</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="exp in recentData" :key="exp.id">
                        <td class="font-mono text-accent">{{ exp.id }}</td>
                        <td class="exp-name-cell">{{ exp.name }}</td>
                        <td>{{ exp.owner }}</td>
                        <td>
                          <span class="status-pill" :class="{
                            'status-in-review': exp.status === 'In Review',
                            'status-running': exp.status === 'Running',
                            'status-completed': exp.status === 'Completed',
                            'status-approved': exp.status === 'Approved'
                          }">
                            {{ exp.status }}
                          </span>
                        </td>
                        <td>
                          <div class="table-progress-wrapper">
                            <span class="progress-val">{{ exp.progress }}%</span>
                            <div class="progress-bar-container">
                              <div class="progress-bar-fill" :style="{ width: exp.progress + '%' }"></div>
                            </div>
                          </div>
                        </td>
                        <td class="text-muted">{{ exp.updated }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <!-- Right sidebar column -->
            <div class="split-right">
              <!-- Success Rate Donut -->
              <div class="card chart-card-donut">
                <h3 class="card-title">Run Success Distribution</h3>
                <div class="donut-chart-wrapper">
                  <canvas ref="successChartRef"></canvas>
                </div>
              </div>

              <!-- Chemical Consumption List -->
              <div class="card consumption-card">
                <h3 class="card-title">Quarterly Chemical Volumes</h3>
                <div class="consumption-list">
                  <div v-for="chem in chemicalsData" :key="chem.name" class="consumption-item">
                    <div class="chem-row">
                      <span class="chem-name">{{ chem.name }}</span>
                      <span class="chem-volume">{{ chem.volume }} {{ chem.unit }}</span>
                    </div>
                    <div class="progress-bar-container">
                      <div class="progress-bar-fill" :style="{ width: Math.min(100, (chem.volume / 1500) * 100) + '%' }"></div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Live Activity Feed -->
              <div class="card activity-card">
                <h3 class="card-title">System & Audit Log</h3>
                <div class="activity-timeline">
                  <div v-for="(act, idx) in feedData" :key="idx" class="timeline-item">
                    <div class="timeline-icon-dot"></div>
                    <div class="timeline-body">
                      <p class="timeline-text">
                        <strong>{{ act.user }}</strong> {{ act.action }} <span class="text-accent">{{ act.target }}</span>
                      </p>
                      <span class="timeline-time">{{ act.time }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Upcoming Tasks Checklist -->
              <div class="card checklist-card">
                <h3 class="card-title">My Lab Checklist</h3>
                <div class="checklist-items">
                  <div v-for="task in tasksData" :key="task.id" class="checklist-item" @click="toggleTask(task)">
                    <div class="checkbox-box" :class="{ checked: task.done }">
                      <svg v-if="task.done" class="check-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                    </div>
                    <span class="checklist-text" :class="{ 'checklist-done': task.done }">{{ task.text }}</span>
                  </div>
                </div>
              </div>

              <!-- Quick Actions Grid -->
              <div class="card quick-actions-card">
                <h3 class="card-title">Quick Lab Actions</h3>
                <div class="quick-actions-grid">
                  <button class="quick-action-btn">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="action-btn-svg"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                    New Run
                  </button>
                  <button class="quick-action-btn">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="action-btn-svg"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                    Add Protocol
                  </button>
                  <button class="quick-action-btn">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="action-btn-svg"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
                    Check Devices
                  </button>
                  <button class="quick-action-btn">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="action-btn-svg"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
                    Audit Report
                  </button>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
</template>


