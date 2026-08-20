// === DYNAMIC-PERMS-START ===
// Whole file belongs to the dynamic-permission work. Left executable but
// unimported by any page; perm-store.test.mjs exercises it directly.
import { defineStore } from 'pinia'
import { ref } from 'vue'

// Extension spelled out: Vite resolves it either way, but Node's ESM loader
// does not, and perm-store.test.mjs runs this module directly under Node.
import { fetchPermissions } from '../api/permissions.js'

// Doctype-level answers (no record yet) and record-level answers share one map,
// so the key has to say which is which - 'new' is the doctype-level slot.
const cacheKey = (doctype, docname) => `${doctype}:${docname || 'new'}`

export const usePermissionStore = defineStore('permissions', () => {
  const cache = ref({})
  // Keyed the same way. Two components mounting at once ask for the same doc,
  // and without this they each fire a request and race to write the answer.
  const inFlight = {}

  const fetchAndCache = async (doctype, docname = null) => {
    const key = cacheKey(doctype, docname)
    if (cache.value[key]) return cache.value[key]
    if (inFlight[key]) return inFlight[key]

    inFlight[key] = fetchPermissions(doctype, docname)
      .then((perms) => {
        // A failed call is left uncached on purpose: caching the null would
        // lock the buttons off for the rest of the session over one dropped
        // request, where leaving it out lets the next mount try again.
        if (perms) cache.value[key] = perms
        return perms
      })
      .finally(() => {
        delete inFlight[key]
      })

    return inFlight[key]
  }

  /**
   * Fails closed. An answer that has not arrived yet is not "allowed pending
   * proof" - returning true here would flash every button on screen and then
   * take them away, and on a slow connection would leave them long enough to
   * click. Callers render off this and let the button appear when the answer
   * does.
   */
  const can = (doctype, action, docname = null) =>
    Boolean(cache.value[cacheKey(doctype, docname)]?.[action])

  // Call after anything that can change the answer - a submit, a cancel, a
  // workflow transition. The dict was true for the state the record was in
  // before the action, and that state is now gone.
  const invalidate = (doctype, docname = null) => {
    delete cache.value[cacheKey(doctype, docname)]
  }

  const invalidateAll = () => {
    cache.value = {}
  }

  // Not persisted anywhere. Permissions are session-fresh by definition, and a
  // dict carried across a login would describe whoever was signed in last.
  return { cache, fetchAndCache, can, invalidate, invalidateAll }
})
// === DYNAMIC-PERMS-END ===
