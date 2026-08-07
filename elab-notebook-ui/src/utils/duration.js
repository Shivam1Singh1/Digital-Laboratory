// Time is stored and transmitted as whole minutes (Int fields), so no unit
// conversion happens on the wire. These helpers only handle display.

export const toMinutes = (value) => Math.max(0, Math.floor(Number(value) || 0))

/** "0 min" · "45 min" · "2h 05m" · "1d 3h 20m" */
export const formatMinutes = (value) => {
  const total = toMinutes(value)
  if (!total) return '0 min'

  const days = Math.floor(total / 1440)
  const hours = Math.floor((total % 1440) / 60)
  const minutes = total % 60

  if (!days && !hours) return `${minutes} min`

  const parts = []
  if (days) parts.push(`${days}d`)
  if (hours) parts.push(`${hours}h`)
  if (minutes) parts.push(`${String(minutes).padStart(2, '0')}m`)

  return `${parts.join(' ')} (${total} min)`
}
