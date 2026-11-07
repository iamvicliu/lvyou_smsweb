<template>
  <div class="dashboard">
    <AppHeader
      :loading="loading"
      :scanning="scanning"
      :is-dark="isDark"
      @scan="startScanAdd"
      @refresh="refreshAll"
      @logout="handleLogout"
      @toggle-theme="toggleTheme"
      @open-settings="$router.push('/settings')"
    />

    <div class="dash-split">
      <div class="dash-main">
        <StatsGrid
          :online="onlineCount"
          :offline="offlineCount"
          :total="devicesStore.devicesTotal"
          :sim-count="devicesStore.numbersTotal"
          :sim-bad="overview.sims ? overview.sims.bad : 0"
          :today-in="overview.today ? overview.today.sms_in : 0"
          :today-out="overview.today ? overview.today.sms_out : 0"
        />

    <section class="device-panel">
      <div class="panel-head">
        <span class="panel-title">设备 <b>{{ devicesStore.devicesTotal }}</b></span>
        <div class="panel-filters">
          <input v-model="searchText" class="search-input" placeholder="搜索设备 / IP / MAC / 号码" />
          <select v-model="groupFilter" class="filter-select">
            <option value="all">全部分组</option>
            <option v-for="g in uniqueGroups.filter(x => x !== 'all')" :key="g" :value="g">{{ groupLabel(g) }}</option>
          </select>
        </div>
        <label class="panel-select">
          <span :class="['checkbox', { checked: allSelected, partial: currentPageSelectedCount > 0 && !allSelected }]">{{ allSelected ? '✓' : (currentPageSelectedCount > 0 ? '−' : '') }}</span>
          <input
            type="checkbox"
            :checked="allSelected"
            :indeterminate="currentPageSelectedCount > 0 && !allSelected"
            @change="toggleSelectAll"
            style="display: none"
          />
          <span>{{ selectedCount > 0 ? `已选 ${selectedCount} 台` : '全选' }}</span>
        </label>
      </div>

      <!-- The batch bar only exists while something is selected; otherwise the
           panel stays a single quiet block. -->
      <div v-if="selectedCount > 0" class="panel-actions">
        <button class="toolbar-btn" title="批量设置板子的 WiFi" @click="openWifiModal">设置 WiFi</button>
        <button class="toolbar-btn" title="批量检查并升级板子固件" @click="openOtaModal">升级固件</button>
        <button class="toolbar-btn" title="批量读取和修改板子配置" @click="openConfigModal">批量改配置</button>
        <button class="toolbar-btn" title="让选中的板子把短信和来电推送到这个面板" @click="setupPush" :disabled="pushing">{{ pushing ? '设置中…' : '开启消息推送' }}</button>
        <button class="toolbar-btn" title="关闭选中板子两张卡的移动网络" @click="batchTurnOffNet" :disabled="netBusy">{{ netBusy ? '处理中…' : '关闭卡槽联网' }}</button>
        <button class="toolbar-btn" title="批量修改板子后台的管理员密码" @click="openPasswordModal">批量改密码</button>
        <span class="panel-spacer"></span>
        <button class="toolbar-btn danger" @click="batchDeleteSelected">删除</button>
        <button class="panel-cancel" @click="selectedIds = []">取消选择</button>
      </div>

      <DeviceGrid
        :devices="filteredDevices"
        :latest-firmware="latestFirmware"
        :selected-ids="selectedIds"
        @toggle-select="toggleSelect"
        @show-detail="showDetail"
        @rename="renameDevice"
        @set-group="setGroup"
        @delete="deleteDevice"
        @reorder="reorderDevice"
        @move-up="moveDeviceUp"
        @move-down="moveDeviceDown"
      />

      <Pagination
        flush
        :page="devicesStore.devicesPage"
        :pages="devicesStore.devicesPages"
        :page-size="devicesStore.devicesPageSize"
        :total="devicesStore.devicesTotal"
        @change="devicesStore.setDevicesPage"
      />
    </section>
      </div>

      <aside class="dash-rail">
        <MessagePanel
          stacked
          v-model:mode="commMode"
          v-model:sender="fromSelected"
          v-model:to-phone="toPhone"
          v-model:content="content"
          v-model:dial-phone="dialPhone"
          v-model:tts-text="ttsText"
          :numbers="allNumbers"
          :loading="loading"
          @send="send"
          @dial="dial"
        />
        <LiveSmsFeed class="feed-rail" />
      </aside>
    </div>

    <WifiModal
      v-if="showWifiModal"
      v-model:ssid="wifiSsid"
      v-model:password="wifiPwd"
      :results="wifiPreviewResults"
      :loading="loading"
      @preview="previewWifi"
      @apply="applyWifi"
      @close="closeWifiModal"
    />

    <OtaModal
      v-if="showOtaModal"
      :results="otaResults"
      :loading="loading"
      :upgrading="otaUpgrading"
      @check="checkOta"
      @upgrade="upgradeOta"
      @close="closeOtaModal"
    />

    <DetailModal
      v-if="showDetailModal && deviceDetail"
      :detail="deviceDetail"
      :loading="loading"
      :my-phone="myPhone"
      :saved-phones="savedPhones"
      @update-sim1="updateDetailSim('sim1number', $event)"
      @update-sim2="updateDetailSim('sim2number', $event)"
      @update-myphone="setMyPhone"
      @quick-dial="quickDial"
      @save="saveSimSingle"
      @close="closeDetailModal"
    />

    <ConfigModal v-if="showConfigModal" />
    <BatchPasswordModal
      v-if="showPasswordModal"
      :device-count="selectedCount"
      :loading="passwordRunning"
      :results="passwordResults"
      @submit="runPasswordChange"
      @close="closePasswordModal"
    />
    <ConfirmModal />
    <PromptModal />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import {
  useAuthStore,
  useContactsStore,
  useDevicesStore,
  useDialogStore,
  useNoticeStore,
  useScanStore
} from '../stores'
import AppHeader from '../components/AppHeader.vue'
import StatsGrid from '../components/StatsGrid.vue'
import MessagePanel from '../components/MessagePanel.vue'
import DeviceGrid from '../components/DeviceGrid.vue'
import Pagination from '../components/Pagination.vue'
import LiveSmsFeed from '../components/LiveSmsFeed.vue'
import WifiModal from '../components/WifiModal.vue'
import OtaModal from '../components/OtaModal.vue'
import DetailModal from '../components/DetailModal.vue'
import ConfigModal from '../components/ConfigModal.vue'
import BatchPasswordModal from '../components/BatchPasswordModal.vue'
import ConfirmModal from '../components/ConfirmModal.vue'
import PromptModal from '../components/PromptModal.vue'
import { useLoading } from '../composables/useLoading'
import { useNotice } from '../composables/useNotice'
import { useDeviceActions } from '../composables/useDeviceActions'
import { useMessaging } from '../composables/useMessaging'
import { useWifi } from '../composables/useWifi'
import { useOta } from '../composables/useOta'
import { useConfigBatch } from '../composables/useConfigBatch'
import { useDetail } from '../composables/useDetail'
import { useKeyboardShortcuts } from '../composables/useKeyboardShortcuts'
import { useTheme } from '../composables/useTheme'
import { groupLabel } from '../utils/format'
import {
  batchBoardPassword,
  batchControlSlots,
  setupDevicePush,
  fetchOverview,
  fetchDeviceHealth
} from '../api/endpoints'

// Silent device-list refresh: SIM insert/remove arrives as a webhook, so the
// dashboard has to re-read the list to show it without pressing 扫描.
let autoRefreshTimer = null
const overview = ref({ sims: null, today: null })

async function loadOverview() {
  try {
    overview.value = await fetchOverview()
  } catch {
    // A failed overview must not blank the device grid; the old numbers stay.
  }
}

// 手动刷新时顺带读一次每块板子的 stat，让卡片的开机时长/内存立刻有值。
// 这是用户点按钮触发的单次诊断，不是定时轮询（厂商文档禁止轮询）。
async function refreshAll() {
  await refresh()
  const list = (devices.value || []).slice()
  const queue = list.concat()
  const workers = Array.from({ length: Math.min(4, queue.length) }, async () => {
    while (queue.length) {
      const d = queue.shift()
      try {
        await fetchDeviceHealth(d.id)
      } catch {
        // 单块板子读不到不影响其它板子和列表刷新
      }
    }
  })
  await Promise.all(workers)
  if (list.length) await devicesStore.refresh({ silent: true })
}

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const devicesStore = useDevicesStore()
const scanStore = useScanStore()
const noticeStore = useNoticeStore()
const dialogStore = useDialogStore()

const { authed, uiPass } = storeToRefs(authStore)
const {
  devices,
  allNumbers,
  searchText,
  groupFilter,
  selectedIds,
  uniqueGroups,
  onlineCount,
  offlineCount,
  latestFirmware,
  selectedCount,
  filteredDevices
} = storeToRefs(devicesStore)
const { scanning } = storeToRefs(scanStore)

const loading = useLoading()
const contactsStore = useContactsStore()
const { clearNotice, setNotice } = useNotice()
const { isDark, toggleTheme } = useTheme()

const {
  refresh,
  startScanAdd,
  toggleSelectAll,
  batchDeleteSelected,
  toggleSelect,
  renameDevice,
  setGroup,
  deleteDevice,
  moveDeviceUp,
  moveDeviceDown,
  reorderDevice
} = useDeviceActions()
const { commMode, fromSelected, toPhone, content, dialPhone, ttsText, send, dial } = useMessaging()
const { showWifiModal, wifiSsid, wifiPwd, wifiPreviewResults, openWifiModal, closeWifiModal, previewWifi, applyWifi } = useWifi()
const { showOtaModal, otaResults, otaUpgrading, openOtaModal, closeOtaModal, checkOta, upgradeOta } = useOta()
const { showConfigModal, openConfigModal } = useConfigBatch()
const {
  showDetailModal,
  deviceDetail,
  myPhone,
  savedPhones,
  setMyPhone,
  closeDetailModal,
  saveSimSingle,
  updateDetailSim,
  quickDial
} = useDetail()

const pushing = ref(false)
const netBusy = ref(false)
const showPasswordModal = ref(false)
const passwordRunning = ref(false)
const passwordResults = ref([])

async function batchTurnOffNet() {
  if (!selectedCount.value || netBusy.value) return
  const count = selectedCount.value
  const confirmed = await dialogStore.confirm({
    title: '批量关闭联网',
    message: `关闭选中的 ${count} 台设备的卡1、卡2 联网？\n\n`
      + '关闭后这两张卡收不到短信、接不到来电，也发不出去；WiFi 保持正常。'
      + '要恢复需要在详情页逐个卡槽重新开启联网。',
    confirmText: '关闭联网',
    danger: true
  })
  if (!confirmed) return
  netBusy.value = true
  setNotice('正在关闭选中设备的卡槽联网…', 'info')
  try {
    const resp = await batchControlSlots({
      device_ids: selectedIds.value.slice(),
      slots: [1, 2],
      action: 'net',
      enabled: false
    })
    const data = (resp && resp.data) || {}
    const failed = (data.items || []).filter(i => !i.ok)
    if (failed.length === 0) {
      setNotice(`已关闭 ${data.ok_slots} 个卡槽的联网`, 'ok')
    } else {
      const detail = failed.map(i => {
        const bad = (i.slots || []).filter(s => !s.ok)
        return `${i.name || i.ip}：` + bad.map(s => `卡${s.slot} ${s.note || '失败'}`).join('、')
      }).join('；')
      setNotice(`已关闭 ${data.ok_slots} 个卡槽，${data.failed_slots} 个失败。${detail}`, 'err')
    }
    await devicesStore.refresh({ silent: true })
  } catch (e) {
    const detail = (e && e.response && e.response.data && e.response.data.detail) || (e && e.message)
    setNotice('关闭联网失败：' + (detail || '请稍后重试'), 'err')
  } finally {
    netBusy.value = false
  }
}

function openPasswordModal() {
  if (!selectedCount.value) return
  passwordResults.value = []
  showPasswordModal.value = true
}

function closePasswordModal() {
  showPasswordModal.value = false
}

async function runPasswordChange(password) {
  if (!selectedCount.value || passwordRunning.value) return
  passwordRunning.value = true
  try {
    const resp = await batchBoardPassword(selectedIds.value.slice(), password)
    const data = (resp && resp.data) || {}
    passwordResults.value = data.items || []
    if (data.ok) {
      setNotice(`已在 ${data.succeeded} 台设备上改好密码，并回连验证通过`, 'ok')
    } else {
      setNotice(`改密码完成 ${data.succeeded} 台，失败 ${data.failed} 台`, 'err')
    }
  } catch (e) {
    const detail = (e && e.response && e.response.data && e.response.data.detail) || (e && e.message)
    setNotice('批量改密码失败：' + (detail || '请稍后重试'), 'err')
  } finally {
    passwordRunning.value = false
  }
}

async function setupPush() {
  if (!selectedCount.value || pushing.value) return
  pushing.value = true
  setNotice('正在为选中的设备开启推送…', 'info')
  try {
    const resp = await setupDevicePush(selectedIds.value.slice())
    const data = (resp && resp.data) || {}
    const items = data.items || []
    const failed = items.filter(i => !i.ok)
    if (items.length && !failed.length) {
      setNotice(`已为 ${items.length} 台设备开启短信/通话回传`, 'ok')
    } else {
      setNotice(
        '部分设备失败：' + failed.map(i => `${i.ip || i.devId} ${i.error || ''}`).join('；'),
        'err'
      )
    }
  } catch (e) {
    const detail = (e && e.response && e.response.data && e.response.data.detail) || (e && e.message)
    setNotice('开启推送失败：' + (detail || '请稍后重试'), 'err')
  } finally {
    pushing.value = false
  }
}

const currentPageSelectedCount = computed(
  () => devices.value.filter(d => selectedIds.value.includes(d.id)).length
)
const allSelected = computed(
  () => filteredDevices.value.length > 0 && currentPageSelectedCount.value === filteredDevices.value.length
)

async function handleLogout() {
  await authStore.logout(true)
  router.push('/login')
}

// Keyboard shortcuts
const shortcuts = {
  'Ctrl+K': () => document.querySelector('.search-input')?.focus(),
  'Space': () => { if (document.activeElement.tagName !== 'INPUT') toggleSelectAll() },
  'Delete': () => { if (selectedCount.value > 0) batchDeleteSelected() },
  'r': () => { if (document.activeElement.tagName !== 'INPUT') refreshAll() }
}
useKeyboardShortcuts(shortcuts)

onMounted(async () => {
  loading.value = true
  // Suggestion names only; a failed fetch must not block the dashboard.
  contactsStore.ensureLoaded().catch(() => {})
  // The contact book's "发短信"/"拨号" buttons land here with ?to=<number>;
  // prefill the recipient and switch the tab, the sender card is still the
  // operator's choice.
  const presetTo = String(route.query.to || '').trim()
  if (presetTo) {
    toPhone.value = presetTo
    commMode.value = route.query.mode === 'dial' ? 'dial' : 'sms'
  }
  try {
    if (await authStore.restore()) {
      await devicesStore.refresh()
      await loadOverview()
    } else {
      router.push('/login')
    }
  } finally {
    loading.value = false
  }
  // SIM insert/remove only reaches us as a board push (204/205/209), so
  // re-read the list quietly to show the new card without a manual scan.
  autoRefreshTimer = setInterval(() => {
    if (!document.hidden) {
      devicesStore.refresh({ silent: true })
      loadOverview()
    }
  }, 30000)
})

onUnmounted(() => {
  if (autoRefreshTimer) clearInterval(autoRefreshTimer)
})
</script>

<style scoped>
/* Same width as 号码 / 短信 / 通话 pages — the dashboard used to be 1560 and
   its cards visibly stuck out past every other tab. */
.dashboard { padding: 24px; max-width: 1440px; margin: 0 auto; }

/* Two columns: stats and the device list on the left, "send" above "receive"
   on the right. Keeping the composer in the rail means it no longer costs a
   full-width row of page height. */
.dash-split {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 16px;
  align-items: start;
}
.dash-main {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}
.dash-main :deep(.stats-bar) { margin-bottom: 0; }
.dash-rail {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
  position: sticky;
  top: 16px;
  max-height: calc(100vh - 32px);
}
/* The feed takes whatever height the send box leaves and scrolls inside it. */
.dash-rail .feed-rail { flex: 1 1 auto; min-height: 180px; }

/* Narrow laptops keep the rail but drop to two card columns; three columns in
   that width made the SIM rows wrap. */
@media (max-width: 1359px) {
  .dash-split { grid-template-columns: minmax(0, 1fr) 320px; }
  .dash-split :deep(.cards-grid) { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

/* Phones and tablets stack. The main column dissolves so its two blocks can
   sit on either side of the rail: stats, then send + feed, then the boards. */
@media (max-width: 1023px) {
  .dash-split { display: flex; flex-direction: column; }
  .dash-main { display: contents; }
  .dash-split :deep(.stats-bar) { order: 1; }
  .dash-rail { order: 2; position: static; max-height: none; }
  .device-panel { order: 3; }
  .dash-split :deep(.cards-grid) { grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); }
  .dash-rail .feed-rail { max-height: 420px; flex: 0 0 auto; }
}
</style>
