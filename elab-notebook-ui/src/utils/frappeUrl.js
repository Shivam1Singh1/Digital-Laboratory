

const FRAPPE_DEV_ORIGIN = 'http://localhost:8000'

export const frappeOrigin = () =>
  import.meta.env.DEV ? FRAPPE_DEV_ORIGIN : window.location.origin


const LOGIN_LANDING = '/api/method/elab_notebook.elab_notebook.api.user.login_redirect'


export const loginUrl = (redirectTo = LOGIN_LANDING) =>
  `${frappeOrigin()}/login?redirect-to=${encodeURIComponent(redirectTo)}`


export const deskUrl = (path, params = {}) => {
  const query = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join('&')

  return `${frappeOrigin()}${path}${query ? `?${query}` : ''}`
}


const FILE_PATH = /^\/(?:private\/)?files\//i


export const fileUrl = (src) =>
  typeof src === 'string' && FILE_PATH.test(src) ? `${frappeOrigin()}${src}` : src


export const resolveFileUrls = (html) => {
  if (typeof html !== 'string' || !html || !/\/(?:private\/)?files\//i.test(html)) return html

  const doc = new DOMParser().parseFromString(html, 'text/html')

  for (const img of doc.querySelectorAll('img[src]')) {
    img.setAttribute('src', fileUrl(img.getAttribute('src')))
  }


  for (const anchor of doc.querySelectorAll('a[href]')) {
    anchor.setAttribute('href', fileUrl(anchor.getAttribute('href')))
  }

  return doc.body.innerHTML
}
