<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal detail-modal">
      <div class="modal-header">
        <div class="header-main">
          <h3>{{ device.alias || device.devId || device.ip }}</h3>
          <span :class="['pill', device.status]">{{ device.status === 'online' ? '在线' : '离线' }}</span>
        </div>
        <button class="modal-close" @click="emit('close')">×</button>
      </div>

      <div class="modal-body">
        <div class="identity">
          <div class="id-cell"><span>设备 ID</span><b class="mono">{{ device.devId || '-' }}</b></div>
          <div class="id-cell"><span>IP</span><b class="mono">{{ device.ip }}</b></div>
          <div class="id-cell"><span>MAC</span><b class="mono">{{ device.mac || '-' }}</b></div>
          <div class="id-cell"><span>分组</span><b>{{ device.grp || 'auto' }}</b></div>
        </div>

        <section class="block">
          <div class="block-head">
            <h4>线路</h4>
            <div class="head-actions">
              <span v-if="health" class="firmware mono">{{ health.firmware || '-' }}</span>
              <button class="btn-secondary mini" :disabled="healthLoading" @click="loadHealth">
                {{ healthLoading ? '读取中…' : '刷新状态' }}
              </button>
            </div>
          </div>

          <p v-if="healthError" class="msg bad">{{ healthError }}</p>

          <div class="slot-row">
            <div v-for="slot in slotViews" :key="slot.slot" class="slot-card">
              <div class="slot-head">
                <span class="slot-name">卡槽 {{ slot.slot }}</span>
                <span :class="['tag', slotTone(slot.state)]">{{ slotStateLabel(slot.state) }}</span>
              </div>

              <input
                :value="slot.number"
                class="form-input slot-input"
                maxlength="32"
                :placeholder="`卡槽 ${slot.slot} 号码或备注`"
                @input="onNumberInput(slot.slot, $event.target.value)"
              />

              <div class="slot-facts">
                <span class="truncate" :title="slot.operator">{{ slot.operator || '运营商未知' }}</span>
                <span>信号 {{ slot.signal >= 0 ? slot.signal + '%' : '-' }}</span>
                <span>联网 {{ netLabel(slot) }}</span>
              </div>

              <div class="slot-actions">
                <button class="btn-secondary mini" :disabled="busy" @click="slotRestart(slot)">重启</button>
                <button class="btn-secondary mini" :disabled="busy" @click="slotPower(slot)">
                  {{ slot.state === 'POWOFF' ? '通电' : '断电' }}
                </button>
                <button class="btn-secondary mini" :disabled="busy" @click="slotNet(slot)">
                  联网{{ slot.net_mode === 'on' ? '关' : '开' }}
                </button>
              </div>
            </div>
          </div>

          <div class="save-row">
            <span class="hint">纯号码会同步给板子；中英文只存面板做备注。</span>
            <button class="btn-confirm" :disabled="loading" @click="emit('save')">保存号码 / 备注</button>
          </div>
        </section>

        <section class="block">
          <div class="block-head">
            <h4>运行状态</h4>
            <span class="hint">仅打开时读取一次</span>
          </div>
          <div v-if="health" class="stat-grid">
            <div class="stat"><span>运行时长</span><b>{{ uptimeLabel(health.uptime) }}</b></div>
            <div class="stat">
              <span>剩余内存</span>
              <b :style="{ color: memColor(health.memory) }">{{ health.memory >= 0 ? health.memory + '%' : '-' }}</b>
            </div>
            <div class="stat"><span>联网通道</span><b>{{ channelLabel(health.net_channel) }}</b></div>
            <div class="stat">
              <span>WiFi</span>
              <b class="truncate" :title="(health.wifi && health.wifi.ssid) || ''">
                {{ (health.wifi && health.wifi.ssid) || '-' }}
                <template v-if="health.wifi && health.wifi.signal >= 0"> · {{ health.wifi.signal }}%</template>
              </b>
            </div>
            <div class="stat">
              <span>每日重启</span>
              <b>{{ health.daily_restart_enabled ? health.daily_restart_hour + ':00 前后' : '已关闭' }}</b>
            </div>
            <div class="stat"><span>信号 / 卡槽</span><b>{{ onlineSlotsText }}</b></div>
          </div>
          <p v-else class="hint">{{ healthLoading ? '正在读取一次状态…' : '还没读取状态，点上方「刷新状态」。' }}</p>
        </section>

        <section class="block">
          <div class="block-head">
            <h4>维护</h4>
          </div>
          <div class="maint-grid">
            <div class="maint-card">
              <div class="maint-title">每日定时重启</div>
              <div class="daily-row">
                <label class="switch">
                  <input v-model="dailyEnabled" type="checkbox" :disabled="busy" />
                  <span>{{ dailyEnabled ? '开启' : '关闭' }}</span>
                </label>
                <select v-model.number="dailyHour" class="form-input hour-select" :disabled="busy || !dailyEnabled">
                  <option v-for="h in 24" :key="h" :value="h - 1">{{ String(h - 1).padStart(2, '0') }}:00 后</option>
                </select>
                <button class="btn-secondary mini" :disabled="busy" @click="applyDaily">应用</button>
              </div>
              <p class="hint">开机满 4 小时后才触发，分钟数由板子随机错开。</p>
            </div>

            <div class="maint-card">
              <div class="maint-title">快速拨打</div>
              <div class="quick-row">
                <input
                  ref="phoneInput"
                  v-model="phoneDraft"
                  class="form-input"
                  list="detail-phone-list"
                  inputmode="tel"
                  placeholder="我的手机号，填一次就记住"
                  @blur="commitPhone"
                  @keyup.enter="commitPhone"
                />
                <button class="btn-secondary mini" :disabled="loading || !phoneDraft" @click="dialMine(1)">卡1</button>
                <button class="btn-secondary mini" :disabled="loading || !phoneDraft" @click="dialMine(2)">卡2</button>
              </div>
              <div v-if="savedPhones.length" class="saved-row">
                <button
                  v-for="phone in savedPhones.slice(0, 4)"
                  :key="phone"
                  type="button"
                  class="saved-chip"
                  :title="phone"
                  @click="phoneDraft = phone"
                >{{ maskPhone(phone) }}</button>
              </div>
              <p class="hint">来电显示的号码就是这张卡的本机号；20 秒自动挂断。号码和首页收发共用一份。</p>
            </div>
          </div>

          <datalist id="detail-phone-list">
            <option v-for="phone in savedPhones" :key="phone" :value="phone"></option>
          </datalist>

          <button class="btn-secondary reboot" :disabled="busy" @click="reboot">立即重启开发板</button>
          <p class="hint">重启期间短信和来电中断，约 1-2 分钟恢复。</p>

          <p v-if="message" :class="['msg', messageOk ? 'ok' : 'bad']">{{ message }}</p>
        </section>
      </div>

      <div class="modal-footer">
        <button class="btn-cancel" @click="emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import {
  controlSimSlot,
  fetchDeviceHealth,
  rebootDevice,
  saveDailyRestart
} from '../api/endpoints'
import { operatorLabel } from '../utils/format'

const props = defineProps({
  detail: { type: Object, required: true },
  loading: { type: Boolean, default: false },
  myPhone: { type: String, default: '' },
  savedPhones: { type: Array, default: () => [] }
})

const emit = defineEmits([
  'close', 'save', 'update-sim1', 'update-sim2',
  'update-myphone', 'quick-dial'
])

const device = computed(() => props.detail.device || {})

const health = ref(null)
const healthLoading = ref(false)
const healthError = ref('')
const phoneInput = ref(null)
const phoneDraft = ref(props.myPhone || '')

// The input is a draft committed on blur / quick-dial: writing every keystroke
// into the shared phone book would reshuffle it mid-typing.
watch(() => props.myPhone, value => {
  const el = phoneInput.value
  if (el && document.activeElement === el) return
  phoneDraft.value = value || ''
})

function commitPhone() {
  const value = String(phoneDraft.value || '').trim()
  if (value !== String(props.myPhone || '').trim()) emit('update-myphone', value)
}

function dialMine(slot) {
  const value = String(phoneDraft.value || '').trim()
  if (value) emit('update-myphone', value)
  emit('quick-dial', slot)
}

const maskPhone = phone => {
  const value = String(phone || '')
  return value.length > 7 ? `${value.slice(0, 3)}****${value.slice(-4)}` : value
}
const busy = ref(false)
const message = ref('')
const messageOk = ref(true)
const dailyEnabled = ref(true)
const dailyHour = ref(4)
const dailyTouched = ref(false)

const SLOT_STATE_LABELS = {
  OK: '正常', NS: '搜网中', PIN: '需PIN码', LT: '受限服务',
  NOSIM: '未检测到卡', POWOFF: '已断电'
}

function slotStateLabel(state) {
  return SLOT_STATE_LABELS[state] || state || '状态未知'
}

function slotTone(state) {
  if (state === 'OK') return 'ok'
  if (state === 'NS') return 'warn'
  return 'miss'
}

// The cards always render both slots, so an offline board still shows the
// numbers the operator typed into the panel.
const slotViews = computed(() => {
  const deviceNumbers = [device.value.sim1number || '', device.value.sim2number || '']
  const deviceOperators = [device.value.sim1operator || '', device.value.sim2operator || '']
  const live = health.value && health.value.slots ? health.value.slots : []
  return [1, 2].map((slot) => {
    const row = live.find(item => item.slot === slot)
    return {
      slot,
      state: row ? row.state : '',
      signal: row ? row.signal : -1,
      operator: operatorLabel(row ? row.operator : deviceOperators[slot - 1]),
      number: row ? row.number : deviceNumbers[slot - 1],
      net_mode: row ? row.net_mode : '',
      net_enabled: row ? row.net_enabled : null
    }
  })
})

const onlineSlotsText = computed(() => {
  if (!health.value || !health.value.slots) return '-'
  const ok = health.value.slots.filter(s => s.state === 'OK').length
  return `${ok} / ${health.value.slots.length} 正常`
})

function onNumberInput(slot, value) {
  emit(slot === 1 ? 'update-sim1' : 'update-sim2', value)
}

function netLabel(slot) {
  if (slot.net_mode === 'on') return '开'
  if (slot.net_mode === 'off') return '关'
  if (slot.net_mode === 'auto') return '自动'
  if (slot.net_enabled === null || slot.net_enabled === undefined) return '-'
  return slot.net_enabled ? '开' : '关'
}

function uptimeLabel(minutes) {
  const m = Number(minutes)
  if (!Number.isFinite(m) || m < 0) return '-'
  if (m < 60) return m + ' 分钟'
  const d = Math.floor(m / 1440)
  const h = Math.floor((m % 1440) / 60)
  if (d) return `${d} 天 ${h} 小时`
  return `${h} 小时 ${m % 60} 分钟`
}

function memColor(value) {
  const v = Number(value)
  if (!Number.isFinite(v) || v < 0) return 'var(--text-secondary)'
  if (v < 20) return 'var(--danger)'
  if (v < 40) return 'var(--warning)'
  return 'var(--success)'
}

function channelLabel(channel) {
  return { 0: 'WiFi', 1: 'SIM1', 2: 'SIM2' }[channel] ?? '-'
}

function failText(e) {
  const detail = e && e.response && e.response.data && e.response.data.detail
  return detail || (e && e.message) || '操作失败'
}

async function loadHealth() {
  healthLoading.value = true
  healthError.value = ''
  try {
    const data = await fetchDeviceHealth(device.value.id)
    if (!data || data.ok === false) {
      health.value = null
      healthError.value = '板子没有返回状态：' + ((data && data.error) || '未知原因')
      return
    }
    health.value = data
    if (!dailyTouched.value) {
      dailyEnabled.value = data.daily_restart_enabled
      dailyHour.value = data.daily_restart_hour >= 0 ? data.daily_restart_hour : 4
    }
  } catch (e) {
    health.value = null
    healthError.value = '读取状态失败：' + failText(e)
  } finally {
    healthLoading.value = false
  }
}

// Health reads use one stat call, so schedule a single follow-up read instead
// of polling while the slot settles.
function refreshLater(delay = 6000) {
  setTimeout(() => { loadHealth() }, delay)
}

async function slotRestart(slot) {
  if (!confirm(`重启卡槽 ${slot.slot}？正在通话或发短信会被打断，大约 30 秒恢复。`)) return
  busy.value = true
  message.value = ''
  try {
    const r = await controlSimSlot(device.value.id, slot.slot, 'restart')
    messageOk.value = !!r.ok
    message.value = r.ok ? `已下发重启卡槽 ${slot.slot}。` : `板子拒绝：${r.note || '未知原因'}`
    if (r.ok) refreshLater()
  } catch (e) {
    messageOk.value = false
    message.value = '重启卡槽失败：' + failText(e)
  } finally {
    busy.value = false
  }
}

async function slotPower(slot) {
  const turningOff = slot.state !== 'POWOFF'
  const tip = turningOff
    ? `关闭卡槽 ${slot.slot} 电源？关闭后这张卡不能用，需要回来手动通电。`
    : `给卡槽 ${slot.slot} 通电？`
  if (!confirm(tip)) return
  busy.value = true
  message.value = ''
  try {
    const r = await controlSimSlot(device.value.id, slot.slot, 'power', !turningOff)
    messageOk.value = !!r.ok
    message.value = r.ok ? `卡槽 ${slot.slot} 已${turningOff ? '断电' : '通电'}。` : `板子拒绝：${r.note || '未知原因'}`
    if (r.ok) refreshLater()
  } catch (e) {
    messageOk.value = false
    message.value = '操作卡槽电源失败：' + failText(e)
  } finally {
    busy.value = false
  }
}

async function slotNet(slot) {
  const turningOn = slot.net_mode !== 'on'
  if (!confirm(`卡槽 ${slot.slot} ${turningOn ? '开启' : '关闭'}联网？${turningOn ? '' : '关掉后这张卡收不到短信和来电。'}`)) return
  busy.value = true
  message.value = ''
  try {
    const r = await controlSimSlot(device.value.id, slot.slot, 'net', turningOn)
    messageOk.value = !!r.ok
    message.value = r.ok ? `卡槽 ${slot.slot} 联网已${turningOn ? '开启' : '关闭'}。` : `板子拒绝：${r.note || '未知原因'}`
    if (r.ok) refreshLater()
  } catch (e) {
    messageOk.value = false
    message.value = '操作卡槽联网失败：' + failText(e)
  } finally {
    busy.value = false
  }
}

async function applyDaily() {
  busy.value = true
  message.value = ''
  try {
    const r = await saveDailyRestart(device.value.id, dailyEnabled.value, dailyHour.value)
    messageOk.value = !!r.ok
    message.value = r.ok
      ? (dailyEnabled.value ? `每日 ${dailyHour.value}:00 后重启已生效。` : '每日定时重启已关闭。')
      : `板子拒绝：${r.note || '未知原因'}`
    dailyTouched.value = false
    if (r.ok) refreshLater(2000)
  } catch (e) {
    messageOk.value = false
    message.value = '设置定时重启失败：' + failText(e)
  } finally {
    busy.value = false
  }
}

async function reboot() {
  if (!confirm('现在重启这块板子？重启期间短信和来电会中断，约 1-2 分钟恢复。')) return
  busy.value = true
  message.value = ''
  try {
    const r = await rebootDevice(device.value.id, 5)
    messageOk.value = !!r.ok
    message.value = r.ok ? '已下发重启，5 秒后开始。' : `板子拒绝：${r.note || '未知原因'}`
  } catch (e) {
    messageOk.value = false
    message.value = '重启失败：' + failText(e)
  } finally {
    busy.value = false
  }
}

onMounted(() => {
  if (device.value.id) loadHealth()
})
</script>

<style scoped>
.detail-modal { max-width: 720px; }
.detail-modal .modal-footer { justify-content: flex-end; }
.detail-modal .modal-footer .btn-cancel { flex: 0 0 auto; min-width: 96px; }
.header-main { display: flex; align-items: center; gap: 10px; min-width: 0; }
.header-main h3 { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pill {
  padding: 2px 8px; border-radius: 999px; font-size: 11px; white-space: nowrap;
  background: var(--bg-input); color: var(--text-muted); border: 1px solid var(--border);
}
.pill.online { color: var(--success); border-color: rgba(16, 185, 129, 0.4); }
.identity {
  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px;
  padding-bottom: 14px; border-bottom: 1px solid var(--border);
}
.id-cell { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.id-cell span { font-size: 11px; color: var(--text-muted); }
.id-cell b { font-size: 12px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.block { border-top: 1px solid var(--border); padding-top: 14px; display: flex; flex-direction: column; gap: 10px; }
.block:first-of-type { border-top: none; padding-top: 0; }
.block-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.block-head .hint { min-width: 0; }
.block h4 { font-size: 13px; font-weight: 600; }
.head-actions { display: flex; align-items: center; gap: 8px; }
.firmware { font-size: 11px; color: var(--text-muted); }
.slot-row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.slot-card {
  display: flex; flex-direction: column; gap: 8px; padding: 12px;
  background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius-md);
  min-width: 0;
}
.slot-head { display: flex; align-items: center; justify-content: space-between; }
.slot-name { font-weight: 600; font-size: 13px; }
.slot-input { padding: 7px 10px; font-size: 13px; }
.slot-facts { display: flex; flex-wrap: wrap; gap: 4px 10px; font-size: 12px; color: var(--text-secondary); }
.slot-actions { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }
.slot-actions .btn-secondary { padding: 6px 4px; font-size: 12px; white-space: nowrap; }
.save-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.save-row .hint { flex: 1; }
.stat-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.stat {
  display: flex; flex-direction: column; gap: 3px; padding: 9px 11px;
  background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius-md);
  min-width: 0;
}
.stat span { font-size: 11px; color: var(--text-muted); }
.stat b { font-size: 13px; font-weight: 500; }
.maint-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.maint-card {
  display: flex; flex-direction: column; gap: 8px; padding: 12px;
  background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius-md);
  min-width: 0;
}
.maint-title { font-size: 12px; font-weight: 600; }
.daily-row, .quick-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.switch { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-secondary); }
.hour-select { width: auto; min-width: 110px; padding: 7px 10px; font-size: 13px; }
.quick-row .form-input { flex: 1; min-width: 130px; padding: 7px 10px; font-size: 13px; }
.saved-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.saved-chip {
  background: var(--bg-card); border: 1px solid var(--border);
  color: var(--text-secondary); border-radius: 999px;
  padding: 4px 10px; font-size: 11px; cursor: pointer;
  font-family: 'JetBrains Mono', 'SF Mono', ui-monospace, monospace;
}
.saved-chip:hover { border-color: var(--primary); color: var(--primary); }
.reboot { border-color: rgba(239, 68, 68, 0.45); color: var(--danger); }
.mini { padding: 6px 12px; font-size: 12px; border-radius: 8px; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; white-space: nowrap; }
.tag.ok { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.tag.warn { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.tag.miss { background: rgba(239, 68, 68, 0.15); color: #f87171; }
.hint { font-size: 12px; color: var(--text-muted); line-height: 1.5; }
.msg { font-size: 12px; line-height: 1.5; }
.msg.ok { color: var(--success); }
.msg.bad { color: var(--danger); }
.truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 640px) {
  .identity { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .slot-row, .stat-grid, .maint-grid { grid-template-columns: 1fr; }
  .save-row { flex-direction: column; align-items: stretch; }
}
</style>
