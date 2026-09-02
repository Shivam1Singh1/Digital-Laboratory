

export const toMinutes = (value) => Math.max(0, Math.floor(Number(value) || 0))


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
