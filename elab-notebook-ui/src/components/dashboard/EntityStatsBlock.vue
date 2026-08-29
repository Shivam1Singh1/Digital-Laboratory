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

      // Auto select latest month
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

// Extract unique months sorted descending
const uniqueMonths = computed(() => {
  const monthsSet = new Set(rawData.value.map(r => r.month))
  return Array.from(monthsSet).sort((a, b) => b.localeCompare(a))
})

// Calculate total count across all time
const grandTotal = computed(() => {
  return rawData.value.reduce((acc, curr) => acc + curr.count, 0)
})

// Calculate status overall totals (for summary cards)
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

// Filter data for selected month or sum up for "all_time"
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

// Total for the selected month — this is what the donut actually plots,
// so the ring, the centre number and the chips all agree.
const filteredTotal = computed(() => {
  return Object.values(chartData.value).reduce((acc, val) => acc + val, 0)
})

// Calculate percentages and counts for the chart legend
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

// Compile rows for data table
const tableRows = computed(() => {
  const rowsMap = {}

  // Initialize mapping for each month
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

  // Aggregate counts
  rawData.value.forEach(r => {
    if (rowsMap[r.month]) {
      rowsMap[r.month].total += r.count
      rowsMap[r.month].statusCounts[r.status] = r.count
    }
  })

  const rowsArray = Object.values(rowsMap)

  // Sort rows
  return rowsArray.sort((a, b) => {
    return sortAscending.value
      ? a.month.localeCompare(b.month)
      : b.month.localeCompare(a.month)
  })
})

const toggleSort = () => {
  sortAscending.value = !sortAscending.value
}

/**
 * The twelve month buckets the trends chart plots, oldest first.
 *
 * The chart used to take its x-axis from the months that happen to be present in
 * the data, so a doctype with records in one month drew one enormous bar and no
 * timeline at all - which is not a trend, it is a total with an axis drawn round
 * it. Twelve fixed buckets give the bar a scale to be read against, and a month
 * with nothing in it is itself information.
 *
 * The window ends at the later of this month and the newest month in the data,
 * so it always contains the most recent records even if the clock and the data
 * disagree. Anything older than twelve months falls outside the chart; the Data
 * Table still lists every month that has records.
 */
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

// Premium status color helper
const getStatusColor = (status) => {
  const st = String(status).toLowerCase();
  if (st.includes('approve') || st.includes('active') || st.includes('production') || st.includes('completed') || st.includes('passed')) {
    return '#10B981'; // Premium Green
  }
  if (st.includes('draft') || st.includes('idle') || st.includes('setup') || st.includes('unsubmitted')) {
    return '#8b5cf6'; // Violet/Purple (was Premium Blue)
  }
  if (st.includes('pending') || st.includes('review') || st.includes('not reporting')) {
    return '#F59E0B'; // Premium Amber
  }
  if (st.includes('reject') || st.includes('left') || st.includes('off') || st.includes('failed') || st.includes('problem') || st.includes('suspended')) {
    return '#EF4444'; // Premium Red
  }
  if (st.includes('archive') || st.includes('inactive') || st.includes('maintenance')) {
    return '#7c3aed'; // Deep Violet
  }
  return '#6B7280'; // Muted Slate Gray
}

// Chart instance references
const chartRef = ref(null)
let chartInstance = null

const barChartRef = ref(null)
let barChartInstance = null
const viewMode = ref('chart') // 'chart' (Bar Graph) by default, toggle to 'table'

// Historical trends live in a modal so the tile itself stays inside one screen
const showTrends = ref(false)

// ---------------------------------------------------------------------------
// Chart typography
// ---------------------------------------------------------------------------
// Chart.js paints to a canvas, so nothing in style.css reaches these labels.
// Left alone they render in Chart.js's own defaults - Helvetica Neue at 12px -
// which is both off the app's font stack and a step *larger* than the body text
// around the tile, so the densest labels on the dashboard came out as the
// biggest. Values are read off :root rather than written out here, so the axis
// and legend keep tracking the scale in style.css instead of drifting from it,
// and they are read at draw time rather than at import because a canvas is only
// ever painted after the stylesheet has been applied.
const chartFont = (sizeToken, weightToken) => {
  const root = getComputedStyle(document.documentElement)
  // The scale is authored in rem against the 14px root, but Chart.js wants a
  // plain number of px - it does not resolve CSS units itself.
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
  if (total === 0) return // Don't draw empty chart

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

  // Twelve fixed buckets, oldest first, rather than only the months present in
  // the data - see trendMonths. Counts are looked up per month instead of read
  // off tableRows in order, so a month with no records plots as a real zero.
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
      // MM/YY, from the same formatter the rest of the app uses. Twelve
      // spelled-out months would collide on this axis.
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
            // Semibold at the smallest step, matching the th rule in style.css:
            // an axis label sits in the same role as a column header.
            font: chartFont('--fs-3xs', '--fw-semibold')
          }
        },
        y: {
          stacked: true,
          grid: {
            display: false
          },
          // These are record counts - there is no such thing as 1.4 templates.
          // With a max of 2 the default tick generator produced 0.2, 0.4, 0.6 …;
          // `precision: 0` rounds the computed step size to a whole number
          // instead, so the axis goes 0, 1, 2 and stays integral at any scale.
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

// Doctypes this app has its own list page for. Anything not here has no Vue
// equivalent and still goes to the desk - Workstation, the fourth block on the
// dashboard, is the case that keeps this fallback honest.
//
// Keyed on doctype rather than on the block's entityName label, because the
// label is display text ("Team", "Experiments") that can be reworded without
// anyone realising a route depends on it.
const IN_APP_LISTS = {
  'Lab Experiment Template': '/templates',
  'Experiment Team': '/elab-notebook',
  'Lab Experiment': '/experiments'
}

const router = useRouter()

// `month` is accepted because the month rows pass it, and deliberately unused:
// none of the in-app lists take a month filter, and the desk URL this replaced
// did not carry one either, so nothing is lost by ignoring it here rather than
// inventing a filter format each list would have to learn.
const navigateToListView = (month) => {
  const route = IN_APP_LISTS[props.doctype]
  if (route) {
    // Same tab. These are pages of this app, and opening one in a new tab left
    // the user with two copies of the SPA running.
    router.push(route)
    return
  }
  // /app/List/<Doctype> unchanged from before - Frappe resolves that form and
  // redirects to its own slug, and this is not the place to start guessing at
  // slugification rules. deskUrl only fixes the origin: on the Vite dev server
  // window.location.origin is :5173, which is not where the desk lives.
  window.open(deskUrl(`/app/List/${props.doctype}`), '_blank', 'noopener')
}

// Watchers
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
