/**
 * Global date formatting utility
 * Format: "day month year" (e.g., "11 August 2026")
 */

export const formatDate = (dateInput) => {
  if (!dateInput) return '-'

  let date
  if (typeof dateInput === 'string') {
    date = new Date(dateInput)
  } else if (dateInput instanceof Date) {
    date = dateInput
  } else {
    return '-'
  }

  if (isNaN(date.getTime())) {
    return '-'
  }

  const day = date.getDate()
  const months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ]
  const month = months[date.getMonth()]
  const year = date.getFullYear()

  return `${day} ${month} ${year}`
}

/**
 * Format date with time
 * Format: "day month year, HH:MM" (e.g., "11 August 2026, 14:30")
 */
export const formatDateTime = (dateInput) => {
  if (!dateInput) return '-'

  let date
  if (typeof dateInput === 'string') {
    date = new Date(dateInput)
  } else if (dateInput instanceof Date) {
    date = dateInput
  } else {
    return '-'
  }

  if (isNaN(date.getTime())) {
    return '-'
  }

  const day = date.getDate()
  const months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ]
  const month = months[date.getMonth()]
  const year = date.getFullYear()
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')

  return `${day} ${month} ${year}, ${hours}:${minutes}`
}

/**
 * Format date for audit trail/history
 * Format: "day month year HH:MM" (e.g., "11 August 2026 14:30")
 */
export const formatAuditDate = (dateInput) => {
  if (!dateInput) return '-'

  let date
  if (typeof dateInput === 'string') {
    date = new Date(dateInput)
  } else if (dateInput instanceof Date) {
    date = dateInput
  } else {
    return '-'
  }

  if (isNaN(date.getTime())) {
    return '-'
  }

  const day = date.getDate()
  const months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ]
  const month = months[date.getMonth()]
  const year = date.getFullYear()
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')

  return `${day} ${month} ${year} ${hours}:${minutes}`
}

/**
 * Format month from "YYYY-MM" format to "Month Year"
 * Format: "August 2026" (e.g., "2026-08" → "August 2026")
 */
export const formatMonth = (monthInput) => {
  if (!monthInput || monthInput === 'all_time') return monthInput

  const months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ]

  // Handle "YYYY-MM" format
  if (typeof monthInput === 'string' && monthInput.includes('-')) {
    const [year, month] = monthInput.split('-')
    const monthIndex = parseInt(month) - 1
    if (monthIndex >= 0 && monthIndex < 12) {
      return `${months[monthIndex]} ${year}`
    }
  }

  return monthInput
}
