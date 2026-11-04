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
        <span class="panel-title">短信记录 <b>{{ total }}</b></span>
        <div class="panel-filters">
          <select v-model="deviceId" class="filter-select" @change="reload">
            <option :value="0">全部设备</option>
            <option v-for="d in devices" :key="d.id" :value="d.id">{{ d.alias || d.devId || d.ip }}</option>
          </select>
          <select v-model="direction" class="filter-select" @change="reload">
            <option value="">全部方向</option>
            <option value="received">收到</option>
            <option value="sent">发出</option>
          </select>
          <input v-model="q" class="search-input" placeholder="搜索号码 / 内容" @keyup.enter="reload" />
        </div>
        <button class="toolbar-btn" @click="reload">查询</button>
        <button class="toolbar-btn" :disabled="syncing" @click="syncAll">
          {{ syncing ? '同步中…' : '从板子同步' }}
        </button>
      </div>

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
              <td>{{ simLabel(row.sim_slot, row.sim_number) }}</td>
              <td>
                <span :class="['tag', row.direction === 'received' ? 'in' : 'out']">
                  {{ row.direction === 'received' ? '收到' : '发出' }}
                </span>
              </td>
              <td class="mono nowrap">{{ row.phone }}</td>
              <td class="content">
                <div :class="['clamp', { open: expanded.has(row.id) }]" @click="toggleExpand(row.id)">
                  {{ row.content }}
                </div>
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
            <span>{{ simLabel(row.sim_slot) }}</span>
            <span class="sep">·</span>
            <span class="mono">{{ row.phone }}</span>
          </div>
          <div :class="['record-body', 'clamp', { open: expanded.has(row.id) }]" @click="toggleExpand(row.id)">
            {{ row.content }}
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
import { fetchSmsHistory, refreshMessages } from '../api/endpoints'
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
// Long SMS clog the list; three lines by default, one tap opens the whole text.
const expanded = ref(new Set())

function toggleExpand(id) {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expanded.value = next
}

let timer = null

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
      try { await refreshMessages(d.id) } catch { /* one dead board must not stop the rest */ }
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
  timer = setInterval(load, 30000)
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
@media (max-width: 640px) {
  .messages-view { padding: 14px; }
  .panel-filters { min-width: 100%; flex-wrap: wrap; }
  .panel-filters .filter-select { flex: 1 1 0; min-width: 0; }
  .panel-filters .search-input { max-width: none; flex: 1 1 100%; min-width: 0; }
}
</style>
