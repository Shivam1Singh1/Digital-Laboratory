

const ATTACH_OPEN = '<!--rte-attachments-->'
const ATTACH_CLOSE = '<!--/rte-attachments-->'


export const splitStored = (raw) => {
  const value = raw || ''
  const start = value.indexOf(ATTACH_OPEN)
  if (start === -1) return { body: value, files: [] }

  const end = value.indexOf(ATTACH_CLOSE, start)


  if (end === -1) return { body: value.slice(0, start), files: [] }

  const json = value.slice(start + ATTACH_OPEN.length, end)
  let files = []
  try {
    const parsed = JSON.parse(json)


    files = Array.isArray(parsed) ? parsed.filter((f) => f && f.url) : []
  } catch {
    console.warn('Unreadable attachment block; ignoring it.')
  }
  return { body: value.slice(0, start), files }
}


export const joinStored = (body, files) =>
  files && files.length
    ? `${body}${ATTACH_OPEN}${JSON.stringify(files)}${ATTACH_CLOSE}`
    : body


export const richHasContent = (raw) => {
  const { body, files } = splitStored(raw)
  if (files.length) return true
  const text = String(body || '')
    .replace(/<[^>]*>/g, '')
    .replace(/&nbsp;/g, ' ')
    .trim()
  return text !== '' || /<(img|table)\b/i.test(body || '')
}
