// Frappe reports validate()/throw() failures in `_server_messages` (a JSON string
// holding JSON strings) rather than in a plain `message`, and the text is HTML
// because of frappe.bold(). Without unwrapping both layers a server-side error
// like "Employee Function not mapped to this project" surfaces as a bare 417.

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
      // fall through to the other shapes
    }
  }

  if (typeof data?.message === 'string' && data.message) return stripHtml(data.message)

  if (data?.exception) {
    // "frappe.exceptions.ValidationError: <text>" -> "<text>"
    const colon = data.exception.indexOf(':')
    return colon === -1 ? data.exception : data.exception.slice(colon + 1).trim()
  }

  return err?.message || 'Something went wrong.'
}
