<template>
  <div ref="root" class="phone-field">
    <input
      class="form-input"
      :class="{ 'has-saved': phones.length }"
      :value="value"
      :list="listId"
      :placeholder="placeholder"
      inputmode="tel"
      @input="$emit('update:value', $event.target.value)"
    />
    <button
      v-if="phones.length"
      type="button"
      :class="['saved-toggle', { open }]"
      title="以前发过的号码，点一下填进来"
      @click.stop="open = !open"
    >
      常用
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true">
        <path d="M6 9l6 6 6-6" />
      </svg>
    </button>
    <div v-if="open" class="saved-menu">
      <button
        v-for="phone in phones"
        :key="phone"
        type="button"
        class="saved-item"
        :title="showsFull ? phone : '关掉顶部遮挡可看完整号码'"
        @click="pick(phone)"
      >{{ label(phone) }}</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { masked } from '../stores/privacy'

const props = defineProps({
  value: { type: String, default: '' },
  phones: { type: Array, default: () => [] },
  placeholder: { type: String, default: '' },
  listId: { type: String, default: '' }
})
const emit = defineEmits(['update:value'])

const root = ref(null)
const open = ref(false)
const showsFull = computed(() => !masked.value)

// Keep the last four digits so two numbers from the same operator stay
// distinguishable while screenshot mode is on.
function label(phone) {
  const value = String(phone || '')
  if (!masked.value || value.length < 8) return value
  return `${value.slice(0, 3)}****${value.slice(-4)}`
}

function pick(phone) {
  emit('update:value', phone)
  open.value = false
}

function onDocClick(event) {
  if (root.value && !root.value.contains(event.target)) open.value = false
}
function onKey(event) {
  if (event.key === 'Escape') open.value = false
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onKey)
})
onUnmounted(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onKey)
})
</script>

<style scoped>
.phone-field { position: relative; min-width: 0; }
.phone-field .form-input { width: 100%; }
.phone-field .form-input.has-saved { padding-right: 74px; }
.saved-toggle {
  position: absolute;
  right: 5px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  gap: 2px;
  height: 26px;
  padding: 0 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: color var(--transition), border-color var(--transition);
}
.saved-toggle svg { width: 12px; height: 12px; }
.saved-toggle:hover,
.saved-toggle.open { color: var(--primary); border-color: var(--primary); }
.saved-menu {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  z-index: 30;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md, 0 8px 24px rgba(0, 0, 0, 0.12));
  padding: 4px;
  max-height: 220px;
  overflow-y: auto;
}
.saved-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 7px 10px;
  border: none;
  border-radius: var(--radius-sm);
  background: none;
  color: var(--text-primary);
  font-size: 13px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  cursor: pointer;
}
.saved-item:hover { background: var(--bg-input); color: var(--primary); }
</style>
