
export function readServerError(err, fallback = 'Something went wrong. Please try again.') {
  const raw = err?.response?.data?._server_messages
  if (!raw) return fallback
  try {
    const messages = JSON.parse(raw)
      .map((entry) => {
        try {
          return JSON.parse(entry).message ?? entry
        } catch {
          return entry
        }
      })
      .map((message) => String(message).replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim())
      .filter(Boolean)
    return messages.length ? messages.join(' ') : fallback
  } catch {
    return fallback
  }
}
