import { computed, ref } from 'vue'

// One phone book for the whole panel: the dashboard recipient field, the dial
// field and the detail dialog's quick dial all read the same list, so a number
// typed once anywhere is available everywhere.
const BOOK_KEY = 'lvyou.phonebook'
const LEGACY_KEY = 'lvyou.myphone'
const MAX_PHONES = 8

function readStored() {
  try {
    const raw = localStorage.getItem(BOOK_KEY)
    if (raw) {
      const list = JSON.parse(raw)
      if (Array.isArray(list)) {
        return list
          .map(v => String(v || '').trim())
          .filter(Boolean)
          .slice(0, MAX_PHONES)
      }
    }
    // Older builds kept a single "my phone" string; fold it into the list so
    // the quick-dial buttons keep working after the upgrade.
    const legacy = String(localStorage.getItem(LEGACY_KEY) || '').trim()
    if (legacy) return [legacy]
  } catch (e) {
    // Private mode can refuse storage; an empty book is still usable.
  }
  return []
}

const phones = ref(readStored())

function persist() {
  try {
    localStorage.setItem(BOOK_KEY, JSON.stringify(phones.value))
    if (phones.value[0]) localStorage.setItem(LEGACY_KEY, phones.value[0])
    else localStorage.removeItem(LEGACY_KEY)
  } catch (e) {
    // Keep the in-memory list; only durability is lost.
  }
}

function normalize(value) {
  return String(value || '').replace(/[\s-]/g, '').trim()
}

export function usePhonebook() {
  const primaryPhone = computed(() => phones.value[0] || '')
  const savedPhones = computed(() => phones.value)

  // Moves the number to the front: the last one used is the one offered first
  // next time, which is what the recipient field needs.
  function rememberPhone(value) {
    const phone = normalize(value)
    if (!phone) return
    phones.value = [phone, ...phones.value.filter(p => p !== phone)].slice(0, MAX_PHONES)
    persist()
  }

  function forgetPhone(value) {
    const phone = normalize(value)
    phones.value = phones.value.filter(p => p !== phone)
    persist()
  }

  return { primaryPhone, savedPhones, rememberPhone, forgetPhone }
}
