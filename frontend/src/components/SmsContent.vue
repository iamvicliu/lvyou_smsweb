<template>
  <div :class="['sms-content', { clamp, open }]" @click="emit('toggle')">
    <template v-for="(seg, i) in segments" :key="i">
      <button
        v-if="seg.code"
        type="button"
        class="code-chip"
        :title="masked ? '已隐藏验证码（关掉遮挡后可看）' : '点击复制验证码 ' + seg.text"
        @click.stop="copy(seg.text)"
      >
        <span class="code-text">{{ masked ? '****' : seg.text }}</span>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <rect x="9" y="9" width="11" height="11" rx="2" />
          <path d="M5 15V5a2 2 0 012-2h10" />
        </svg>
      </button>
      <span v-else>{{ maskText(seg.text) }}</span>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { splitByCodes } from '../utils/codes'
import { maskText } from '../utils/format'
import { masked } from '../stores/privacy'
import { useToast } from '../composables/useToast'

const props = defineProps({
  content: { type: String, default: '' },
  clamp: { type: Boolean, default: false },
  open: { type: Boolean, default: false }
})

const emit = defineEmits(['toggle'])
const toast = useToast()

const segments = computed(() => splitByCodes(props.content))

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // Older WebViews (and plain http origins) reject the async clipboard API.
    const holder = document.createElement('textarea')
    holder.value = text
    holder.style.position = 'fixed'
    holder.style.opacity = '0'
    document.body.appendChild(holder)
    holder.select()
    try {
      document.execCommand('copy')
    } finally {
      document.body.removeChild(holder)
    }
  }
  toast.showToast(masked.value ? '验证码已复制（内容已遮挡）' : `验证码 ${text} 已复制`, 'success')
}
</script>

<style scoped>
.sms-content { white-space: pre-wrap; word-break: break-word; cursor: pointer; }
.code-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin: 0 2px;
  padding: 0 6px;
  border: 1px solid var(--primary, #2563eb);
  border-radius: 6px;
  background: color-mix(in srgb, var(--primary, #2563eb) 10%, transparent);
  color: var(--primary, #2563eb);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.95em;
  font-weight: 600;
  letter-spacing: 0.02em;
  line-height: 1.5;
  cursor: pointer;
  vertical-align: baseline;
}
.code-chip:hover { background: color-mix(in srgb, var(--primary, #2563eb) 18%, transparent); }
.code-chip svg { width: 12px; height: 12px; opacity: 0.75; }
.code-chip:hover svg { opacity: 1; }
</style>
