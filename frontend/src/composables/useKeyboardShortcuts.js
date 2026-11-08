import { onMounted, onBeforeUnmount } from 'vue'

const EDITABLE_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT'])

function isEditable(target) {
  if (!target) return false
  if (EDITABLE_TAGS.has(target.tagName)) return true
  return !!target.isContentEditable
}

export function useKeyboardShortcuts(shortcuts) {
  function handleKeydown(e) {
    let key = e.key.toLowerCase()
    // Space reports " " as its key; normalise to the name used in the maps.
    if (e.code === 'Space' || key === ' ') key = 'space'
    const ctrl = e.ctrlKey || e.metaKey

    for (const [combo, handler] of Object.entries(shortcuts)) {
      const parts = combo.toLowerCase().split('+')
      const needCtrl = parts.includes('ctrl')
      const needKey = parts[parts.length - 1]

      if (needCtrl !== ctrl || key !== needKey) continue
      // Bare keys must not fire while the operator is typing; Escape and the
      // Ctrl combinations stay available everywhere.
      if (!needCtrl && needKey !== 'escape' && isEditable(e.target)) return

      e.preventDefault()
      handler()
      return
    }
  }

  onMounted(() => window.addEventListener('keydown', handleKeydown))
  onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown))
}
