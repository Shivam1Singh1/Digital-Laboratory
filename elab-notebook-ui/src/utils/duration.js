// Frappe's Duration fieldtype travels over the REST API as an integer number of
// seconds. The form edits days/hours/minutes, so every value has to be converted
// on the way in and on the way out — a raw "10" posted for "10 days" would be
// stored as ten seconds.

const SECONDS_PER_DAY = 86400
const SECONDS_PER_HOUR = 3600
const SECONDS_PER_MINUTE = 60

export const toSeconds = (days, hours, minutes) =>
  (Number(days) || 0) * SECONDS_PER_DAY +
  (Number(hours) || 0) * SECONDS_PER_HOUR +
  (Number(minutes) || 0) * SECONDS_PER_MINUTE

export const splitDuration = (value) => {
  let total = Math.max(0, Math.floor(Number(value) || 0))

  const days = Math.floor(total / SECONDS_PER_DAY)
  total -= days * SECONDS_PER_DAY

  const hours = Math.floor(total / SECONDS_PER_HOUR)
  total -= hours * SECONDS_PER_HOUR

  const minutes = Math.floor(total / SECONDS_PER_MINUTE)

  return { days, hours, minutes }
}

export const formatDuration = (value) => {
  const seconds = Math.max(0, Math.floor(Number(value) || 0))
  if (!seconds) return '0m'

  const { days, hours, minutes } = splitDuration(seconds)
  const parts = []
  if (days) parts.push(`${days} day${days === 1 ? '' : 's'}`)
  if (hours) parts.push(`${hours}h`)
  if (minutes) parts.push(`${minutes}m`)

  return parts.join(' ')
}
