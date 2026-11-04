<template>
  <div class="dashboard">
    <AppHeader
      :loading="loading"
      :scanning="scanning"
      :is-dark="isDark"
      @scan="startScanAdd"
      @refresh="refresh"
      @logout="handleLogout"
      @toggle-theme="toggleTheme"
      @open-settings="$router.push('/settings')"
    />

    <StatsGrid
      :online="onlineCount"
      :offline="offlineCount"
      :total="devicesStore.devicesTotal"
      :sim-count="devicesStore.numbersTotal"
      :trend-data="trendData"
    />

    <MessagePanel
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

    <div class="toolbar">
      <div class="toolbar-left">
        <input v-model="searchText" class="search-input" placeholder="搜索设备/IP/MAC/号码..." />
        <select v-model="groupFilter" class="filter-select">
          <option value="all">全部分组</option>
          <option v-for="g in uniqueGroups.filter(x => x !== 'all')" :key="g" :value="g">{{ g }}</option>
        </select>
      </div>
      <div class="toolbar-right">
        <button class="toolbar-btn" :class="{ active: sortMode }" @click="sortMode = !sortMode">
          {{ sortMode ? '完成排序' : '排序' }}
        </button>
        <button class="toolbar-btn" @click="openWifiModal" :disabled="selectedCount === 0">WiFi</button>
        <button class="toolbar-btn" @click="openOtaModal" :disabled="selectedCount === 0">OTA</button>
        <button class="toolbar-btn" @click="openConfigModal" :disabled="selectedCount === 0">配置</button>
        <button class="toolbar-btn" @click="setupPush" :disabled="selectedCount === 0 || pushing">
          {{ pushing ? '接入中…' : '接入推送' }}
        </button>
        <button class="toolbar-btn" @click="batchTurnOffNet" :disabled="selectedCount === 0 || netBusy">
          {{ netBusy ? '处理中…' : '批量关联网' }}
        </button>
        <button class="toolbar-btn" @click="openPasswordModal" :disabled="selectedCount === 0">
          改密码
        </button>
        <button class="toolbar-btn danger" @click="batchDeleteSelected" :disabled="selectedCount === 0">删除</button>
      </div>
    </div>

    <div class="select-bar">
      <label class="select-all-label">
        <span :class="['checkbox', { checked: currentPageSelectedCount > 0 && currentPageSelectedCount === filteredDevices.length }]">
          {{ currentPageSelectedCount > 0 && currentPageSelectedCount === filteredDevices.length ? '✓' : (currentPageSelectedCount > 0 ? '−' : '') }}
        </span>
        <input
          type="checkbox"
          :checked="currentPageSelectedCount === filteredDevices.length && filteredDevices.length > 0"
          :indeterminate="currentPageSelectedCount > 0 && currentPageSelectedCount < filteredDevices.length"
          @change="toggleSelectAll"
          style="display: none"
        />
        <span class="select-text">
          {{ selectedCount > 0 ? `已选择 ${selectedCount} 台` : '全选' }}
        </span>
      </label>
      <button v-if="selectedCount > 0" class="batch-cancel" @click="selectedIds = []">取消选择</button>
    </div>

    <div class="tab-bar">
      <button :class="['tab-btn', { active: activeTab === 'devices' }]" @click="activeTab = 'devices'">
        设备列表 ({{ devicesStore.devicesTotal }})
      </button>
      <button :class="['tab-btn', { active: activeTab === 'numbers' }]" @click="$router.push('/numbers')">
        号码列表 ({{ devicesStore.numbersTotal }})
      </button>
    </div>

    <DeviceGrid
      v-if="activeTab === 'devices'"
      :devices="filteredDevices"
      :selected-ids="selectedIds"
      :sort-mode="sortMode"
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
      v-if="activeTab === 'devices'"
      :page="devicesStore.devicesPage"
      :pages="devicesStore.devicesPages"
      :page-size="devicesStore.devicesPageSize"
      :total="devicesStore.devicesTotal"
      @change="devicesStore.setDevicesPage"
    />

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
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import {
  useAuthStore,
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
import {
  batchBoardPassword,
  batchControlSlots,
  setupDevicePush
} from '../api/endpoints'

// Silent device-list refresh: SIM insert/remove arrives as a webhook, so the
// dashboard has to re-read the list to show it without pressing 扫描.
let autoRefreshTimer = null

const router = useRouter()
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
  selectedCount,
  filteredDevices
} = storeToRefs(devicesStore)
const { scanning } = storeToRefs(scanStore)

const loading = useLoading()
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
  setMyPhone,
  closeDetailModal,
  saveSimSingle,
  updateDetailSim,
  quickDial
} = useDetail()

const activeTab = ref('devices')
const pushing = ref(false)
const sortMode = ref(false)
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

const trendData = ref({
  online: [65, 72, 68, 75, 80, 78, 82],
  offline: [15, 12, 14, 10, 8, 10, 6],
  total: [80, 84, 82, 85, 88, 88, 88],
  sim: [160, 168, 164, 170, 176, 176, 176]
})

const currentPageSelectedCount = computed(
  () => devices.value.filter(d => selectedIds.value.includes(d.id)).length
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
  'r': () => { if (document.activeElement.tagName !== 'INPUT') refresh() }
}
useKeyboardShortcuts(shortcuts)

onMounted(async () => {
  loading.value = true
  try {
    if (await authStore.restore()) {
      await devicesStore.refresh()
    } else {
      router.push('/login')
    }
  } finally {
    loading.value = false
  }
  // SIM insert/remove only reaches us as a board push (204/205/209), so
  // re-read the list quietly to show the new card without a manual scan.
  autoRefreshTimer = setInterval(() => {
    if (!document.hidden) devicesStore.refresh({ silent: true })
  }, 30000)
})

onUnmounted(() => {
  if (autoRefreshTimer) clearInterval(autoRefreshTimer)
})
</script>

<style scoped>
.dashboard { padding: 24px; max-width: 1440px; margin: 0 auto; }
</style>
