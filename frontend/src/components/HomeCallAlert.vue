<template>
  <section v-if="calls.length" class="home-call" :class="{ ringing }" aria-live="polite">
    <div class="hc-head">
      <span class="hc-dot" :class="{ ring: ringing }"></span>
      <strong>{{ ringing ? '有来电' : '通话进行中' }}</strong>
      <span class="hc-sub">{{ ringing ? '可以直接在首页接听或挂断' : '线路还开着，可以在这里挂断' }}</span>
      <RouterLink class="hc-all" to="/calls">通话页 →</RouterLink>
    </div>

    <div
      v-for="call in calls"
      :key="call.id"
      class="hc-row"
      :class="{ ring: call.state === 'ringing' }"
    >
      <span class="hc-who">
        <b v-if="contactName(call.phone)">{{ contactName(call.phone) }}</b>
        <span class="mono" :class="{ muted: contactName(call.phone) }">
          {{ maskText(call.phone) || '未知号码' }}
        </span>
      </span>
      <span class="hc-where">{{ shortDevice(call.device_name) }} · 卡槽 {{ call.slot }}</span>
      <span class="hc-state" :class="call.state">{{ stateLabel(call.state) }}</span>
      <span class="hc-elapsed mono">{{ elapsedText(call.state, call.elapsed) }}</span>
      <span class="hc-actions">
        <button
          v-if="call.state === 'ringing'"
          class="btn-confirm mini"
          :disabled="!!busy[call.id]"
          @click="act(call, 'answer')"
        >{{ busy[call.id] === 'answer' ? '接听中…' : '接听' }}</button>
        <button
          class="btn-secondary mini danger"
          :disabled="!!busy[call.id]"
          @click="act(call, 'hangup')"
        >挂断</button>
      </span>
      <span v-if="status[call.id]" class="hc-msg" :class="status[call.id].ok ? 'ok' : 'bad'">
        {{ status[call.id].text }}
      </span>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { controlPhone, fetchLiveCalls } from '../api/endpoints'
import { useContactsStore } from '../stores/contacts'
import { maskText } from '../utils/format'

// Same 5-second cadence as the calls page: a ringing line must show up here
// before the board's own auto-answer timer (a few rings) takes it.
const POLL_MS = 5000

const contactsStore = useContactsStore()
const calls = ref([])
const busy = reactive({})
const status = reactive({})
// A hangup the operator just pressed must stay gone while the board's final
// 603 push is in flight; the row is keyed by record id, so a new call still
// shows up immediately.
const suppressed = new Set()

const ringing = computed(() => calls.value.some(call => call.state === 'ringing'))

const baseTitle = typeof document !== 'undefined' ? document.title : ''

function contactName(phone) {
  return contactsStore.nameOf(phone)
}

function shortDevice(name) {
  return String(name || '').replace(/^X31[-\s]*/i, 'X31 ')
}

function stateLabel(state) {
  return { ringing: '响铃中', answered: '通话中', dialing: '呼出中' }[state] || state
}

function elapsedText(state, value) {
  const total = Math.max(0, Number(value || 0))
  const m = Math.floor(total / 60)
  const text = m ? `${m} 分 ${total % 60} 秒` : `${total} 秒`
  return state === 'ringing' ? `响了 ${text}` : text
}

async function loadNow() {
  try {
    const data = await fetchLiveCalls()
    calls.value = ((data && data.items) || []).filter(item => !suppressed.has(item.id))
  } catch {
    // Keep the previous banner on a transient read failure; the next tick
    // retries in five seconds.
  }
}

async function act(call, action) {
  busy[call.id] = action
  delete status[call.id]
  try {
    const r = await controlPhone({ deviceId: call.device_id, slot: call.slot, action })
    if (!r || r.ok === false) {
      throw new Error((r && r.note) || '板子没有接受这条指令')
    }
    if (action === 'hangup') {
      suppressed.add(call.id)
      calls.value = calls.value.filter(item => item.id !== call.id)
    } else {
      call.state = 'answered'
      setTimeout(loadNow, 1500)
    }
  } catch (e) {
    const detail = e && e.response && e.response.data && e.response.data.detail
    status[call.id] = { ok: false, text: detail || (e && e.message) || '指令没有发出去' }
    setTimeout(() => { delete status[call.id] }, 6000)
  } finally {
    delete busy[call.id]
  }
}

// A background tab still gets the title change, so the call is noticed even
// when the dashboard is not the visible window.
watch(ringing, value => {
  if (typeof document === 'undefined') return
  document.title = value ? '📞 来电 - ' + baseTitle : baseTitle
})

let timer = null

onMounted(() => {
  contactsStore.ensureLoaded().catch(() => {})
  loadNow()
  timer = setInterval(loadNow, POLL_MS)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (typeof document !== 'undefined') document.title = baseTitle
})
</script>

<style scoped>
.home-call {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0 0 14px;
  padding: 12px 14px;
  border: 1px solid rgba(245, 158, 11, 0.45);
  border-radius: var(--radius-lg);
  background: rgba(245, 158, 11, 0.08);
}
.home-call.ringing { animation: hcRing 2s ease-in-out infinite; }
@keyframes hcRing {
  0%, 100% { border-color: rgba(245, 158, 11, 0.45); }
  50% { border-color: rgba(245, 158, 11, 0.95); }
}
.hc-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 13px; }
.hc-head strong { font-size: 14px; color: var(--text-primary); }
.hc-sub { font-size: 12px; color: var(--text-muted); }
.hc-all { margin-left: auto; font-size: 12px; color: var(--primary); }
.hc-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--warning, #f59e0b);
  box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.18);
}
.hc-dot.ring { animation: hcDot 1.2s ease-in-out infinite; }
@keyframes hcDot {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.35); opacity: 0.65; }
}
.hc-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 9px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-card);
}
.hc-who { display: flex; align-items: baseline; gap: 6px; font-size: 14px; min-width: 0; }
.hc-who b { color: var(--text-primary); max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hc-who .muted { font-size: 12px; color: var(--text-muted); }
.hc-where { font-size: 12px; color: var(--text-secondary); white-space: nowrap; }
.hc-state {
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  white-space: nowrap;
}
.hc-state.ringing { background: rgba(245, 158, 11, 0.15); color: var(--warning, #f59e0b); }
.hc-state.answered, .hc-state.dialing { background: var(--success-glow, rgba(16, 185, 129, 0.15)); color: var(--success, #10b981); }
.hc-elapsed { font-size: 12px; color: var(--text-muted); white-space: nowrap; }
.hc-actions { display: flex; gap: 8px; margin-left: auto; }
.hc-actions .mini { padding: 5px 14px; font-size: 12px; }
.hc-msg { flex-basis: 100%; font-size: 12px; }
.hc-msg.ok { color: var(--success, #10b981); }
.hc-msg.bad { color: var(--danger, #ef4444); }
@media (max-width: 640px) {
  .home-call { padding: 10px 12px; }
  .hc-actions { margin-left: 0; width: 100%; }
  .hc-actions .mini { flex: 1; }
}
</style>
