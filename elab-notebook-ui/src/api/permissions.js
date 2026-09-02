

import axios from 'axios'

const ENDPOINT = '/api/method/elab_notebook.elab_notebook.api.permissions.get_permissions'


export async function fetchPermissions(doctype, docname = null) {
  try {
    const res = await axios.get(ENDPOINT, {
      params: { doctype, docname: docname || undefined }
    })
    return res.data?.message || null
  } catch (err) {
    console.error(`Failed to load permissions for ${doctype}${docname ? `/${docname}` : ''}`, err)
    return null
  }
}

