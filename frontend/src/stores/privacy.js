import { ref } from 'vue'

// Screenshot mode: masks phone numbers and verification codes everywhere the
// panel prints them. Kept in localStorage so it survives a reload, and in a
// module-level ref so every view reacts without prop drilling.
const KEY = 'lv_privacy_mask'

function readInitial() {
  try {
    return localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

export const masked = ref(readInitial())

export function usePrivacy() {
  function toggle() {
    masked.value = !masked.value
    try {
      localStorage.setItem(KEY, masked.value ? '1' : '0')
    } catch {
      // Private-mode browsers may refuse storage; the ref still works.
    }
  }
  return { masked, toggle }
}
