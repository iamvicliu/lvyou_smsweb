import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { fetchContacts } from '../api/endpoints'
import { phoneKey } from '../utils/phone'

// One server-side address book shared by the send form, the board detail
// dialog and the SMS/call lists. Loaded once per session; every mutation
// reloads it so the name lookup never drifts from the database.
export const useContactsStore = defineStore('contacts', () => {
  const list = ref([])
  const loaded = ref(false)
  const loading = ref(false)
  let inflight = null

  // Flattened {id, name, phone, label, favorite} rows for the suggestion menu.
  const entries = computed(() => {
    const out = []
    for (const contact of list.value) {
      for (const item of contact.phones || []) {
        out.push({
          id: contact.id,
          name: contact.name,
          phone: item.phone,
          label: item.label,
          favorite: contact.favorite
        })
      }
    }
    return out
  })

  const byPhone = computed(() => {
    const map = new Map()
    for (const entry of entries.value) map.set(phoneKey(entry.phone), entry)
    return map
  })

  function nameOf(phone) {
    const entry = byPhone.value.get(phoneKey(phone))
    return entry ? entry.name : ''
  }

  function entryOf(phone) {
    return byPhone.value.get(phoneKey(phone)) || null
  }

  async function load(force = false) {
    if (loading.value && inflight) return inflight
    if (loaded.value && !force) return list.value
    loading.value = true
    inflight = (async () => {
      try {
        const resp = await fetchContacts()
        const data = (resp && resp.data) || {}
        list.value = data.items || []
        loaded.value = true
        return list.value
      } finally {
        loading.value = false
        inflight = null
      }
    })()
    return inflight
  }

  function ensureLoaded() {
    return loaded.value ? Promise.resolve(list.value) : load()
  }

  return { list, loaded, loading, entries, load, ensureLoaded, nameOf, entryOf }
})
