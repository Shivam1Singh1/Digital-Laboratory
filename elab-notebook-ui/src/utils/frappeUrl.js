// The Vite dev server (5173) only proxies /api, so desk routes like /app/... have
// to be sent to the Frappe origin explicitly. In production the built app is
// served by Frappe itself, where same-origin is correct.
const FRAPPE_DEV_ORIGIN = 'http://localhost:8000'

export const frappeOrigin = () =>
  import.meta.env.DEV ? FRAPPE_DEV_ORIGIN : window.location.origin

/**
 * Where Frappe's login page sends the browser once a session exists.
 *
 * A server endpoint rather than a path straight into this app: `redirect-to`
 * only accepts a same-site path, so the hop through login_redirect is what lets
 * the final destination be configured per site (see SPA_URL_KEY in api/user.py)
 * rather than being fixed in the bundle.
 */
const LOGIN_LANDING = '/api/method/elab_notebook.elab_notebook.api.user.login_redirect'

/**
 * Absolute URL to Frappe's login page.
 *
 * Built through frappeOrigin() like everything else here. Both callers - the
 * router's auth guard and the Sign out button - used to write
 * `http://localhost:8000/login?...` inline with no dev guard, so in production
 * every logged-out visitor, and everyone who signed out, was sent to a login
 * page on their own machine. Defined once so there is no second copy to miss.
 */
export const loginUrl = (redirectTo = LOGIN_LANDING) =>
  `${frappeOrigin()}/login?redirect-to=${encodeURIComponent(redirectTo)}`

/** Absolute URL to a Frappe desk route, e.g. deskUrl('/app/experiment/new'). */
export const deskUrl = (path, params = {}) => {
  const query = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join('&')

  return `${frappeOrigin()}${path}${query ? `?${query}` : ''}`
}

// An uploaded file, as Frappe stores it: /files/x.png when public,
// /private/files/x.png when not. Both are served by the desk origin, and neither
// is proxied by the dev server - see the note at the top of this file.
const FILE_PATH = /^\/(?:private\/)?files\//i

/** Absolute URL to an uploaded file. Anything else is returned untouched. */
export const fileUrl = (src) =>
  typeof src === 'string' && FILE_PATH.test(src) ? `${frappeOrigin()}${src}` : src

/**
 * A rich-text field's HTML with its file references made absolute.
 *
 * Text Editor fields store what the editor wrote, and the editor writes the
 * root-relative `file_url` Frappe hands back on upload. Root-relative resolves
 * against whatever origin is showing the page - which is the desk in production
 * and the Vite dev server on :5173 in development, where /files is not proxied
 * and every image 404s. Rewriting them to the desk origin makes both cases work
 * from one code path.
 *
 * Rewritten through DOMParser rather than a regex over the markup: an attribute
 * is only an attribute in the places the parser says it is, and `src="..."` also
 * occurs inside text a scientist pasted. parseFromString builds an inert
 * document - no scripts run and no resources load while it is being read - so
 * this neither adds nor removes any exposure that v-html on the same string
 * already has.
 *
 * The guard is not just an optimisation: markup with no file reference is
 * returned as the identical string rather than a re-serialised one, so a field
 * that needs nothing done to it is never reshaped by the round trip.
 */
export const resolveFileUrls = (html) => {
  if (typeof html !== 'string' || !html || !/\/(?:private\/)?files\//i.test(html)) return html

  const doc = new DOMParser().parseFromString(html, 'text/html')

  for (const img of doc.querySelectorAll('img[src]')) {
    img.setAttribute('src', fileUrl(img.getAttribute('src')))
  }
  // Attachment links written into the body, so "open the raw trace" still opens
  // it when the report is read from the dev server.
  for (const anchor of doc.querySelectorAll('a[href]')) {
    anchor.setAttribute('href', fileUrl(anchor.getAttribute('href')))
  }

  return doc.body.innerHTML
}
