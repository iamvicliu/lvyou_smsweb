<template>
  <div class="calls-view">
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

    <LiveCallPanel @refresh="load" />

    <section class="records-panel">
      <div class="panel-head">
        <span class="panel-title">通话记录 <b>{{ total }}</b></span>
        <div class="panel-filters">
          <select v-model="deviceId" class="filter-select" @change="reload">
            <option :value="0">全部设备</option>
            <option v-for="d in devices" :key="d.id" :value="d.id">{{ d.alias || d.devId || d.ip }}</option>
          </select>
          <select v-model="direction" class="filter-select" @change="reload">
            <option value="">全部方向</option>
            <option value="incoming">呼入</option>
            <option value="outgoing">呼出</option>
          </select>
          <input v-model="q" class="search-input" placeholder="搜索号码" @keyup.enter="reload" />
        </div>
        <button class="toolbar-btn" @click="reload">查询</button>
        <button
          class="toolbar-btn"
          :disabled="syncing"
          title="让面板马上向每块板子取一次最新通话"
          @click="syncAll"
        >
          {{ syncing ? '同步中…' : '同步最新记录' }}
        </button>
      </div>

      <div class="records-scroll records-table-only">
        <table v-if="items.length" class="records-table cols-8">
          <thead>
            <tr>
              <th style="width:170px">时间</th>
              <th style="width:150px">设备</th>
              <th style="width:190px">卡槽</th>
              <th style="width:64px">方向</th>
              <th style="width:140px">号码</th>
              <th style="width:80px">状态</th>
              <th style="width:80px">时长</th>
              <th style="width:240px">录音</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="row in items" :key="row.id">
            <tr>
              <td class="muted nowrap">{{ row.call_time }}</td>
              <td>{{ row.device_name }}</td>
              <td>{{ simLabel(row.sim_slot, row.sim_number) }}</td>
              <td>{{ row.direction === 'incoming' ? '呼入' : '呼出' }}</td>
              <td class="mono nowrap">{{ row.phone }}</td>
              <td><span :class="['tag', tagClass(row.action)]">{{ actionLabel(row.action) }}</span></td>
              <td class="nowrap">{{ formatDuration(rowDuration(row)) }}</td>
              <td>
                <AudioClip
                  v-if="row.recording && row.recording.status !== 'failed'"
                  :src="audioUrl(row.recording.id)"
                  :download="downloadUrl(row.recording.id)"
                  :duration="row.recording.duration"
                  :size="row.recording.size"
                  can-delete
                  @delete="removeRecording(row)"
                />
                <span v-else-if="row.recording" class="rec-fail" :title="row.recording.note">
                  录音失败
                </span>
                <span v-else class="muted">-</span>
              </td>
            </tr>
            </template>
          </tbody>
        </table>
        <div v-else class="empty-row">{{ loading ? '加载中…' : '暂无通话记录' }}</div>
      </div>

      <div v-if="items.length" class="record-list">
        <div v-for="row in items" :key="'c' + row.id" class="record-item">
          <div class="record-top">
            <span class="record-time">{{ row.call_time }}</span>
            <span :class="['tag', tagClass(row.action)]">{{ actionLabel(row.action) }}</span>
          </div>
          <div class="record-sub">
            <span>{{ row.device_name }}</span>
            <span class="sep">·</span>
            <span>{{ simLabel(row.sim_slot) }}</span>
            <span class="sep">·</span>
            <span class="mono">{{ row.phone }}</span>
            <span class="sep">·</span>
            <span>{{ row.direction === 'incoming' ? '呼入' : '呼出' }}</span>
            <template v-if="Number(rowDuration(row) || 0) > 0">
              <span class="sep">·</span>
              <span>{{ formatDuration(rowDuration(row)) }}</span>
            </template>
          </div>
          <div v-if="row.recording" class="record-actions">
            <AudioClip
              v-if="row.recording.status !== 'failed'"
              :src="audioUrl(row.recording.id)"
              :download="downloadUrl(row.recording.id)"
              :duration="row.recording.duration"
              :size="row.recording.size"
              can-delete
              @delete="removeRecording(row)"
            />
            <span v-else class="rec-fail" :title="row.recording.note">录音失败</span>
          </div>
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
    </section>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore, useDevicesStore } from '../stores'
import AppHeader from '../components/AppHeader.vue'
import Pagination from '../components/Pagination.vue'
import LiveCallPanel from '../components/LiveCallPanel.vue'
import AudioClip from '../components/AudioClip.vue'
import {
  fetchCallHistory,
  refreshMessages,
  deleteRecording,
  recordingAudioUrl,
  recordingDownloadUrl
} from '../api/endpoints'
import { useTheme } from '../composables/useTheme'
import { simLabel } from '../utils/format'

const router = useRouter()
const authStore = useAuthStore()
const devicesStore = useDevicesStore()
const { isDark, toggleTheme } = useTheme()

const loading = ref(false)
const syncing = ref(false)
const q = ref('')
const direction = ref('')
const deviceId = ref(0)
const page = ref(1)
const pageSize = ref(30)
const total = ref(0)
const pages = ref(0)
const items = ref([])
const devices = ref([])

let timer = null

function actionLabel(action) {
  return { answered: '已接', missed: '未接', no_answer: '未接', ringing: '响铃中' }[action] || action || '-'
}
function tagClass(action) {
  return action === 'answered' ? 'ok' : action === 'ringing' ? 'warn' : 'miss'
}
function formatDuration(seconds) {
  const s = Number(seconds || 0)
  if (!s) return '-'
  const m = Math.floor(s / 60)
  return m ? `${m}分${s % 60}秒` : `${s}秒`
}

// The 601 push carries no call length, so answered calls can arrive with 0.
// The recording knows how long the audio is; show that instead of a dash.
function rowDuration(row) {
  if (Number(row.duration || 0) > 0) return row.duration
  const rec = row.recording
  if (rec && Number(rec.duration || 0) > 0) return rec.duration
  return row.duration
}

function audioUrl(id) {
  return recordingAudioUrl(id)
}

function downloadUrl(id) {
  return recordingDownloadUrl(id)
}

async function removeRecording(row) {
  if (!row.recording) return
  if (!confirm('删除这条录音？音频文件会一起删除，通话记录保留。')) return
  try {
    await deleteRecording(row.recording.id)
    row.recording = null
  } catch (e) {
    alert((e.response && e.response.data && e.response.data.detail) || '删除失败')
  }
}

async function load() {
  loading.value = true
  try {
    const data = await fetchCallHistory({
      page: page.value,
      pageSize: pageSize.value,
      q: q.value.trim(),
      direction: direction.value,
      deviceId: deviceId.value
    })
    items.value = data.items || []
    total.value = data.total || 0
    pages.value = data.pages || 0
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  load()
}

async function syncAll() {
  syncing.value = true
  try {
    for (const d of devices.value) {
      try { await refreshMessages(d.id) } catch { /* keep going */ }
    }
    await load()
  } finally {
    syncing.value = false
  }
}

async function handleLogout() {
  await authStore.logout(true)
  router.push('/login')
}

onMounted(async () => {
  if (!(await authStore.restore())) {
    router.push('/login')
    return
  }
  await devicesStore.refresh()
  devices.value = devicesStore.devices
  await load()
  timer = setInterval(load, 60000)
})

onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.calls-view { padding: 24px; max-width: 1440px; margin: 0 auto; }
.muted { color: var(--text-muted, #94a3b8); }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; white-space: nowrap; }
.tag.ok { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.tag.miss { background: rgba(239, 68, 68, 0.15); color: #f87171; }
.tag.warn { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.rec-fail { color: var(--danger); font-size: 12px; }
@media (max-width: 640px) {
  .calls-view { padding: 14px; }
  .panel-filters { min-width: 100%; flex-wrap: wrap; }
  .panel-filters .filter-select { flex: 1 1 0; min-width: 0; }
  .panel-filters .search-input { max-width: none; flex: 1 1 100%; min-width: 0; }
}
</style>
