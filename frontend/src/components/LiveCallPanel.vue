<template>
  <div v-if="calls.length" class="live-panel">
    <div class="live-head">
      <span class="live-dot" />
      <strong>正在通话</strong>
      <span class="muted">这些是板子当前的电话线路，在面板上接听、挂断、放语音或按键</span>
    </div>

    <div v-for="call in calls" :key="call.id" class="live-card">
      <div class="live-main">
        <div class="live-info">
          <span class="live-device">{{ call.device_name }} · 卡槽 {{ call.slot }}</span>
          <span class="live-phone mono">{{ call.phone || '未知号码' }}</span>
        </div>
        <div class="live-state">
          <span :class="['tag', call.state === 'answered' ? 'ok' : 'warn']">{{ stateLabel(call) }}</span>
          <span :class="['policy', policyTone(call)]">{{ policyLabel(call) }}</span>
          <span class="muted mono">{{ elapsedLabel(call) }}</span>
        </div>
      </div>

      <div class="live-actions">
        <button
          v-if="call.state === 'ringing' && policyMode(call) !== 0"
          class="btn-secondary mini"
          :disabled="isBusy(call)"
          @click="pauseAutoAnswer(call)"
        >改为人工接管</button>
        <button
          v-if="policyMode(call) === 0 && pausedMode(call)"
          class="btn-secondary mini"
          :disabled="isBusy(call)"
          @click="resumeAutoAnswer(call)"
        >恢复自动接听</button>
        <button
          v-if="call.state === 'ringing'"
          class="btn-confirm mini"
          :disabled="isBusy(call)"
          @click="send(call, 'answer')"
        >接听</button>
        <button class="btn-secondary mini danger" :disabled="isBusy(call)" @click="send(call, 'hangup')">挂断</button>
        <button
          v-if="call.state === 'answered'"
          class="btn-secondary mini"
          :disabled="isBusy(call)"
          @click="toggleRecord(call)"
        >{{ recording[call.id] ? '停止录音' : '开始录音' }}</button>
        <span v-if="status[call.id]" :class="['live-msg', status[call.id].ok ? 'ok' : 'bad']">
          {{ status[call.id].text }}
        </span>
      </div>

      <div v-if="call.state === 'answered'" class="live-tools">
        <div class="tool-row">
          <input
            v-model="ttsText[call.id]"
            class="form-input tool-input"
            maxlength="200"
            placeholder="接通后播放的内容，例如：您的快递已放在门口"
          />
          <button class="btn-secondary mini" :disabled="isBusy(call) || !ttsText[call.id]" @click="playTts(call)">播放</button>
          <button class="btn-secondary mini" :disabled="isBusy(call)" @click="send(call, 'stop_tts')">停止语音</button>
        </div>
        <div class="tool-row">
          <input
            v-model="dtmfKeys[call.id]"
            class="form-input tool-input mono"
            maxlength="32"
            placeholder="按键，例如 1 或 1234#"
          />
          <button class="btn-secondary mini" :disabled="isBusy(call) || !dtmfKeys[call.id]" @click="sendKeys(call)">发送按键</button>
          <button class="btn-secondary mini" :disabled="isBusy(call)" @click="send(call, 'clear_keys')">清空按键</button>
        </div>
      </div>
    </div>

    <p class="live-hint">
      面板只下发板子指令，不承载通话音频；要听到对方声音，仍然需要通过板子本身的语音通道。语音播放和录音只能二选一。
      板子自己的自动接听会抢在人工接听之前，想自己接就先把这张卡改成人工接管；改完只影响之后的来电。
    </p>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { controlPhone, fetchAnswerMode, fetchLiveCalls, setAnswerMode } from '../api/endpoints'

const emit = defineEmits(['refresh'])

const calls = ref([])
const busy = reactive({})
const status = reactive({})
const recording = reactive({})
const ttsText = reactive({})
const dtmfKeys = reactive({})
// deviceId -> { "1": {mode, mode_label, ring, paused_mode}, "2": {...} }
const answerModes = reactive({})
const answerLoading = reactive({})

let timer = null

function stateLabel(call) {
  return { ringing: '响铃中', answered: '通话中', dialing: '呼出中' }[call.state] || call.state
}

function elapsedLabel(call) {
  const s = Math.max(0, Number(call.elapsed || 0))
  const m = Math.floor(s / 60)
  return m ? `${m} 分 ${s % 60} 秒` : `${s} 秒`
}

function isBusy(call) {
  return !!busy[call.id]
}

function setStatus(call, ok, text) {
  status[call.id] = { ok, text }
  setTimeout(() => {
    if (status[call.id] && status[call.id].text === text) delete status[call.id]
  }, 6000)
}

function slotPolicy(call) {
  const device = answerModes[call.device_id]
  if (!device) return null
  return device[String(call.slot)] || null
}

function policyMode(call) {
  const policy = slotPolicy(call)
  return policy ? Number(policy.mode) : null
}

function pausedMode(call) {
  const policy = slotPolicy(call)
  return policy && policy.paused_mode != null ? Number(policy.paused_mode) : null
}

function policyLabel(call) {
  const policy = slotPolicy(call)
  if (!policy) return answerLoading[call.device_id] ? '读接听设置…' : '接听设置未知'
  const mode = Number(policy.mode)
  if (mode === 0) return pausedMode(call) ? '人工接管中' : '不自动接听'
  const label = { 1: '自动接听', 2: '自动接听并录音', 3: '自动挂断' }[mode] || '自动接听'
  return `${label}·${policy.ring}声`
}

function policyTone(call) {
  const mode = policyMode(call)
  if (mode === null) return ''
  return mode === 0 ? (pausedMode(call) ? 'manual' : 'idle') : 'auto'
}

async function loadAnswerMode(deviceId, force = false) {
  if (!deviceId) return
  if (answerLoading[deviceId] && !force) return
  answerLoading[deviceId] = true
  try {
    const resp = await fetchAnswerMode(deviceId)
    const data = (resp && resp.data) || {}
    if (data.ok) answerModes[deviceId] = data.slots || {}
  } catch (e) {
    // A board that is busy mid-call may refuse the read; the badge then shows
    // "接听设置未知" instead of claiming the slot is safe to take over.
  } finally {
    answerLoading[deviceId] = false
  }
}

async function pauseAutoAnswer(call) {
  busy[call.id] = true
  try {
    const r = await setAnswerMode(call.device_id, call.slot, 0)
    const data = (r && r.data) || {}
    if (data.ok === false) throw new Error('板子没有接受修改')
    await loadAnswerMode(call.device_id, true)
    setStatus(call, true, '已改为人工接管，这通还在响就可以点接听')
  } catch (e) {
    setStatus(call, false, failText(e))
  } finally {
    busy[call.id] = false
  }
}

async function resumeAutoAnswer(call) {
  const target = pausedMode(call)
  if (!target) return
  busy[call.id] = true
  try {
    const r = await setAnswerMode(call.device_id, call.slot, target)
    const data = (r && r.data) || {}
    if (data.ok === false) throw new Error('板子没有接受修改')
    await loadAnswerMode(call.device_id, true)
    setStatus(call, true, '已恢复原来的自动接听设置')
  } catch (e) {
    setStatus(call, false, failText(e))
  } finally {
    busy[call.id] = false
  }
}

function failText(e) {
  const detail = e && e.response && e.response.data && e.response.data.detail
  return detail || (e && e.message) || '指令没有发出去'
}

async function send(call, action, extra = {}) {
  busy[call.id] = true
  try {
    const r = await controlPhone({
      deviceId: call.device_id,
      slot: call.slot,
      action,
      ...extra
    })
    const ok = !!r.ok
    setStatus(call, ok, ok ? '已下发' : `板子拒绝：${r.note || '未知原因'}`)
    if (ok && action !== 'answer') emit('refresh')
    if (ok && action === 'answer') {
      call.state = 'answered'
      emit('refresh')
    }
    if (ok && action === 'hangup') {
      calls.value = calls.value.filter(item => item.id !== call.id)
    }
    if (ok) load(2000)
  } catch (e) {
    setStatus(call, false, failText(e))
  } finally {
    busy[call.id] = false
  }
}

function playTts(call) {
  return send(call, 'tts', { text: ttsText[call.id] || '' })
}

function sendKeys(call) {
  return send(call, 'dtmf', { keys: dtmfKeys[call.id] || '' })
}

function toggleRecord(call) {
  const next = !recording[call.id]
  recording[call.id] = next
  return send(call, next ? 'start_record' : 'stop_record', { duration: 60 })
}

async function load(delay = 0) {
  if (delay) {
    setTimeout(loadNow, delay)
    return
  }
  loadNow()
}

async function loadNow() {
  try {
    const data = await fetchLiveCalls()
    const items = (data && data.items) || []
    calls.value = items.map(item => {
      const previous = calls.value.find(c => c.id === item.id)
      return previous ? { ...previous, ...item } : item
    })
  } catch {
    // A failed poll is silent: the call list below still refreshes on its own.
  }
}

onMounted(() => {
  loadNow()
  timer = setInterval(loadNow, 5000)
})

// Only fetch board settings for boards that actually have a line open: reading
// them costs one HTTP round trip per board.
watch(
  () => calls.value.map(c => c.device_id).join(','),
  () => {
    const deviceIds = [...new Set(calls.value.map(c => c.device_id))]
    deviceIds.forEach(id => loadAnswerMode(id))
  }
)

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.live-panel {
  margin: 0 0 12px; padding: 14px 16px; border-radius: 12px;
  background: rgba(16, 185, 129, 0.07); border: 1px solid rgba(16, 185, 129, 0.35);
  display: flex; flex-direction: column; gap: 10px;
}
.live-head { display: flex; align-items: center; gap: 8px; font-size: 13px; flex-wrap: wrap; }
.live-dot { width: 8px; height: 8px; border-radius: 50%; background: #34d399; box-shadow: 0 0 0 4px rgba(52, 211, 153, 0.18); }
.live-card { background: var(--bg-card, #111a2e); border: 1px solid var(--border, #253048); border-radius: 10px; padding: 12px; display: flex; flex-direction: column; gap: 10px; }
.live-main { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.live-info { display: flex; flex-direction: column; gap: 2px; }
.live-device { font-size: 12px; color: var(--text-muted, #94a3b8); }
.live-phone { font-size: 16px; font-weight: 600; }
.live-state { display: flex; align-items: center; gap: 10px; }
.live-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.live-actions .btn-confirm, .live-actions .btn-secondary { flex: 0 0 auto; width: auto; }
.live-tools { display: flex; flex-direction: column; gap: 8px; }
.tool-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tool-input { flex: 1; min-width: 200px; padding: 8px 10px; font-size: 13px; }
.live-msg { font-size: 12px; }
.live-msg.ok { color: #34d399; }
.live-msg.bad { color: #f87171; }
.live-hint { font-size: 12px; color: var(--text-muted, #94a3b8); line-height: 1.6; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; }
.tag.ok { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.tag.warn { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.policy {
  display: inline-block; padding: 2px 8px; border-radius: 999px;
  font-size: 11px; border: 1px solid transparent;
}
.policy.auto { color: #fbbf24; border-color: rgba(245, 158, 11, 0.4); background: rgba(245, 158, 11, 0.12); }
.policy.manual { color: #34d399; border-color: rgba(52, 211, 153, 0.4); background: rgba(52, 211, 153, 0.12); }
.policy.idle { color: var(--text-muted, #94a3b8); border-color: var(--border, #253048); }
.mini { padding: 6px 12px; font-size: 12px; border-radius: 8px; }
.danger { border-color: rgba(239, 68, 68, 0.45); color: #f87171; }
.muted { color: var(--text-muted, #94a3b8); }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
</style>
