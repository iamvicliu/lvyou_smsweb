<template>
  <div class="audio-clip">
    <button
      class="clip-btn play"
      :title="playing ? '暂停录音' : '播放录音'"
      :aria-label="playing ? '暂停录音' : '播放录音'"
      @click="toggle"
    >
      <svg v-if="!playing" viewBox="0 0 20 20" fill="currentColor"><path d="M6.5 4.2v11.6c0 .6.6.9 1.1.6l9-5.8a.7.7 0 000-1.2l-9-5.8c-.5-.3-1.1 0-1.1.6z"/></svg>
      <svg v-else viewBox="0 0 20 20" fill="currentColor"><rect x="5.5" y="4" width="3.5" height="12" rx="1.2"/><rect x="11" y="4" width="3.5" height="12" rx="1.2"/></svg>
    </button>
    <div
      ref="trackEl"
      class="clip-track"
      role="slider"
      aria-label="录音进度"
      :aria-valuenow="Math.round(pct)"
      aria-valuemin="0"
      aria-valuemax="100"
      tabindex="0"
      @click="seek"
      @keydown.left.prevent="skip(-5)"
      @keydown.right.prevent="skip(5)"
    >
      <div class="clip-fill" :style="{ width: pct + '%' }"></div>
      <span class="clip-thumb" :style="{ left: pct + '%' }"></span>
    </div>
    <span class="clip-time">{{ clock(current) }}<template v-if="total > 0"> / {{ clock(total) }}</template></span>
    <a class="clip-btn ghost" :href="download" :title="`下载录音${sizeLabel ? ' · ' + sizeLabel : ''}`" :aria-label="`下载录音${sizeLabel ? ' · ' + sizeLabel : ''}`" download>
      <svg viewBox="0 0 20 20" fill="currentColor"><path d="M10 3a1 1 0 011 1v6.6l2.3-2.3a1 1 0 111.4 1.4l-4 4a1 1 0 01-1.4 0l-4-4a1 1 0 111.4-1.4L9 10.6V4a1 1 0 011-1z"/><path d="M4 14a1 1 0 011 1v1h10v-1a1 1 0 112 0v1.5a1.5 1.5 0 01-1.5 1.5h-11A1.5 1.5 0 013 16.5V15a1 1 0 011-1z"/></svg>
    </a>
    <button v-if="canDelete" class="clip-btn ghost danger" title="删除录音" aria-label="删除录音" @click="emit('delete')">
      <svg viewBox="0 0 20 20" fill="currentColor"><path d="M8 2.5a1 1 0 00-.9.55L6.4 4H4a1 1 0 000 2h12a1 1 0 100-2h-2.4l-.7-1.45A1 1 0 0012 2.5H8z"/><path d="M5 7h10l-.7 9.1a1.5 1.5 0 01-1.5 1.4H7.2a1.5 1.5 0 01-1.5-1.4L5 7z"/></svg>
    </button>
    <audio
      ref="audioEl"
      :src="src"
      preload="none"
      @play="playing = true"
      @pause="playing = false"
      @timeupdate="onTime"
      @loadedmetadata="onMeta"
      @ended="onEnded"
    ></audio>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  src: { type: String, required: true },
  download: { type: String, default: '' },
  duration: { type: Number, default: 0 },
  size: { type: Number, default: 0 },
  canDelete: { type: Boolean, default: false }
})

const emit = defineEmits(['delete'])

const audioEl = ref(null)
const trackEl = ref(null)
const playing = ref(false)
const current = ref(0)
const metaDuration = ref(0)

const total = computed(() => metaDuration.value || props.duration || 0)
const pct = computed(() => (total.value ? Math.min(100, (current.value / total.value) * 100) : 0))
const sizeLabel = computed(() => {
  const n = props.size
  if (!n) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
})

function clock(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0))
  const m = Math.floor(s / 60)
  return `${m}:${String(s % 60).padStart(2, '0')}`
}

function toggle() {
  const el = audioEl.value
  if (!el) return
  if (el.paused) {
    // Each clip owns its own <audio>; pause the others globally so two
    // recordings never play over each other.
    document.querySelectorAll('.audio-clip audio').forEach(other => {
      if (other !== el) other.pause()
    })
    el.play().catch(() => { playing.value = false })
  } else {
    el.pause()
  }
}

function seek(e) {
  const el = audioEl.value
  if (!el || !total.value) return
  const rect = trackEl.value.getBoundingClientRect()
  const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width))
  el.currentTime = ratio * total.value
  current.value = el.currentTime
}

function skip(delta) {
  const el = audioEl.value
  if (!el || !total.value) return
  el.currentTime = Math.min(total.value, Math.max(0, el.currentTime + delta))
  current.value = el.currentTime
}

function onTime() {
  current.value = audioEl.value ? audioEl.value.currentTime : 0
}

function onMeta() {
  metaDuration.value = audioEl.value && isFinite(audioEl.value.duration) ? audioEl.value.duration : 0
}

function onEnded() {
  playing.value = false
  current.value = 0
  if (audioEl.value) audioEl.value.currentTime = 0
}

watch(() => props.src, () => {
  playing.value = false
  current.value = 0
  metaDuration.value = 0
})

onBeforeUnmount(() => {
  if (audioEl.value) audioEl.value.pause()
})
</script>

<style scoped>
.audio-clip {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  min-width: 218px;
  max-width: 100%;
  padding: 3px 4px;
}
.clip-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  flex-shrink: 0;
  transition: color var(--transition), background var(--transition), transform var(--transition);
}
.clip-btn svg { width: 15px; height: 15px; }
.clip-btn.play { background: var(--primary-glow); color: var(--primary); }
.clip-btn.play:hover { background: var(--primary); color: #fff; transform: scale(1.04); }
.clip-btn.ghost:hover { color: var(--text-primary); background: var(--bg-input); }
.clip-btn.danger:hover { color: var(--danger); background: var(--danger-glow); }
.clip-btn:focus-visible,
.clip-track:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
.clip-track {
  position: relative;
  flex: 1;
  min-width: 76px;
  height: 5px;
  border-radius: 999px;
  background: var(--border);
  cursor: pointer;
  transition: background var(--transition);
}
.clip-track:hover { background: var(--border-light); }
.clip-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--primary), var(--primary-light, var(--primary)));
  pointer-events: none;
}
.clip-thumb {
  position: absolute;
  top: 50%;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #fff;
  border: 2px solid var(--primary);
  transform: translate(-50%, -50%);
  pointer-events: none;
  opacity: 0;
  transition: opacity var(--transition);
}
.audio-clip:hover .clip-thumb,
.clip-track:focus-visible .clip-thumb { opacity: 1; }
.clip-time {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11.5px;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}
.audio-clip audio { display: none; }
</style>
