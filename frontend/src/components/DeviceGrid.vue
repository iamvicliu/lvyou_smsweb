<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useDevicesStore, useScanStore } from '../stores'
import { useDeviceActions } from '../composables/useDeviceActions'
import { useDetail } from '../composables/useDetail'
import {
  agoText,
  displayName,
  firmwareView,
  groupLabel,
  linkView,
  maskText,
  memoryTone,
  operatorLabel,
  prettyTime,
  rebootText,
  signalBars,
  signalHint,
  simTone,
  simToneHint,
  uptimeShort
} from '../utils/format'

const props = defineProps({
  devices: { type: Array, default: () => [] },
  selectedIds: { type: Array, default: () => [] },
  latestFirmware: { type: String, default: '' }
})

const emit = defineEmits(['toggle-select', 'show-detail', 'rename', 'set-group', 'delete', 'reorder', 'move-up', 'move-down'])

const { scanning } = storeToRefs(useScanStore())
const { startScanAdd } = useDeviceActions()
const { showDetail } = useDetail()
const router = useRouter()

const dragDevice = ref(null)
// Drag is a plain reorder: which side of the hovered card decides where the
// card lands, so there is no separate "sort mode" to toggle any more.
const dropTarget = ref(null)

function isSelected(id) {
  return props.selectedIds.includes(id)
}

function openDetail(device) {
  showDetail(device)
}

function handleDragStart(e, device) {
  dragDevice.value = device
  e.dataTransfer.effectAllowed = 'move'
  e.target.classList.add('dragging')
}

function handleDragEnd(e) {
  e.target.classList.remove('dragging')
  dragDevice.value = null
  dropTarget.value = null
}

function handleDragOver(e, device) {
  if (!dragDevice.value || dragDevice.value.id === device.id) return
  e.preventDefault()
  e.dataTransfer.dropEffect = 'move'
  const rect = e.currentTarget.getBoundingClientRect()
  const after = (e.clientX - rect.left) > rect.width / 2
  dropTarget.value = { id: device.id, after }
}

function handleDragLeave(e) {
  if (dropTarget.value && dropTarget.value.id === e.currentTarget.dataset.id) {
    dropTarget.value = null
  }
}

function handleDrop(e, targetDevice) {
  e.preventDefault()
  const from = dragDevice.value
  const target = dropTarget.value
  if (from && target && from.id !== targetDevice.id) {
    emit('reorder', from, targetDevice, target.after)
  }
  dragDevice.value = null
  dropTarget.value = null
}

function dropClass(id) {
  const t = dropTarget.value
  if (!t || t.id !== id) return ''
  return t.after ? 'drop-after' : 'drop-before'
}

// 卡片上只放一行：链路结论 + 开机时长 + 剩余内存。数据来自面板已经收到的
// 998 心跳和最近一次 stat，不会为了这个去访问板子。
function runtimeText(health) {
  const h = health || {}
  const parts = []
  if (h.uptime >= 0 && h.uptime !== undefined) parts.push('开机 ' + uptimeShort(h.uptime))
  if (h.memory >= 0 && h.memory !== undefined) parts.push('内存 ' + h.memory + '%')
  return parts.join(' · ')
}

function runtimeHint(health) {
  const h = health || {}
  if (!h.at) return '还没有读取过运行信息；打开详情或点「刷新数据」会读一次'
  return `最近一次读取在 ${agoText(h.age)}，来自板子的 stat 状态`
}

function fwOf(device) {
  return firmwareView(device.firmwareVersion, props.latestFirmware)
}

function rbOf(device) {
  return rebootText(device.link_health)
}

function unreadOf(device) {
  const u = device.unread || {}
  return { sms: Number(u.sms || 0), missed: Number(u.missed || 0) }
}

function simOf(device, slot) {
  const s = (device.sims && device.sims['sim' + slot]) || {}
  return {
    number: s.number || '',
    operator: s.operator || '',
    signal: Number(s.signal || 0)
  }
}

function openRecords(kind, device) {
  router.push({
    path: kind === 'sms' ? '/messages' : '/calls',
    query: { device: String(device.id) }
  })
}
</script>

<template>
  <div class="cards-grid">
    <div v-if="devices.length === 0" class="empty-state">
      <div class="empty-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M4 6h18V4H4c-1.1 0-2 .9-2 2v11H0v3h14v-3H4V6z"/></svg>
      </div>
      <p>还没有板子。点下面的按钮，在局域网里搜一遍。</p>
      <button class="empty-btn" @click="startScanAdd" :disabled="scanning">
        {{ scanning ? '搜索中...' : '查找板子' }}
      </button>
    </div>

    <div
      v-for="d in devices"
      :key="d.id"
      class="device-card"
      :class="[
        {
          selected: isSelected(d.id),
          offline: d.status !== 'online'
        },
        dropClass(d.id)
      ]"
      :data-id="d.id"
      draggable="true"
      @click="openDetail(d)"
      @dragstart="handleDragStart($event, d)"
      @dragend="handleDragEnd"
      @dragover="handleDragOver($event, d)"
      @dragleave="handleDragLeave"
      @drop="handleDrop($event, d)"
    >
      <div class="card-header">
        <div class="card-checkbox" @click.stop="emit('toggle-select', d.id)">
          <span :class="['checkbox', { checked: isSelected(d.id) }]">✓</span>
        </div>
        <div class="card-badges">
          <button
            v-if="unreadOf(d).sms"
            class="unread-badge sms"
            :title="`有 ${unreadOf(d).sms} 条新收到的短信，点开查看`"
            @click.stop="openRecords('sms', d)"
          >{{ unreadOf(d).sms }} 条新短信</button>
          <button
            v-if="unreadOf(d).missed"
            class="unread-badge missed"
            :title="`有 ${unreadOf(d).missed} 个未接来电，点开查看`"
            @click.stop="openRecords('calls', d)"
          >{{ unreadOf(d).missed }} 未接</button>
        </div>
        <div class="card-status" :class="d.status">
          {{ d.status === 'online' ? '在线' : '离线' }}
        </div>
      </div>

      <div class="card-body">
        <div class="device-name">{{ displayName(d) }}</div>
        <div class="device-ip">{{ d.ip }}</div>
        <div class="device-mac">{{ d.mac || '-' }}</div>

        <div class="link-row">
          <span
            class="link-chip"
            :class="linkView(d.link_health).tone"
            :title="linkView(d.link_health).hint"
          >{{ linkView(d.link_health).label }}</span>
          <span
            v-if="runtimeText(d.runtime_health)"
            class="runtime-text"
            :class="memoryTone((d.runtime_health || {}).memory)"
            :title="runtimeHint(d.runtime_health)"
          >{{ runtimeText(d.runtime_health) }}</span>
        </div>

        <!-- 两个卡槽固定各占一行：缺卡也保留占位，卡片高度才不会一高一低。 -->
        <div class="sims-info">
          <div v-for="slot in [1, 2]" :key="slot" class="sim-item">
            <span class="sim-label">SIM{{ slot }}</span>
            <span
              :class="['sim-op', simTone(simOf(d, slot).operator)]"
              :title="simToneHint(simOf(d, slot).operator)"
            >{{ operatorLabel(simOf(d, slot).operator) || '无卡' }}</span>
            <span
              v-if="simOf(d, slot).signal > 0"
              class="sim-bars"
              :class="'lv' + signalBars(simOf(d, slot).signal)"
              :title="signalHint(simOf(d, slot).signal)"
            >
              <i v-for="n in 4" :key="n" :class="{ on: n <= signalBars(simOf(d, slot).signal) }"></i>
            </span>
            <span class="sim-num">{{ simOf(d, slot).number ? maskText(simOf(d, slot).number) : '—' }}</span>
          </div>
        </div>

        <div class="facts-row">
          <span
            class="fact"
            :class="fwOf(d).tone"
            :title="fwOf(d).hint"
          >固件 {{ fwOf(d).label }}</span>
          <span
            class="fact"
            :class="rbOf(d).tone"
            :title="rbOf(d).hint"
          >{{ rbOf(d).label }}</span>
        </div>

        <div class="device-meta">
          <span class="device-group" title="设备分组">{{ groupLabel(d.grp) }}</span>
          <span class="device-time" title="面板最后一次收到这块板子消息的时间">
            {{ prettyTime(d.lastSeen) }}
          </span>
        </div>
      </div>

      <div class="card-actions">
        <button class="card-btn touch-sort" @click.stop="emit('move-up', d)" title="上移" aria-label="上移">↑</button>
        <button class="card-btn touch-sort" @click.stop="emit('move-down', d)" title="下移" aria-label="下移">↓</button>
        <button class="card-btn" @click.stop="showDetail(d)" title="详情" aria-label="详情">
          <svg viewBox="0 0 20 20" fill="currentColor"><path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/><path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"/></svg>
        </button>
        <button class="card-btn" @click.stop="emit('rename', d)" title="改名" aria-label="改名">
          <svg viewBox="0 0 20 20" fill="currentColor"><path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"/></svg>
        </button>
        <button class="card-btn" @click.stop="emit('set-group', d)" title="分组" aria-label="分组">
          <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M17.707 9.293a1 1 0 010 1.414l-7 7a1 1 0 01-1.414 0l-7-7A.997.997 0 012 10V5a3 3 0 013-3h5c.256 0 .512.098.707.293l7 7zM5 6a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"/></svg>
        </button>
        <button class="card-btn danger" @click.stop="emit('delete', d)" title="删除" aria-label="删除">
          <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>
        </button>
      </div>

    </div>
  </div>
</template>

<style scoped>
.device-card {
  position: relative;
  cursor: grab;
}
.device-card:active { cursor: grabbing; }
.device-card.dragging { opacity: 0.5; transform: scale(0.95); }
.device-card.drop-before,
.device-card.drop-after { border-color: var(--primary); }
/* Insertion marker: the card slides in on the side the cursor is on. */
.device-card.drop-before::before,
.device-card.drop-after::after {
  content: '';
  position: absolute;
  top: 10px;
  bottom: 10px;
  width: 3px;
  border-radius: 2px;
  background: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-glow);
}
.device-card.drop-before::before { left: -9px; }
.device-card.drop-after::after { right: -9px; }
/* Touch devices cannot drag HTML5 cards, so they get arrows instead. */
.touch-sort { display: none; }
@media (hover: none) { .touch-sort { display: inline-flex; } }

/* 一行元数据：链路状态用点 + 文字，运行指标跟在后面。 */
.link-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin: -6px 0 10px;
  font-size: 11px;
  line-height: 1.3;
}
.link-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--text-muted);
  white-space: nowrap;
}
.link-chip::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
  flex-shrink: 0;
}
.link-chip.ok { color: var(--success); }
.link-chip.ok::before { background: var(--success); }
.link-chip.late { color: var(--warning); }
.link-chip.late::before { background: var(--warning); }
.link-chip.down { color: var(--danger); }
.link-chip.down::before { background: var(--danger); }
.runtime-text {
  color: var(--text-muted);
  white-space: nowrap;
  border-left: 1px solid var(--border);
  padding-left: 8px;
}
.runtime-text.warn { color: var(--warning); }
.runtime-text.bad { color: var(--danger); }

.card-badges {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  margin-right: 8px;
  min-width: 0;
}
.unread-badge {
  border: none;
  cursor: pointer;
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
  padding: 4px 8px;
  border-radius: 999px;
  white-space: nowrap;
  background: var(--danger-glow);
  color: var(--danger);
}
.unread-badge.missed { background: var(--warning-glow); color: var(--warning); }
.unread-badge:hover { filter: brightness(1.08); }

/* 四格信号：细条比百分比更快读，精确数值放在 tooltip 里。 */
.sim-bars { display: inline-flex; align-items: flex-end; gap: 2px; height: 11px; flex-shrink: 0; }
.sim-bars i {
  width: 3px;
  border-radius: 1px;
  background: var(--border);
  display: block;
}
.sim-bars i:nth-child(1) { height: 4px; }
.sim-bars i:nth-child(2) { height: 6px; }
.sim-bars i:nth-child(3) { height: 8px; }
.sim-bars i:nth-child(4) { height: 11px; }
.sim-bars i.on { background: var(--success); }
.sim-bars.lv1 i.on { background: var(--danger); }
.sim-bars.lv2 i.on { background: var(--warning); }

.facts-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: nowrap;
  font-size: 11px;
  color: var(--text-muted);
  margin: -2px 0 8px;
  overflow: hidden;
}
.fact { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.fact.ok { color: var(--success); }
.fact.warn { color: var(--warning); }
</style>
