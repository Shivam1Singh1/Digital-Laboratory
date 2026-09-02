<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { Chart } from 'chart.js/auto'
import { useUserStore } from '../../stores/user'
import { formatMonth } from '../../utils/dateFormatter'
import { deskUrl } from '../../utils/frappeUrl'
import './EntityStatsBlock.css'

const props = defineProps({
  entityName: {
    type: String,
    required: true
  },
  doctype: {
    type: String,
    required: true
  },
  statusField: {
    type: String,
    required: true
  }
})

const userStore = useUserStore()
const loading = ref(true)
const rawData = ref([])
const statuses = ref([])
const selectedMonth = ref('')
const sortAscending = ref(false)

const fetchData = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/method/elab_notebook.elab_notebook.api.dashboard.get_entity_stats', {
      params: {
        doctype: props.doctype,
        status_field: props.statusField,
        project: userStore.currentProject
      }
    })
    if (res.data && res.data.message) {
      rawData.value = res.data.message.data || []
      statuses.value = res.data.message.statuses || []


      if (uniqueMonths.value.length > 0) {
        selectedMonth.value = uniqueMonths.value[0]
      } else {
        selectedMonth.value = 'all_time'
      }
    }
  } catch (err) {
    console.error(`Failed to fetch stats for ${props.doctype}:`, err)
  } finally {
    loading.value = false
    await nextTick()
    renderChart()
  }
}


const uniqueMonths = computed(() => {
  const monthsSet = new Set(rawData.value.map(r => r.month))
  return Array.from(monthsSet).sort((a, b) => b.localeCompare(a))
})


const grandTotal = computed(() => {
  return rawData.value.reduce((acc, curr) => acc + curr.count, 0)
})


const statusOverallCounts = computed(() => {
  const counts = {}
  statuses.value.forEach(st => {
    counts[st] = 0
  })
  rawData.value.forEach(r => {
    if (counts[r.status] !== undefined) {
      counts[r.status] += r.count
    } else {
      counts[r.status] = r.count
    }
  })
  return counts
})


const chartData = computed(() => {
  const counts = {}
  statuses.value.forEach(st => {
    counts[st] = 0
  })

  rawData.value.forEach(r => {
    if (selectedMonth.value === 'all_time' || r.month === selectedMonth.value) {
      if (counts[r.status] !== undefined) {
        counts[r.status] += r.count
      } else {
        counts[r.status] = r.count
      }
    }
  })
  return counts
})


const filteredTotal = computed(() => {
  return Object.values(chartData.value).reduce((acc, val) => acc + val, 0)
})


const legendItems = computed(() => {
  const total = filteredTotal.value
  return statuses.value.map(st => {
    const val = chartData.value[st] || 0
    const pct = total > 0 ? ((val / total) * 100).toFixed(1) : '0.0'
    return {
      status: st,
      count: val,
      percentage: pct,
      color: getStatusColor(st)
    }
  })
})


const tableRows = computed(() => {
  const rowsMap = {}


  uniqueMonths.value.forEach(m => {
    rowsMap[m] = {
      month: m,
      total: 0,
      statusCounts: {}
    }
    statuses.value.forEach(st => {
      rowsMap[m].statusCounts[st] = 0
    })
  })


  rawData.value.forEach(r => {
    if (rowsMap[r.month]) {
      rowsMap[r.month].total += r.count
      rowsMap[r.month].statusCounts[r.status] = r.count
    }
  })

  const rowsArray = Object.values(rowsMap)


  return rowsArray.sort((a, b) => {
    return sortAscending.value
      ? a.month.localeCompare(b.month)
      : b.month.localeCompare(a.month)
  })
})

const toggleSort = () => {
  sortAscending.value = !sortAscending.value
}


const TREND_MONTHS = 12

const trendMonths = computed(() => {
  const now = new Date()
  let end = now.getFullYear() * 12 + now.getMonth()

  for (const m of uniqueMonths.value) {
    const match = /^(\d{4})-(\d{1,2})$/.exec(m)
    if (!match) continue
    const index = Number(match[1]) * 12 + (Number(match[2]) - 1)
    if (index > end) end = index
  }

  const months = []
  for (let i = TREND_MONTHS - 1; i >= 0; i--) {
    const index = end - i
    const year = Math.floor(index / 12)
    const month = (index % 12) + 1
    months.push(`${year}-${String(month).padStart(2, '0')}`)
  }
  return months
})


const getStatusColor = (status) => {
  const st = String(status).toLowerCase();
  if (st.includes('approve') || st.includes('active') || st.includes('production') || st.includes('completed') || st.includes('passed')) {
    return '#10B981';
  }
  if (st.includes('draft') || st.includes('idle') || st.includes('setup') || st.includes('unsubmitted')) {
    return '#8b5cf6';
  }
  if (st.includes('pending') || st.includes('review') || st.includes('not reporting')) {
    return '#F59E0B';
  }
  if (st.includes('reject') || st.includes('left') || st.includes('off') || st.includes('failed') || st.includes('problem') || st.includes('suspended')) {
    return '#EF4444';
  }
  if (st.includes('archive') || st.includes('inactive') || st.includes('maintenance')) {
    return '#7c3aed';
  }
  return '#6B7280';
}


const chartRef = ref(null)
let chartInstance = null

const barChartRef = ref(null)
let barChartInstance = null
const viewMode = ref('chart')


const showTrends = ref(false)


const chartFont = (sizeToken, weightToken) => {
  const root = getComputedStyle(document.documentElement)


  const rootPx = parseFloat(root.fontSize) || 14
  const size = root.getPropertyValue(sizeToken).trim()
  return {
    family: root.getPropertyValue('--sans').trim(),
    size: size.endsWith('rem') ? parseFloat(size) * rootPx : parseFloat(size),
    weight: root.getPropertyValue(weightToken).trim()
  }
}

const renderChart = () => {
  if (chartInstance) {
    chartInstance.destroy()
    chartInstance = null
  }

  if (!chartRef.value) return

  const isLight = userStore.theme === 'light'

  const labels = legendItems.value.map(item => item.status)
  const dataVals = legendItems.value.map(item => item.count)
  const bgColors = legendItems.value.map(item => item.color)

  const total = dataVals.reduce((acc, val) => acc + val, 0)
  if (total === 0) return

  chartInstance = new Chart(chartRef.value, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: dataVals,
        backgroundColor: bgColors,
        borderWidth: isLight ? 1 : 0,
        borderColor: isLight ? '#FAF9FD' : 'transparent'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '76%',
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          titleFont: chartFont('--fs-xs', '--fw-semibold'),
          bodyFont: chartFont('--fs-xs', '--fw-regular'),
          callbacks: {
            label: (context) => {
              const val = context.raw || 0
              const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0
              return ` ${context.label}: ${val} (${pct}%)`
            }
          }
        }
      }
    }
  })
}

const renderBarChart = () => {
  if (barChartInstance) {
    barChartInstance.destroy()
    barChartInstance = null
  }
  if (!barChartRef.value) return

  const isLight = userStore.theme === 'light'


  const months = trendMonths.value
  const byMonth = Object.fromEntries(tableRows.value.map(r => [r.month, r]))

  const datasets = statuses.value.map(st => {
    const data = months.map(m => byMonth[m]?.statusCounts[st] || 0)
    const color = getStatusColor(st)
    return {
      label: st,
      data: data,
      backgroundColor: color,
      borderColor: isLight ? '#FAF9FD' : 'transparent',
      borderWidth: isLight ? 1 : 0,
      borderRadius: 4
    }
  })

  barChartInstance = new Chart(barChartRef.value, {
    type: 'bar',
    data: {


      labels: months.map(formatMonth),
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          stacked: true,
          grid: {
            display: false
          },
          ticks: {
            color: 'var(--text-muted)',


            font: chartFont('--fs-3xs', '--fw-semibold')
          }
        },
        y: {
          stacked: true,
          grid: {
            display: false
          },


          beginAtZero: true,
          ticks: {
            color: 'var(--text-muted)',
            precision: 0,
            font: chartFont('--fs-3xs', '--fw-semibold')
          }
        }
      },
      plugins: {
        legend: {
          display: true,
          position: 'top',
          labels: {
            color: 'var(--text-primary)',
            boxWidth: 12,
            font: chartFont('--fs-2xs', '--fw-semibold')
          }
        },
        tooltip: {
          mode: 'index',
          intersect: false,
          titleFont: chartFont('--fs-xs', '--fw-semibold'),
          bodyFont: chartFont('--fs-xs', '--fw-regular')
        }
      }
    }
  })
}

const openTrends = async () => {
  showTrends.value = true
  await nextTick()
  if (viewMode.value === 'chart') renderBarChart()
}

const closeTrends = () => {
  showTrends.value = false
  if (barChartInstance) {
    barChartInstance.destroy()
    barChartInstance = null
  }
}

const onKeydown = (e) => {
  if (e.key === 'Escape' && showTrends.value) closeTrends()
}


const IN_APP_LISTS = {
  'Lab Experiment Template': '/templates',
  'Experiment Team': '/elab-notebook',
  'Lab Experiment': '/experiments'
}

const router = useRouter()


const navigateToListView = (month) => {
  const route = IN_APP_LISTS[props.doctype]
  if (route) {


    router.push(route)
    return
  }


  window.open(deskUrl(`/app/List/${props.doctype}`), '_blank', 'noopener')
}


watch(() => userStore.currentProject, () => {
  fetchData()
})

watch(() => userStore.theme, () => {
  renderChart()
  if (showTrends.value && viewMode.value === 'chart') {
    renderBarChart()
  }
})

watch(selectedMonth, () => {
  renderChart()
})

watch(viewMode, async (newMode) => {
  if (showTrends.value && newMode === 'chart') {
    await nextTick()
    renderBarChart()
  }
})

watch(tableRows, () => {
  if (showTrends.value && viewMode.value === 'chart') {
    nextTick(() => {
      renderBarChart()
    })
  }
})

onMounted(() => {
  fetchData()
  window.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  if (chartInstance) chartInstance.destroy()
  if (barChartInstance) barChartInstance.destroy()
})
</script>

<template>
  <div class="entity-stats-block card">
    <!-- Header: title, month filter, trends launcher -->
    <div class="block-header">
      <h2 class="block-title">{{ entityName }}</h2>
      <div class="block-header-actions">
        <select v-model="selectedMonth" class="month-select" :aria-label="`Filter ${entityName} by month`">
          <option value="all_time">All Time</option>
          <option v-for="m in uniqueMonths" :key="m" :value="m">{{ formatMonth(m) }}</option>
        </select>
        <button
          class="trends-expand-btn"
          @click="openTrends"
          :title="`Historical trends for ${entityName}`"
          :aria-label="`Historical trends for ${entityName}`"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="15 3 21 3 21 9" />
            <polyline points="9 21 3 21 3 15" />
            <line x1="21" y1="3" x2="14" y2="10" />
            <line x1="3" y1="21" x2="10" y2="14" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Body: donut on the left, status chips on the right -->
    <div class="tile-body">
      <div v-if="loading" class="tile-loading">
        <span class="tile-spinner"></span>
      </div>

      <template v-else-if="filteredTotal > 0">
        <div class="tile-chart">
          <canvas ref="chartRef"></canvas>
          <div class="chart-center-text">
            <span class="chart-center-number">{{ filteredTotal }}</span>
            <span class="chart-center-label">Total</span>
          </div>
        </div>

        <div class="tile-stats">
          <div
            v-for="item in legendItems"
            :key="item.status"
            class="stat-chip"
            :style="{ '--chip-color': item.color, '--chip-bg': item.color + '14' }"
          >
            <span class="stat-chip-label">
              <span class="legend-dot" :style="{ backgroundColor: item.color }"></span>
              <span class="stat-chip-status">{{ item.status }}</span>
            </span>
            <span class="stat-chip-value">
              {{ item.count }}
              <span class="stat-chip-pct">{{ item.percentage }}%</span>
            </span>
          </div>
        </div>
      </template>

      <div v-else class="empty-chart-state">
        <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="12" cy="12" r="10" />
          <line x1="8" y1="12" x2="16" y2="12" />
        </svg>
        <p>No statistics for this scope.</p>
      </div>
    </div>

    <!-- Footer: all-time total, so the month filter never hides the big number -->
    <div class="tile-footer">
      <span class="tile-footer-label">All time</span>
      <span class="tile-footer-value">{{ grandTotal }}</span>
    </div>

    <!-- Historical trends, lifted out of the tile into a modal -->
    <Teleport to="body">
      <div v-if="showTrends" class="trends-modal-backdrop" @click.self="closeTrends">
        <div class="trends-modal" role="dialog" aria-modal="true">
          <div class="section-tabs-header">
            <h3 class="trend-section-title">{{ entityName }} &mdash; Historical Trends</h3>
            <div class="trends-modal-controls">
              <div class="view-toggle-buttons">
                <button
                  class="toggle-btn"
                  :class="{ active: viewMode === 'chart' }"
                  @click="viewMode = 'chart'"
                >
                  <svg class="toggle-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="18" y="3" width="4" height="18" rx="1"/><rect x="10" y="8" width="4" height="13" rx="1"/><rect x="2" y="13" width="4" height="8" rx="1"/></svg>
                  Bar Graph
                </button>
                <button
                  class="toggle-btn"
                  :class="{ active: viewMode === 'table' }"
                  @click="viewMode = 'table'"
                >
                  <svg class="toggle-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="9" y1="6" x2="20" y2="6"/><line x1="9" y1="12" x2="20" y2="12"/><line x1="9" y1="18" x2="20" y2="18"/><circle cx="5" cy="6" r="1"/><circle cx="5" cy="12" r="1"/><circle cx="5" cy="18" r="1"/></svg>
                  Data Table
                </button>
              </div>
              <button class="trends-close-btn" @click="closeTrends" aria-label="Close">&times;</button>
            </div>
          </div>

          <!-- Bar Graph View -->
          <div v-if="viewMode === 'chart'" class="bar-chart-view-wrapper">
            <div class="bar-chart-container" v-if="tableRows.length > 0">
              <canvas ref="barChartRef"></canvas>
            </div>
            <div v-else class="empty-chart-state">
              <p>No historical trend data available.</p>
            </div>
          </div>

          <!-- Data Table View -->
          <div v-else class="table-container">
            <table>
              <thead>
                <tr>
                  <th @click="toggleSort" class="sortable-header">
                    Month
                    <span class="sort-icon">{{ sortAscending ? '▲' : '▼' }}</span>
                  </th>
                  <th>Total</th>
                  <th v-for="st in statuses" :key="st">{{ st }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in tableRows"
                  :key="row.month"
                  class="clickable-row"
                  @click="navigateToListView(row.month)"
                  title="Click to view list in Frappe Desk"
                >
                  <td><strong>{{ formatMonth(row.month) }}</strong></td>
                  <td><strong>{{ row.total }}</strong></td>
                  <td v-for="st in statuses" :key="st">
                    <span
                      v-if="row.statusCounts[st] > 0"
                      class="cell-badge"
                      :style="{ color: getStatusColor(st), backgroundColor: getStatusColor(st) + '12' }"
                    >
                      {{ row.statusCounts[st] }}
                    </span>
                    <span v-else class="cell-zero">-</span>
                  </td>
                </tr>
                <tr v-if="tableRows.length === 0">
                  <td :colspan="statuses.length + 2" class="empty-table-cell">
                    No monthly breakdown data available.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
