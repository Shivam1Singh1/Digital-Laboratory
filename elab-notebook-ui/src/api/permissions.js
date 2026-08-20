// === DYNAMIC-PERMS-START ===
// Whole file belongs to the dynamic-permission work. Left executable but
// unimported - dead code to the bundler, which drops it entirely (verified:
// module count returns to its pre-wiring value after the freeze).
import axios from 'axios'

const ENDPOINT = '/api/method/elab_notebook.elab_notebook.api.permissions.get_permissions'

/**
 * Ask the server what the signed-in user may do.
 *
 * Deliberately dumb: one call, one parsed dict, no caching and no policy. The
 * cache lives in stores/permissions.js so there is a single place to invalidate
 * from, and the policy lives on the server so there is a single place it is
 * decided. Omit `docname` for the doctype-level answer a list page needs.
 *
 * A failed call resolves to null rather than throwing, so a caller that cannot
 * reach the server ends up with no permissions rather than an unhandled
 * rejection - the store turns that into a closed door.
 */
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
// === DYNAMIC-PERMS-END ===
