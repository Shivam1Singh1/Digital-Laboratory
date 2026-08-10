// The Vite dev server (5173) only proxies /api, so desk routes like /app/... have
// to be sent to the Frappe origin explicitly. In production the built app is
// served by Frappe itself, where same-origin is correct.
const FRAPPE_DEV_ORIGIN = 'http://localhost:8000'

export const frappeOrigin = () =>
  import.meta.env.DEV ? FRAPPE_DEV_ORIGIN : window.location.origin

/** Absolute URL to a Frappe desk route, e.g. deskUrl('/app/experiment/new'). */
export const deskUrl = (path, params = {}) => {
  const query = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join('&')

  return `${frappeOrigin()}${path}${query ? `?${query}` : ''}`
}
