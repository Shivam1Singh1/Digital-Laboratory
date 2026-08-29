/**
 * Global date formatting utility.
 *
 * One format across the whole app: DD/MM/YY, zero-padded, e.g. 27/08/26.
 * Every list, detail page, audit trail and chart axis goes through here, so the
 * format is changed in one place rather than per component.
 */

const pad = (n) => String(n).padStart(2, '0')

/**
 * Parse what Frappe actually sends, without the UTC trap.
 *
 * `new Date('2026-08-27')` is parsed by the spec as UTC midnight, so west of
 * Greenwich it renders as the 26th - a date-only value silently losing a day.
 * A bare YYYY-MM-DD is therefore split by hand and built in local time, which is
 * what a date with no timezone on it means. Strings that carry a time are left
 * to the engine, which already reads those as local.
 */
const toDate = (dateInput) => {
  if (dateInput instanceof Date) return dateInput
  if (typeof dateInput !== 'string') return null

  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateInput.trim())
  if (dateOnly) {
    return new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
  }

  // 'YYYY-MM-DD HH:MM:SS' - Safari refuses the space, so hand it the T form.
  const date = new Date(dateInput.includes(' ') ? dateInput.replace(' ', 'T') : dateInput)
  return isNaN(date.getTime()) ? null : date
}

/** DD/MM/YY, e.g. '27/08/26'. */
export const formatDate = (dateInput) => {
  if (!dateInput) return '-'
  const date = toDate(dateInput)
  if (!date || isNaN(date.getTime())) return '-'

  return [
    pad(date.getDate()),
    pad(date.getMonth() + 1),
    pad(date.getFullYear() % 100),
  ].join('/')
}

/** DD/MM/YY, HH:MM - e.g. '27/08/26, 14:30'. */
export const formatDateTime = (dateInput) => {
  if (!dateInput) return '-'
  const date = toDate(dateInput)
  if (!date || isNaN(date.getTime())) return '-'

  return formatDate(date) + ', ' + pad(date.getHours()) + ':' + pad(date.getMinutes())
}

/**
 * DD/MM/YY HH:MM - e.g. '27/08/26 14:30'.
 *
 * formatDateTime without the comma. Kept separate because the audit trail lines
 * these up in a column, where the comma reads as part of the value.
 */
export const formatAuditDate = (dateInput) => {
  if (!dateInput) return '-'
  const date = toDate(dateInput)
  if (!date || isNaN(date.getTime())) return '-'

  return formatDate(date) + ' ' + pad(date.getHours()) + ':' + pad(date.getMinutes())
}

/**
 * A YYYY-MM bucket as MM/YY, e.g. '2026-08' -> '08/26'.
 *
 * The house style with the day dropped, because a month bucket has no day to
 * show. Short on purpose: this labels twelve x-axis ticks on the trends chart,
 * where a spelled-out month would collide with its neighbours.
 */
export const formatMonth = (monthInput) => {
  if (!monthInput || monthInput === 'all_time') return monthInput
  if (typeof monthInput !== 'string') return monthInput

  const match = /^(\d{4})-(\d{1,2})$/.exec(monthInput.trim())
  if (!match) return monthInput

  return pad(match[2]) + '/' + pad(Number(match[1]) % 100)
}
