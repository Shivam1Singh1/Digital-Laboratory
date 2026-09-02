

const pad = (n) => String(n).padStart(2, '0')


const toDate = (dateInput) => {
  if (dateInput instanceof Date) return dateInput
  if (typeof dateInput !== 'string') return null

  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateInput.trim())
  if (dateOnly) {
    return new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
  }


  const date = new Date(dateInput.includes(' ') ? dateInput.replace(' ', 'T') : dateInput)
  return isNaN(date.getTime()) ? null : date
}


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


export const formatDateTime = (dateInput) => {
  if (!dateInput) return '-'
  const date = toDate(dateInput)
  if (!date || isNaN(date.getTime())) return '-'

  return formatDate(date) + ', ' + pad(date.getHours()) + ':' + pad(date.getMinutes())
}


export const formatAuditDate = (dateInput) => {
  if (!dateInput) return '-'
  const date = toDate(dateInput)
  if (!date || isNaN(date.getTime())) return '-'

  return formatDate(date) + ' ' + pad(date.getHours()) + ':' + pad(date.getMinutes())
}


export const formatMonth = (monthInput) => {
  if (!monthInput || monthInput === 'all_time') return monthInput
  if (typeof monthInput !== 'string') return monthInput

  const match = /^(\d{4})-(\d{1,2})$/.exec(monthInput.trim())
  if (!match) return monthInput

  return pad(match[2]) + '/' + pad(Number(match[1]) % 100)
}
