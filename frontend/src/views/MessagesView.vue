<template>
  <div class="messages-view">
    <AppHeader
      :loading="loading"
      :scanning="false"
      :is-dark="isDark"
      @refresh="load"
      @logout="handleLogout"
      @toggle-theme="toggleTheme"
      @open-settings="$router.push('/settings')"
      @scan="$router.push('/dashboard')"
    />

    <section class="records-panel">
      <div class="panel-head">
        <span class="panel-title">短信记录 <b>{{ mode === 'thread' ? threadTotal : total }}</b></span>
        <div class="mode-switch" role="tablist" aria-label="短信展示方式">
          <button
            :class="{ active: mode === 'list' }"
            role="tab"
            :aria-selected="mode === 'list'"
            @click="setMode('list')"
          >列表</button>
          <button
            :class="{ active: mode === 'thread' }"
            role="tab"
            :aria-selected="mode === 'thread'"
            title="按号码把收发短信归到同一个会话里"
            @click="setMode('thread')"
          >会话</button>
        </div>
        <div class="panel-filters">
          <select v-model="deviceId" class="filter-select" @change="reload">
            <option :value="0">全部设备</option>
            <option v-for="d in devices" :key="d.id" :value="d.id">{{ d.alias || d.devId || d.ip }}</option>
          </select>
          <select v-if="mode === 'list'" v-model="direction" class="filter-select" @change="reload">
            <option value="">全部方向</option>
            <option value="received">收到</option>
            <option value="sent">发出</option>
          </select>
          <input v-model="q" class="search-input" placeholder="搜索号码 / 内容" @keyup.enter="reload" />
        </div>
        <button class="toolbar-btn" @click="reload">查询</button>
        <button
          class="toolbar-btn"
          :disabled="syncing"
          title="让面板马上向每块板子取一次最新短信"
          @click="syncAll"
        >
          {{ syncing ? '同步中…' : '同步最新记录' }}
        </button>
        <button
          class="toolbar-btn"
          :disabled="exporting"
          title="按当前筛选条件导出全部记录（CSV，可用 Excel 打开）"
          @click="exportCsv"
        >
          {{ exporting ? '导出中…' : '导出 CSV' }}
        </button>
      </div>

      <template v-if="mode === 'list'">
        <div class="records-scroll records-table-only">
          <table v-if="items.length" class="records-table">
            <thead>
              <tr>
                <th style="width:170px">时间</th>
                <th style="width:150px">设备</th>
                <th style="width:190px">卡槽</th>
                <th style="width:74px">方向</th>
                <th style="width:140px">号码</th>
                <th>内容</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in items" :key="row.id">
                <td class="muted nowrap">{{ row.sms_time }}</td>
                <td>{{ row.device_name }}</td>
                <td>{{ maskText(simLabel(row.sim_slot, row.sim_number)) }}</td>
                <td>
                  <span :class="['tag', row.direction === 'received' ? 'in' : 'out']">
                    {{ row.direction === 'received' ? '收到' : '发出' }}
                  </span>
                </td>
                <td class="mono nowrap">{{ maskText(row.phone) }}</td>
                <td class="content">
                  <SmsContent
                    :content="row.content"
                    clamp
                    :open="expanded.has(row.id)"
                    @toggle="toggleExpand(row.id)"
                  />
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty-row">{{ loading ? '加载中…' : '暂无短信记录' }}</div>
        </div>

        <div v-if="items.length" class="record-list">
          <div v-for="row in items" :key="'m' + row.id" class="record-item">
            <div class="record-top">
              <span class="record-time">{{ row.sms_time }}</span>
              <span :class="['tag', row.direction === 'received' ? 'in' : 'out']">
                {{ row.direction === 'received' ? '收到' : '发出' }}
              </span>
            </div>
            <div class="record-sub">
              <span>{{ row.device_name }}</span>
              <span class="sep">·</span>
              <span>{{ maskText(simLabel(row.sim_slot, row.sim_number)) }}</span>
              <span class="sep">·</span>
              <span class="mono">{{ maskText(row.phone) }}</span>
            </div>
            <SmsContent
              class="record-body"
              :content="row.content"
              clamp
              :open="expanded.has(row.id)"
              @toggle="toggleExpand(row.id)"
            />
          </div>
        </div>

        <Pagination
          flush
          :page="page"
          :pages="pages"
          :page-size="pageSize"
          :total="total"
          @change="p => { page = p; load() }"
        />
      </template>

      <div v-else class="threads-layout">
        <div class="thread-list" :class="{ 'is-hidden': threadOpenMobile }">
          <button
            v-for="t in threads"
            :key="t.phone || 'unknown'"
            class="thread-row"
            :class="{ active: activePhone === t.phone }"
            @click="openThread(t.phone)"
          >
            <span class="thread-main">
              <span class="thread-phone mono">{{ maskText(t.phone || '未知号码') }}</span>
              <span class="thread-preview">{{ t.last_content || '-' }}</span>
            </span>
            <span class="thread-side">
              <span class="thread-time">{{ t.last_time }}</span>
              <span class="thread-count" :title="`共 ${t.total} 条，其中收到 ${t.received} 条`">{{ t.total }}</span>
            </span>
          </button>
          <div v-if="!threads.length" class="empty-row">{{ loading ? '加载中…' : '暂无短信记录' }}</div>
        </div>

        <div v-if="activePhone !== null" class="thread-panel">
          <div class="thread-head">
            <button class="thread-back" title="返回会话列表" @click="closeThread">←</button>
            <span class="mono">{{ maskText(activePhone || '未知号码') }}</span>
            <span class="thread-head-count">{{ threadItems.length }} 条</span>
          </div>
          <div class="bubbles">
            <div
              v-for="m in threadItems"
              :key="m.id"
              class="bubble-row"
              :class="m.direction === 'received' ? 'in' : 'out'"
            >
              <div class="bubble-meta">{{ m.sms_time }} · {{ m.device_name }} · {{ maskText(simLabel(m.sim_slot, m.sim_number)) }}</div>
              <div class="bubble">{{ m.content }}</div>
            </div>
            <div v-if="!threadItems.length" class="empty-row">{{ threadLoading ? '加载中…' : '这个号码还没有记录' }}</div>
          </div>
        </div>
        <div v-else class="thread-placeholder">点左边的号码，查看这段对话</div>
      </div>

      <Pagination
        v-if="mode === 'thread'"
        flush
        :page="threadPage"
        :pages="threadPages"
        :page-size="threadPageSize"
        :total="threadTotal"
        @change="p => { threadPage = p; loadThreads() }"
      />
    </section>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore, useDevicesStore } from '../stores'
import AppHeader from '../components/AppHeader.vue'
import Pagination from '../components/Pagination.vue'
import SmsContent from '../components/SmsContent.vue'
import {
  fetchSmsHistory,
  fetchSmsThread,
  fetchSmsThreads,
  markRecordsSeen,
  refreshMessages
} from '../api/endpoints'
import { useTheme } from '../composables/useTheme'
import { maskText, simLabel } from '../utils/format'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const devicesStore = useDevicesStore()
const { isDark, toggleTheme } = useTheme()

const loading = ref(false)
const syncing = ref(false)
const exporting = ref(false)
const mode = ref('list')
const q = ref('')
const direction = ref('')
const deviceId = ref(0)
const page = ref(1)
const pageSize = ref(30)
const total = ref(0)
const pages = ref(0)
const items = ref([])
const devices = ref([])
// Long SMS clog the list; three lines by default, one tap opens the whole text.
const expanded = ref(new Set())

const threads = ref([])
const threadPage = ref(1)
const threadPageSize = ref(20)
const threadTotal = ref(0)
const threadPages = ref(0)
const activePhone = ref(null)
const threadItems = ref([])
const threadLoading = ref(false)
const threadOpenMobile = ref(false)

function toggleExpand(id) {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expanded.value = next
}

function setMode(next) {
  mode.value = next
  if (next === 'thread' && !threads.value.length) loadThreads()
}

async function load() {
  loading.value = true
  try {
    const data = await fetchSmsHistory({
      page: page.value,
      pageSize: pageSize.value,
      q: q.value.trim(),
      direction: direction.value,
      deviceId: deviceId.value
    })
    items.value = data.items || []
    total.value = data.total || 0
    pages.value = data.pages || 0
    await markRecordsSeen('sms')
  } finally {
    loading.value = false
  }
}

async function loadThreads() {
  loading.value = true
  try {
    const data = await fetchSmsThreads({
      page: threadPage.value,
      pageSize: threadPageSize.value,
      q: q.value.trim(),
      deviceId: deviceId.value
    })
    threads.value = data.items || []
    threadTotal.value = data.total || 0
    threadPages.value = data.pages || 0
    await markRecordsSeen('sms')
  } finally {
    loading.value = false
  }
}

async function openThread(phone) {
  activePhone.value = phone
  threadOpenMobile.value = true
  threadLoading.value = true
  try {
    const data = await fetchSmsThread({ phone, deviceId: deviceId.value })
    threadItems.value = data.items || []
  } catch {
    threadItems.value = []
  } finally {
    threadLoading.value = false
  }
}

function closeThread() {
  activePhone.value = null
  threadOpenMobile.value = false
  threadItems.value = []
}

function reload() {
  page.value = 1
  threadPage.value = 1
  if (mode.value === 'thread') {
    loadThreads()
    if (activePhone.value !== null) openThread(activePhone.value)
  } else {
    load()
  }
}

async function syncAll() {
  syncing.value = true
  try {
    for (const d of devices.value) {
      try { await refreshMessages(d.id) } catch { /* one dead board must not stop the rest */ }
    }
    await reload()
  } finally {
    syncing.value = false
  }
}

function csvCell(value) {
  const s = String(value ?? '')
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

function saveCsv(name, header, rows) {
  const body = [header, ...rows].map(r => r.map(csvCell).join(',')).join('\r\n')
  // BOM keeps Excel on Windows from mangling Chinese; the file is UTF-8.
  const blob = new Blob(['\uFEFF' + body], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

async function collectAll(fetcher, pageSizeOverride = 200) {
  const out = []
  let p = 1
  let pageCount = 1
  do {
    const data = await fetcher({
      page: p,
      pageSize: pageSizeOverride,
      q: q.value.trim(),
      direction: direction.value,
      deviceId: deviceId.value
    })
    out.push(...(data.items || []))
    pageCount = data.pages || 0
    p += 1
    if (p > 200) break
  } while (p <= pageCount)
  return out
}

async function exportCsv() {
  exporting.value = true
  try {
    const rows = await collectAll(fetchSmsHistory)
    const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, '')
    saveCsv(
      `短信记录-${stamp}.csv`,
      ['时间', '设备', '卡槽', '方向', '号码', '内容'],
      rows.map(r => [
        r.sms_time,
        r.device_name,
        simLabel(r.sim_slot, r.sim_number),
        r.direction === 'received' ? '收到' : '发出',
        r.phone,
        r.content
      ])
    )
  } finally {
    exporting.value = false
  }
}

async function handleLogout() {
  await authStore.logout(true)
  router.push('/login')
}

let timer = null

onMounted(async () => {
  if (!(await authStore.restore())) {
    router.push('/login')
    return
  }
  const preset = Number(route.query.device || 0)
  if (preset) deviceId.value = preset
  await devicesStore.refresh()
  devices.value = devicesStore.devices
  await load()
  timer = setInterval(() => {
    if (mode.value === 'thread') loadThreads()
    else load()
  }, 30000)
})

onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.messages-view { padding: 24px; max-width: 1440px; margin: 0 auto; }
.muted { color: var(--text-muted, #94a3b8); }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; white-space: nowrap; }
.tag.in { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.tag.out { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }

/* 列表 / 会话 切换：两个按钮一组，避免和右侧筛选抢位置。 */
.mode-switch {
  display: inline-flex;
  padding: 2px;
  border-radius: 999px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  flex-shrink: 0;
}
.mode-switch button {
  border: none;
  background: none;
  color: var(--text-secondary);
  font-size: 12px;
  padding: 5px 12px;
  border-radius: 999px;
  cursor: pointer;
}
.mode-switch button.active {
  background: var(--primary);
  color: #fff;
  font-weight: 600;
}

.threads-layout { display: grid; grid-template-columns: minmax(260px, 360px) 1fr; min-height: 420px; }
.thread-list { border-right: 1px solid var(--border); overflow-y: auto; max-height: 62vh; }
.thread-row {
  display: flex;
  width: 100%;
  gap: 10px;
  padding: 12px 16px;
  border: none;
  border-bottom: 1px solid var(--border);
  background: none;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.thread-row:hover { background: var(--bg-card-hover); }
.thread-row.active { background: var(--primary-glow); }
.thread-main { display: flex; flex-direction: column; gap: 4px; min-width: 0; flex: 1; }
.thread-phone { font-size: 13px; font-weight: 600; }
.thread-preview { font-size: 12px; color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.thread-side { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; flex-shrink: 0; }
.thread-time { font-size: 11px; color: var(--text-muted); white-space: nowrap; }
.thread-count { font-size: 10px; color: var(--text-muted); background: var(--bg-input); border-radius: 999px; padding: 1px 7px; }

.thread-panel { display: flex; flex-direction: column; min-width: 0; max-height: 62vh; }
.thread-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
  font-weight: 600;
}
.thread-back { display: none; border: none; background: none; color: var(--primary); font-size: 16px; cursor: pointer; }
.thread-head-count { margin-left: auto; font-size: 11px; color: var(--text-muted); font-weight: 400; }
.bubbles { padding: 16px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }
.bubble-row { display: flex; flex-direction: column; gap: 4px; max-width: 78%; }
.bubble-row.in { align-self: flex-start; }
.bubble-row.out { align-self: flex-end; align-items: flex-end; }
.bubble-meta { font-size: 10px; color: var(--text-muted); }
.bubble {
  padding: 9px 12px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.5;
  background: var(--bg-input);
  border: 1px solid var(--border);
  white-space: pre-wrap;
  word-break: break-word;
}
.bubble-row.out .bubble { background: var(--primary-glow); border-color: transparent; }
.thread-placeholder { display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-size: 13px; }

@media (max-width: 860px) {
  .threads-layout { grid-template-columns: 1fr; }
  .thread-list { border-right: none; max-height: none; }
  .thread-list.is-hidden { display: none; }
  .thread-panel { max-height: none; }
  .thread-back { display: inline-block; }
  .bubble-row { max-width: 88%; }
}
@media (max-width: 640px) {
  .messages-view { padding: 14px; }
  .panel-filters { min-width: 100%; flex-wrap: wrap; }
  .panel-filters .filter-select { flex: 1 1 0; min-width: 0; }
  .panel-filters .search-input { max-width: none; flex: 1 1 100%; min-width: 0; }
}
</style>
