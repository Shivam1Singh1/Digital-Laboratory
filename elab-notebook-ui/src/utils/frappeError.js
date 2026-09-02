

const stripHtml = (html) => {
  const el = document.createElement('div')
  el.innerHTML = html || ''
  return (el.textContent || '').trim()
}

export const extractFrappeError = (err) => {
  const data = err?.response?.data

  if (data?._server_messages) {
    try {
      const messages = JSON.parse(data._server_messages)
      const texts = messages
        .map((raw) => {
          try {
            const parsed = JSON.parse(raw)
            return stripHtml(parsed.message || raw)
          } catch {
            return stripHtml(raw)
          }
        })
        .filter(Boolean)
      if (texts.length) return texts.join('\n')
    } catch {

    }
  }

  if (typeof data?.message === 'string' && data.message) return stripHtml(data.message)

  if (data?.exception) {

    const colon = data.exception.indexOf(':')
    return colon === -1 ? data.exception : data.exception.slice(colon + 1).trim()
  }

  return err?.message || 'Something went wrong.'
}
