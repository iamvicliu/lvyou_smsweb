<template>
  <div ref="root" class="phone-field">
    <input
      class="form-input"
      :class="{ 'has-saved': hasMenu }"
      :value="value"
      :list="listId"
      :placeholder="placeholder"
      inputmode="tel"
      @input="$emit('update:value', $event.target.value)"
    />
    <button
      v-if="hasMenu"
      type="button"
      :class="['saved-toggle', { open }]"
      :title="contactEntries.length ? '打开通讯录和最近发过的号码' : '以前发过的号码，点一下填进来'"
      @click.stop="open = !open"
    >
      {{ contactEntries.length ? '联系人' : '常用' }}
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true">
        <path d="M6 9l6 6 6-6" />
      </svg>
    </button>
    <div v-if="open" class="saved-menu">
      <template v-if="contactEntries.length">
        <div class="menu-section">通讯录</div>
        <button
          v-for="entry in contactEntries"
          :key="'c' + entry.phone"
          type="button"
          class="saved-item with-name"
          :title="showsFull ? entry.phone : '关掉顶部遮挡可看完整号码'"
          @click="pick(entry.phone)"
        >
          <span class="item-name">{{ entry.name }}</span>
          <span class="item-phone">{{ label(entry.phone) }}</span>
          <span v-if="entry.label" class="item-tag">{{ entry.label }}</span>
        </button>
      </template>
      <template v-if="recentPhones.length">
        <div v-if="contactEntries.length" class="menu-section">最近使用</div>
        <button
          v-for="phone in recentPhones"
          :key="'r' + phone"
          type="button"
          class="saved-item"
          :title="showsFull ? phone : '关掉顶部遮挡可看完整号码'"
          @click="pick(phone)"
        >{{ label(phone) }}</button>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { masked } from '../stores/privacy'
import { maskPhone, phoneKey } from '../utils/phone'

const props = defineProps({
  value: { type: String, default: '' },
  phones: { type: Array, default: () => [] },
  // Server-side address book rows: {name, phone, label}. Kept separate from
  // `phones` (local recents) so the menu can label the two groups.
  entries: { type: Array, default: () => [] },
  placeholder: { type: String, default: '' },
  listId: { type: String, default: '' }
})
const emit = defineEmits(['update:value'])

const root = ref(null)
const open = ref(false)
const showsFull = computed(() => !masked.value)

const contactEntries = computed(() => (props.entries || []).filter(e => e && e.phone))

// Recents that already belong to a contact would otherwise show up twice.
const recentPhones = computed(() => {
  const known = new Set(contactEntries.value.map(e => phoneKey(e.phone)))
  return (props.phones || []).filter(p => p && !known.has(phoneKey(p)))
})

const hasMenu = computed(() => contactEntries.value.length > 0 || recentPhones.value.length > 0)

function label(phone) {
  return masked.value ? maskPhone(phone) : String(phone || '')
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
.menu-section {
  padding: 6px 10px 3px;
  color: var(--text-muted);
  font-size: 11px;
  letter-spacing: 0.04em;
}
.saved-item.with-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: inherit;
}
.saved-item .item-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
}
.saved-item .item-phone {
  color: var(--text-secondary);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}
.saved-item .item-tag {
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--bg-input);
  color: var(--text-muted);
  font-size: 11px;
}
</style>
