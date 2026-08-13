/**
 * Turn a Frappe error response into one readable sentence.
 *
 * `_server_messages` is a JSON list of JSON strings, each an object with its own
 * `message` - joining the raw value puts the encoded payload on screen. The
 * messages also carry markup (<b>, <br>) that reads as noise inline, so it is
 * stripped rather than rendered.
 *
 * Anything reaching here is a rule the form does not check itself, so it still
 * has to be readable: pass a `fallback` that names what was being attempted.
 */
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
