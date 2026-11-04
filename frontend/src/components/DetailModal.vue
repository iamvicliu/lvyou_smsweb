<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal modal-lg">
      <div class="modal-header">
        <h3>📋 设备详情</h3>
        <button class="modal-close" @click="emit('close')">×</button>
      </div>
      <div class="modal-body">
        <div class="detail-grid">
          <div class="detail-item"><span class="detail-label">设备ID</span><span>{{ device.devId || '-' }}</span></div>
          <div class="detail-item"><span class="detail-label">别名</span><span>{{ device.alias || '-' }}</span></div>
          <div class="detail-item"><span class="detail-label">IP 地址</span><span class="mono">{{ device.ip }}</span></div>
          <div class="detail-item"><span class="detail-label">MAC 地址</span><span class="mono">{{ device.mac || '-' }}</span></div>
          <div class="detail-item"><span class="detail-label">分组</span><span>{{ device.grp || 'auto' }}</span></div>
          <div class="detail-item">
            <span class="detail-label">状态</span>
            <span :class="['status-badge', device.status]">
              {{ device.status === 'online' ? '在线' : '离线' }}
            </span>
          </div>
          <div class="detail-item"><span class="detail-label">SIM1 号码 / 标签</span><span class="mono">{{ device.sim1number || '-' }}</span></div>
          <div class="detail-item"><span class="detail-label">SIM1 运营商</span><span>{{ device.sim1operator || '-' }}</span></div>
          <div class="detail-item"><span class="detail-label">SIM2 号码 / 标签</span><span class="mono">{{ device.sim2number || '-' }}</span></div>
          <div class="detail-item"><span class="detail-label">SIM2 运营商</span><span>{{ device.sim2operator || '-' }}</span></div>
          <div class="detail-item"><span class="detail-label">WiFi 名称</span><span>{{ device.wifiName || '-' }}</span></div>
          <div class="detail-item"><span class="detail-label">信号强度</span><span :style="{ color: wifiDbmColor(device.wifiDbm) }">{{ wifiDbmLabel(device.wifiDbm) }}</span></div>
        </div>

        <div class="sim-edit-section">
          <div class="section-head">
            <p class="sim-edit-title">运行状态</p>
            <button class="btn-secondary mini" :disabled="healthLoading" @click="loadHealth">
              {{ healthLoading ? '读取中…' : '刷新' }}
            </button>
          </div>

          <p v-if="healthError" class="health-error">{{ healthError }}</p>

          <template v-else-if="health">
            <div class="health-grid">
              <div class="health-item"><span class="detail-label">固件</span><span class="mono">{{ health.firmware || '-' }}</span></div>
              <div class="health-item"><span class="detail-label">运行时长</span><span>{{ uptimeLabel(health.uptime) }}</span></div>
              <div class="health-item">
                <span class="detail-label">剩余内存</span>
                <span :style="{ color: memColor(health.memory) }">{{ health.memory >= 0 ? health.memory + '%' : '-' }}</span>
              </div>
              <div class="health-item"><span class="detail-label">联网通道</span><span>{{ channelLabel(health.net_channel) }}</span></div>
              <div class="health-item"><span class="detail-label">WiFi</span><span>{{ health.wifi.ssid || '-' }} · {{ health.wifi.mode || '-' }}</span></div>
              <div class="health-item">
                <span class="detail-label">每日重启</span>
                <span>{{ health.daily_restart_enabled ? health.daily_restart_hour + ':00 左右' : '已关闭' }}</span>
              </div>
            </div>

            <div class="slot-row">
              <div v-for="slot in health.slots" :key="slot.slot" class="slot-card">
                <div class="slot-head">
                  <span class="slot-name">卡槽 {{ slot.slot }}</span>
                  <span :class="['tag', slotTone(slot.state)]">{{ slotStateLabel(slot.state) }}</span>
                </div>
                <div class="slot-meta">
                  <span>{{ slot.operator || '未知运营商' }}</span>
                  <span class="mono">{{ slot.number || '未知号码' }}</span>
                </div>
                <div class="slot-meta">
                  <span>信号 {{ slot.signal >= 0 ? slot.signal + '%' : '-' }}</span>
                  <span>联网 {{ slot.net_enabled === null ? '-' : (slot.net_enabled ? '开' : '关') }}</span>
                </div>
                <div class="slot-actions">
                  <button class="btn-secondary mini" :disabled="busy" @click="slotRestart(slot.slot)">重启卡槽</button>
                  <button class="btn-secondary mini" :disabled="busy" @click="slotPower(slot)">{{ slot.state === 'POWOFF' ? '通电' : '断电' }}</button>
                  <button class="btn-secondary mini" :disabled="busy" @click="slotNet(slot)">联网{{ slot.net_enabled ? '关' : '开' }}</button>
                </div>
              </div>
            </div>
          </template>
          <p v-else class="sim-edit-hint">{{ healthLoading ? '正在向板子查询一次状态…' : '点击刷新读取板子状态' }}</p>

          <p class="sim-edit-hint">状态来自一次按需查询，不轮询；在线判断仍用板子心跳。断电后卡槽要手动通电才会恢复。</p>
        </div>

        <div class="sim-edit-section">
          <p class="sim-edit-title">整机重启与定时重启</p>
          <div class="daily-row">
            <label class="daily-toggle">
              <input v-model="dailyEnabled" type="checkbox" :disabled="busy" />
              每日定时重启
            </label>
            <select v-model.number="dailyHour" class="form-input hour-select" :disabled="busy || !dailyEnabled">
              <option v-for="h in 24" :key="h" :value="h - 1">{{ String(h - 1).padStart(2, '0') }}:00 后</option>
            </select>
            <button class="btn-secondary mini" :disabled="busy" @click="applyDaily">应用</button>
          </div>
          <div class="sim-edit-actions">
            <button class="btn-secondary reboot" :disabled="busy" @click="reboot">立即重启开发板</button>
          </div>
          <p class="sim-edit-hint">
            定时重启要开机超过 4 小时才会触发，分钟数由板子随机错开。整机重启期间面板会短暂离线，约 1-2 分钟后自动恢复。
          </p>
          <p v-if="message" :class="['health-error', messageOk ? 'ok' : '']">{{ message }}</p>
        </div>

        <div class="sim-edit-section">
          <p class="sim-edit-title">编辑 SIM 卡号</p>
          <input :value="device.sim1number || ''" class="form-input" maxlength="32" placeholder="SIM1 号码或标签，如 138… 或 移动保号" @input="emit('update-sim1', $event.target.value)" />
          <input :value="device.sim2number || ''" class="form-input" maxlength="32" placeholder="SIM2 号码或标签，如 138… 或 giffgaff" @input="emit('update-sim2', $event.target.value)" />
          <div class="sim-edit-actions">
            <button class="btn-confirm" :disabled="loading" @click="emit('save')">保存卡号</button>
          </div>
          <p class="sim-edit-hint">填纯号码会显示为“本机 …”并同步到板子；填中英文会当作标签显示在通知里，只存面板，不写入板子。最多 32 个字符。</p>
        </div>

        <div class="sim-edit-section">
          <p class="sim-edit-title">快速拨打（查这张卡的本机号码）</p>
          <input
            :value="myPhone"
            class="form-input"
            inputmode="tel"
            placeholder="我的手机号，填一次就会记住"
            @input="emit('update-myphone', $event.target.value)"
          />
          <div class="sim-edit-actions">
            <button class="btn-secondary" :disabled="loading || !myPhone" @click="emit('quick-dial', 1)">用卡1打给我</button>
            <button class="btn-secondary" :disabled="loading || !myPhone" @click="emit('quick-dial', 2)">用卡2打给我</button>
          </div>
          <p class="sim-edit-hint">你手机上的来电号码就是这张卡的号码，填到上面点“保存卡号”。通话 20 秒后自动挂断。</p>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn-cancel" @click="emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  controlSimSlot,
  fetchDeviceHealth,
  rebootDevice,
  saveDailyRestart
} from '../api/endpoints'

const props = defineProps({
  detail: { type: Object, required: true },
  loading: { type: Boolean, default: false },
  myPhone: { type: String, default: '' }
})

const emit = defineEmits([
  'close', 'save', 'update-sim1', 'update-sim2',
  'update-myphone', 'quick-dial'
])

const device = computed(() => props.detail.device || {})

const health = ref(null)
const healthLoading = ref(false)
const healthError = ref('')
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
  return SLOT_STATE_LABELS[state] || state || '未知'
}

function slotTone(state) {
  if (state === 'OK') return 'ok'
  if (state === 'NS') return 'warn'
  return 'miss'
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
  if (!confirm(`重启卡槽 ${slot}？正在通话或发短信会被打断，大约 30 秒恢复。`)) return
  busy.value = true
  message.value = ''
  try {
    const r = await controlSimSlot(device.value.id, slot, 'restart')
    messageOk.value = !!r.ok
    message.value = r.ok ? `已下发重启卡槽 ${slot}。` : `板子拒绝：${r.note || '未知原因'}`
    if (r.ok) refreshLater()
  } catch (e) {
    messageOk.value = false
    message.value = '重启卡槽失败：' + failText(e)
  } finally {
    busy.value = false
  }
}

async function slotPower(slotInfo) {
  const turningOff = slotInfo.state !== 'POWOFF'
  const tip = turningOff
    ? `关闭卡槽 ${slotInfo.slot} 电源？关闭后这张卡不能用，需要回来手动通电。`
    : `给卡槽 ${slotInfo.slot} 通电？`
  if (!confirm(tip)) return
  busy.value = true
  message.value = ''
  try {
    const r = await controlSimSlot(device.value.id, slotInfo.slot, 'power', !turningOff)
    messageOk.value = !!r.ok
    message.value = r.ok ? `卡槽 ${slotInfo.slot} 已${turningOff ? '断电' : '通电'}。` : `板子拒绝：${r.note || '未知原因'}`
    if (r.ok) refreshLater()
  } catch (e) {
    messageOk.value = false
    message.value = '操作卡槽电源失败：' + failText(e)
  } finally {
    busy.value = false
  }
}

async function slotNet(slotInfo) {
  const turningOn = !slotInfo.net_enabled
  if (!confirm(`卡槽 ${slotInfo.slot} ${turningOn ? '开启' : '关闭'}联网？`)) return
  busy.value = true
  message.value = ''
  try {
    const r = await controlSimSlot(device.value.id, slotInfo.slot, 'net', turningOn)
    messageOk.value = !!r.ok
    message.value = r.ok ? `卡槽 ${slotInfo.slot} 联网已${turningOn ? '开启' : '关闭'}。` : `板子拒绝：${r.note || '未知原因'}`
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

function wifiDbmColor(dbm) {
  const v = parseInt(dbm, 10)
  if (isNaN(v)) return 'var(--text-secondary)'
  if (v >= 60) return 'var(--success)'
  if (v >= 30) return 'var(--warning)'
  return 'var(--danger)'
}

function wifiDbmLabel(dbm) {
  const v = parseInt(dbm, 10)
  if (isNaN(v) || !dbm) return '-'
  if (v >= 60) return `${dbm} (强)`
  if (v >= 30) return `${dbm} (中)`
  return `${dbm} (弱)`
}

onMounted(() => {
  if (device.value.id) loadHealth()
})
</script>

<style scoped>
.section-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.mini { padding: 6px 12px; font-size: 12px; border-radius: 8px; }
.health-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.health-item { display: flex; flex-direction: column; gap: 3px; padding: 8px 10px; background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius-md); font-size: 13px; }
.slot-row { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.slot-card { display: flex; flex-direction: column; gap: 8px; padding: 12px; background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius-md); }
.slot-head { display: flex; align-items: center; justify-content: space-between; }
.slot-name { font-weight: 600; font-size: 13px; }
.slot-meta { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; color: var(--text-secondary); }
.slot-actions { display: flex; flex-wrap: wrap; gap: 6px; }
.slot-actions .btn-secondary { flex: 1; min-width: 84px; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; }
.tag.ok { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.tag.warn { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.tag.miss { background: rgba(239, 68, 68, 0.15); color: #f87171; }
.daily-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.daily-toggle { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-secondary); }
.hour-select { width: auto; min-width: 130px; padding: 8px 10px; }
.reboot { width: 100%; border-color: rgba(239, 68, 68, 0.45); color: var(--danger); }
.health-error { font-size: 12px; color: var(--danger); line-height: 1.5; }
.health-error.ok { color: var(--success); }
@media (max-width: 640px) {
  .health-grid { grid-template-columns: 1fr; }
  .slot-row { grid-template-columns: 1fr; }
}
</style>
