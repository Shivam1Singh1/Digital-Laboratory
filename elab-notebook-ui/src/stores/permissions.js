

import { defineStore } from 'pinia'
import { ref } from 'vue'


import { fetchPermissions } from '../api/permissions.js'


const cacheKey = (doctype, docname) => `${doctype}:${docname || 'new'}`

export const usePermissionStore = defineStore('permissions', () => {
  const cache = ref({})


  const inFlight = {}

  const fetchAndCache = async (doctype, docname = null) => {
    const key = cacheKey(doctype, docname)
    if (cache.value[key]) return cache.value[key]
    if (inFlight[key]) return inFlight[key]

    inFlight[key] = fetchPermissions(doctype, docname)
      .then((perms) => {


        if (perms) cache.value[key] = perms
        return perms
      })
      .finally(() => {
        delete inFlight[key]
      })

    return inFlight[key]
  }


  const can = (doctype, action, docname = null) =>
    Boolean(cache.value[cacheKey(doctype, docname)]?.[action])


  const invalidate = (doctype, docname = null) => {
    delete cache.value[cacheKey(doctype, docname)]
  }

  const invalidateAll = () => {
    cache.value = {}
  }


  return { cache, fetchAndCache, can, invalidate, invalidateAll }
})

