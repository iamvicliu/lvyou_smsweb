<template>
  <div class="settings-view">
    <header class="header">
      <div class="header-left">
        <button class="back-btn" @click="router.push('/dashboard')" title="返回">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </button>
        <div class="header-title">
          <h1>系统设置</h1>
        </div>
      </div>
      <div class="header-right">
        <button class="header-btn logout" @click="handleLogout">退出</button>
      </div>
    </header>

    <div class="settings-grid">
      <div class="settings-card">
        <h3>外观</h3>
        <div class="setting-item">
          <div class="setting-info">
            <span class="setting-label">主题模式</span>
            <span class="setting-desc">切换深色/浅色主题</span>
          </div>
          <button class="theme-toggle" @click="toggleTheme">
            <span class="theme-icon">{{ isDark ? '' : '☀️' }}</span>
            <span>{{ isDark ? '深色' : '浅色' }}</span>
          </button>
        </div>
      </div>

      <div class="settings-card">
        <h3>设备接入</h3>
        <div class="cred-form">
          <label class="cred-row">
            <span class="setting-label">管理员账号</span>
            <input v-model="credUser" class="cred-input" placeholder="admin" autocomplete="off" />
          </label>
          <label class="cred-row">
            <span class="setting-label">管理员密码</span>
            <input
              v-model="credPass"
              class="cred-input"
              type="password"
              autocomplete="new-password"
              :placeholder="passwordConfigured ? '已设置，留空表示不修改' : '板子后台的管理员密码'"
            />
          </label>
          <label class="cred-check">
            <input v-model="applyToAll" type="checkbox" />
            <span>同时应用到所有已添加设备</span>
          </label>
          <div class="cred-actions">
            <button class="theme-toggle" :disabled="savingCred" @click="saveCred">
              <span>{{ savingCred ? '保存中…' : '保存' }}</span>
            </button>
            <span class="cred-state" :class="{ err: credError }">{{ credStatus }}</span>
          </div>
          <p class="cred-hint">
            扫描新设备、读取状态、批量配置和 OTA 都用这一组凭据；板子改了密码后在这里更新一次即可。
          </p>
        </div>
      </div>

      <div class="settings-card">
        <h3>消息推送（Bark）</h3>
        <div class="cred-form">
          <label class="cred-row">
            <span class="setting-label">Bark 推送地址</span>
            <input
              v-model="barkUrl"
              class="cred-input"
              type="password"
              autocomplete="off"
              spellcheck="false"
              :placeholder="barkConfigured ? '已设置（' + barkHost + '），留空表示不修改' : 'https://…/设备Key/分组'"
            />
          </label>
          <div class="cred-actions">
            <button class="theme-toggle" :disabled="savingBark" @click="saveBark(false)">
              <span>{{ savingBark ? '保存中…' : '保存' }}</span>
            </button>
            <button class="theme-toggle" :disabled="savingBark" @click="saveBark(true)">
              <span>保存并测试</span>
            </button>
            <span class="cred-state" :class="{ err: barkError }">{{ barkStatus }}</span>
          </div>
          <p class="cred-hint">
            收到短信、短信发出/失败/送达时推送到 iPhone。地址含设备 Key，保存后只显示域名，不会再回显完整链接。
          </p>
        </div>
      </div>

      <div class="settings-card">
        <h3>快捷键</h3>
        <div class="shortcuts-list">
          <div class="shortcut-item">
            <span class="shortcut-keys"><kbd>Ctrl</kbd>+<kbd>K</kbd></span>
            <span class="shortcut-desc">聚焦搜索框</span>
          </div>
          <div class="shortcut-item">
            <span class="shortcut-keys"><kbd>Space</kbd></span>
            <span class="shortcut-desc">全选/取消全选</span>
          </div>
          <div class="shortcut-item">
            <span class="shortcut-keys"><kbd>Delete</kbd></span>
            <span class="shortcut-desc">批量删除选中设备</span>
          </div>
          <div class="shortcut-item">
            <span class="shortcut-keys"><kbd>R</kbd></span>
            <span class="shortcut-desc">刷新设备列表</span>
          </div>
          <div class="shortcut-item">
            <span class="shortcut-keys"><kbd>Esc</kbd></span>
            <span class="shortcut-desc">关闭弹窗</span>
          </div>
        </div>
      </div>

      <div class="settings-card wide">
        <h3>通话录音</h3>
        <div class="cred-form">
          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">录音上传通道</span>
              <span class="setting-desc">
                {{ recTokenConfigured ? '已生成专用上传令牌（' + recTokenHint + '）' : '尚未生成上传令牌' }}
                · 已存 {{ recCount }} 条 / {{ formatSize(recBytes) }}
                · {{ recFfmpeg ? 'MP3 转码可用' : '容器缺少 ffmpeg，只能播放 AMR' }}
              </span>
            </div>
            <button class="theme-toggle" :disabled="recBusy" @click="applyRecordingUrls">
              <span>{{ recBusy ? '下发中…' : '下发到全部设备' }}</span>
            </button>
          </div>
          <p class="cred-hint">
            下发会把录音上传地址写入每块板子的 telRecUrl，并打开 695/696 上报；
            通话结束后面板自动收下 AMR 并转成 MP3。令牌写在地址里，不需要额外登录。
          </p>
          <div class="cred-actions">
            <button class="theme-toggle" @click="router.push('/calls')">
              <span>打开通话记录</span>
            </button>
            <button class="theme-toggle" :disabled="recBusy" @click="rotateToken">
              <span>重置上传令牌</span>
            </button>
            <span class="cred-state" :class="{ err: recError }">{{ recStatus }}</span>
          </div>
        </div>

        <hr class="card-divider" />

        <div class="cred-form">
          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">自动接听 / 录音模式</span>
              <span class="setting-desc">
                录音只在“接听并录音”模式下产生；板子会在通话结束后自动上传。
                建议最大通话时长不超过 15 秒，过长时板子可能来不及上传。
              </span>
            </div>
          </div>
          <div class="answer-form">
            <label class="cred-row compact">
              <span class="setting-label">范围</span>
              <select v-model="answerDevice" class="cred-input">
                <option :value="0">全部设备</option>
                <option v-for="d in devicesStore.devices" :key="d.id" :value="d.id">
                  {{ d.alias || d.devId || d.ip }}
                </option>
              </select>
            </label>
            <label class="cred-row compact">
              <span class="setting-label">模式</span>
              <select v-model.number="answerMode" class="cred-input">
                <option :value="0">不接听</option>
                <option :value="1">自动接听</option>
                <option :value="2">接听并录音</option>
                <option :value="3">自动挂断</option>
              </select>
            </label>
            <label class="cred-row compact">
              <span class="setting-label">响铃</span>
              <input v-model.number="answerRing" type="number" min="0" max="30" class="cred-input" />
            </label>
            <label class="cred-row compact">
              <span class="setting-label">最长秒数</span>
              <input v-model.number="answerSeconds" type="number" min="1" max="999" class="cred-input" />
            </label>
            <button class="theme-toggle" :disabled="answerBusy" @click="applyAnswerMode">
              <span>{{ answerBusy ? '应用中…' : '应用' }}</span>
            </button>
          </div>
          <p class="cred-hint">
            两个卡槽一起设置。该配置写入板子“运行参数”，重启后保留。
            这张卡一旦设置了自动接听，来电会先被板子接走，人在面板上就来不及接；
            想人工接听时到通话页点「改为人工接管」，把这张卡临时切成不接听，之后可一键恢复。
          </p>
          <div v-if="answerDevices.length" class="answer-list">
            <div v-for="d in answerDevices" :key="d.device_id" class="answer-row">
              <span class="answer-name">{{ d.name }}</span>
              <span v-if="d.ok" class="answer-values">
                卡1 {{ d.slots['1'].mode_label }}（{{ d.slots['1'].ring }}声/{{ d.slots['1'].max_seconds }}秒）
                · 卡2 {{ d.slots['2'].mode_label }}（{{ d.slots['2'].ring }}声/{{ d.slots['2'].max_seconds }}秒）
              </span>
              <span v-else class="cred-state err">{{ d.error || '读取失败' }}</span>
            </div>
          </div>
          <div class="cred-actions">
            <button class="theme-toggle" :disabled="answerBusy" @click="loadAnswerConfig">
              <span>刷新板子当前设置</span>
            </button>
            <span class="cred-state" :class="{ err: answerError }">{{ answerStatus }}</span>
          </div>
        </div>
      </div>

      <div class="settings-card wide">
        <h3>SIM 异常自愈</h3>
        <div class="cred-form">
          <div class="setting-item">
            <div class="setting-info">
              <span class="setting-label">209 自动重启卡槽</span>
              <span class="setting-desc">
                板子报 SIM 初始化失败（209）时先观察 30 秒，期间恢复就取消；
                观察期满只做一次 stat 确认，确认仍异常才重启对应卡槽。
                同一台设备 24 小时内最多自动重启一次，观察和取消不推送。
              </span>
            </div>
            <button class="theme-toggle" :disabled="guardBusy" @click="toggleGuard">
              <span>{{ guardEnabled ? '已开启' : '已关闭' }}</span>
            </button>
          </div>
          <div v-if="guardItems.length" class="answer-list">
            <div v-for="g in guardItems" :key="g.device_id" class="answer-row">
              <span class="answer-name">{{ g.name }}</span>
              <span class="answer-values">{{ guardLine(g) }}</span>
              <button class="theme-toggle" :disabled="guardBusy" @click="toggleGuardMute(g)">
                <span>{{ g.muted ? '取消静音' : '静音此板' }}</span>
              </button>
            </div>
          </div>
          <p class="cred-hint">
            冷却时间按设备计算，收到 204（卡就绪）即清零。仅“已重启 / 已恢复 / 需人工”会推送到 Bark 与钉钉。
          </p>
          <div class="cred-actions">
            <button class="theme-toggle" :disabled="guardBusy" @click="loadGuard">
              <span>刷新状态</span>
            </button>
            <span class="cred-state" :class="{ err: guardError }">{{ guardStatus }}</span>
          </div>
        </div>
      </div>

      <div class="settings-card">
        <h3>关于</h3>
        <div class="about-info">
          <p><strong>绿邮群控系统</strong></p>
          <p>版本：v5.2.0</p>
          <p>技术栈：Vue 3 + Naive UI + Pinia</p>
          <p>License: MIT</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore, useDevicesStore } from '../stores'
import { useTheme } from '../composables/useTheme'
import { useDeviceActions } from '../composables/useDeviceActions'
import {
  fetchAnswerConfig,
  fetchRecordingConfig,
  fetchNotifySettings,
  fetchSimGuard,
  getDeviceCredentialSetting,
  rotateRecordingToken,
  saveDeviceCredentialSetting,
  saveAnswerConfig,
  saveSimGuard,
  saveSimGuardMute,
  setupRecordings,
  saveNotifySettings,
} from '../api/endpoints'

const router = useRouter()
const authStore = useAuthStore()
const devicesStore = useDevicesStore()

const { isDark, toggleTheme } = useTheme()
const { refresh } = useDeviceActions()

const credUser = ref('admin')
const credPass = ref('')
const applyToAll = ref(true)
const passwordConfigured = ref(false)
const savingCred = ref(false)
const credStatus = ref('')
const credError = ref(false)

const barkUrl = ref('')
const barkConfigured = ref(false)
const barkHost = ref('')
const savingBark = ref(false)
const barkStatus = ref('')
const barkError = ref(false)

const recTokenConfigured = ref(false)
const recTokenHint = ref('')
const recCount = ref(0)
const recBytes = ref(0)
const recFfmpeg = ref(false)
const recBusy = ref(false)
const recStatus = ref('')
const recError = ref(false)

const answerDevice = ref(0)
const answerMode = ref(2)
const answerRing = ref(1)
const answerSeconds = ref(15)
const answerBusy = ref(false)
const answerStatus = ref('')
const answerError = ref(false)
const answerDevices = ref([])

const guardEnabled = ref(true)
const guardItems = ref([])
const guardBusy = ref(false)
const guardStatus = ref('')
const guardError = ref(false)

function guardLine(g) {
  const parts = []
  if (g.muted) parts.push('已静音（只记日志，不推送、不重启）')
  if (g.detail) parts.push(g.detail)
  else parts.push('暂无记录')
  if (g.pending && g.pending.length) {
    const p = g.pending[0]
    parts.push(`观察中 · 卡${p.slot} · 还剩 ${p.remaining}s`)
  }
  if (g.cooldown) parts.push(`冷却 ${(g.cooldown / 3600).toFixed(1)}h`)
  if (g.updated) {
    const d = new Date(g.updated * 1000)
    parts.push(`${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`)
  }
  return parts.join(' · ')
}

async function loadGuard() {
  try {
    const resp = await fetchSimGuard()
    const data = resp.data || {}
    guardEnabled.value = !!data.enabled
    guardItems.value = data.items || []
    guardError.value = false
    guardStatus.value = ''
  } catch (e) {
    guardStatus.value = '读取失败'
    guardError.value = true
  }
}

async function toggleGuard() {
  if (guardBusy.value) return
  guardBusy.value = true
  guardStatus.value = '保存中…'
  try {
    const resp = await saveSimGuard(!guardEnabled.value)
    const data = resp.data || {}
    guardEnabled.value = !!data.enabled
    guardItems.value = data.items || []
    guardError.value = false
    guardStatus.value = guardEnabled.value ? '已开启' : '已关闭'
  } catch (e) {
    guardStatus.value = '保存失败'
    guardError.value = true
  } finally {
    guardBusy.value = false
  }
}

async function toggleGuardMute(g) {
  if (guardBusy.value) return
  guardBusy.value = true
  guardStatus.value = '保存中…'
  try {
    const resp = await saveSimGuardMute(g.devId, !g.muted)
    const data = resp.data || {}
    guardEnabled.value = !!data.enabled
    guardItems.value = data.items || []
    guardError.value = false
    guardStatus.value = g.muted ? '已取消静音' : '已静音'
  } catch (e) {
    guardStatus.value = '保存失败'
    guardError.value = true
  } finally {
    guardBusy.value = false
  }
}

function formatSize(bytes) {
  const n = Number(bytes || 0)
  if (!n) return '0 B'
  if (n < 1024) return n + ' B'
  if (n < 1024 * 1024) return (n / 1024).toFixed(0) + ' KB'
  return (n / 1024 / 1024).toFixed(1) + ' MB'
}

async function loadRecordingConfig() {
  try {
    const resp = await fetchRecordingConfig()
    const data = resp.data || {}
    recTokenConfigured.value = !!data.token_configured
    recTokenHint.value = data.token_hint || ''
    recCount.value = data.count || 0
    recBytes.value = data.bytes || 0
    recFfmpeg.value = !!data.ffmpeg
    recError.value = !recTokenConfigured.value
    recStatus.value = recTokenConfigured.value ? '' : '尚未下发录音地址'
  } catch (e) {
    recStatus.value = '读取失败'
    recError.value = true
  }
}

async function applyRecordingUrls() {
  if (recBusy.value) return
  const ids = (devicesStore.devices || []).map(d => d.id)
  if (!ids.length) {
    recStatus.value = '没有设备'
    recError.value = true
    return
  }
  recBusy.value = true
  recStatus.value = '下发中…'
  try {
    const resp = await setupRecordings(ids)
    const data = resp.data || {}
    const failed = (data.items || []).filter(i => !i.ok)
    recError.value = failed.length > 0
    recStatus.value = failed.length
      ? `${ids.length - failed.length} 台成功，${failed.length} 台失败：` +
        failed.map(i => `${i.ip} ${i.error || ''}`).join('；')
      : `已下发到 ${ids.length} 台设备`
    await loadRecordingConfig()
  } catch (e) {
    recError.value = true
    recStatus.value = (e.response && e.response.data && e.response.data.detail) || '下发失败'
  } finally {
    recBusy.value = false
  }
}

async function rotateToken() {
  if (!confirm('重置后旧地址立即失效，需要重新“下发到全部设备”。继续？')) return
  recBusy.value = true
  try {
    await rotateRecordingToken()
    recStatus.value = '令牌已重置，请重新下发到设备'
    recError.value = true
    await loadRecordingConfig()
  } catch (e) {
    recStatus.value = '重置失败'
    recError.value = true
  } finally {
    recBusy.value = false
  }
}

async function loadAnswerConfig() {
  answerBusy.value = true
  answerStatus.value = '读取中…'
  try {
    const resp = await fetchAnswerConfig()
    answerDevices.value = (resp.data || {}).items || []
    const failed = answerDevices.value.filter(d => !d.ok)
    answerError.value = failed.length > 0
    answerStatus.value = failed.length
      ? `${failed.length} 台设备读取失败`
      : `已读取 ${answerDevices.value.length} 台设备`
  } catch (e) {
    answerError.value = true
    answerStatus.value = '读取失败'
  } finally {
    answerBusy.value = false
  }
}

async function applyAnswerMode() {
  if (answerBusy.value) return
  const ids = answerDevice.value
    ? [answerDevice.value]
    : (devicesStore.devices || []).map(d => d.id)
  if (!ids.length) {
    answerStatus.value = '没有设备'
    answerError.value = true
    return
  }
  if (answerMode.value === 2 &&
      !confirm('“接听并录音”会让这些卡槽自动接听所有来电（响铃 ' + answerRing.value +
               ' 声后），最长通话 ' + answerSeconds.value + ' 秒。继续？')) {
    return
  }
  answerBusy.value = true
  answerStatus.value = '应用中…'
  try {
    const resp = await saveAnswerConfig({
      device_ids: ids,
      mode: answerMode.value,
      ring: answerRing.value,
      max_seconds: answerSeconds.value,
    })
    const data = resp.data || {}
    const failed = (data.items || []).filter(i => !i.ok)
    answerError.value = failed.length > 0
    answerStatus.value = failed.length
      ? `${ids.length - failed.length} 台成功，${failed.length} 台失败：` +
        failed.map(i => `${i.ip} ${i.error || ''}`).join('；')
      : `已应用到 ${ids.length} 台设备`
    await loadAnswerConfig()
  } catch (e) {
    answerError.value = true
    answerStatus.value = (e.response && e.response.data && e.response.data.detail) || '应用失败'
  } finally {
    answerBusy.value = false
  }
}

async function loadNotify() {
  try {
    const resp = await fetchNotifySettings()
    const data = resp.data || {}
    barkConfigured.value = !!data.bark_configured
    barkHost.value = data.bark_host || ''
    barkStatus.value = barkConfigured.value ? '已设置' : '未设置，短信不会推送'
    barkError.value = !barkConfigured.value
  } catch (e) {
    barkStatus.value = '读取失败'
    barkError.value = true
  }
}

async function saveBark(withTest) {
  if (savingBark.value) return
  const url = String(barkUrl.value || '').trim()
  if (!url && barkConfigured.value) {
    barkStatus.value = '未修改'
    barkError.value = false
    return
  }
  if (!url) {
    barkStatus.value = '请填写推送地址'
    barkError.value = true
    return
  }
  savingBark.value = true
  barkStatus.value = '保存中…'
  try {
    const payload = { bark_url: url }
    if (withTest) payload.test_bark = true
    const resp = await saveNotifySettings(payload)
    const data = resp.data || {}
    barkUrl.value = ''
    barkConfigured.value = true
    let message = '已保存'
    let failed = false
    if (withTest) {
      failed = !data.test_bark_ok
      message = data.test_bark_ok ? '已保存，推送测试成功' : '已保存，推送测试失败'
    }
    await loadNotify()
    barkError.value = failed
    barkStatus.value = message
  } catch (e) {
    barkError.value = true
    barkStatus.value = (e.response && e.response.data && e.response.data.detail) || '保存失败'
  } finally {
    savingBark.value = false
  }
}

async function loadCredential() {
  try {
    const resp = await getDeviceCredentialSetting()
    const data = resp.data || {}
    credUser.value = data.user || 'admin'
    passwordConfigured.value = !!data.passwordConfigured
    credStatus.value = passwordConfigured.value ? '已设置' : '未设置，设备操作会失败'
    credError.value = !passwordConfigured.value
  } catch (e) {
    credStatus.value = '读取失败'
    credError.value = true
  }
}

async function saveCred() {
  if (savingCred.value) return
  if (!credPass.value && passwordConfigured.value) {
    credStatus.value = '未修改密码'
    credError.value = false
    return
  }
  if (!credPass.value) {
    credStatus.value = '请输入密码'
    credError.value = true
    return
  }
  savingCred.value = true
  credStatus.value = ''
  try {
    const resp = await saveDeviceCredentialSetting({
      user: credUser.value || 'admin',
      password: credPass.value,
      applyToAll: applyToAll.value,
    })
    const data = resp.data || {}
    passwordConfigured.value = true
    credPass.value = ''
    credError.value = false
    credStatus.value = data.devicesReset ? `已保存，${data.devicesReset} 台设备改用新凭据` : '已保存'
    await refresh()
  } catch (e) {
    credError.value = true
    credStatus.value = (e.response && e.response.data && e.response.data.detail) || '保存失败'
  } finally {
    savingCred.value = false
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
  await Promise.all([
    loadCredential(),
    loadNotify(),
    loadRecordingConfig(),
    loadGuard(),
    devicesStore.refresh(),
  ])
  loadAnswerConfig()
})
</script>

<style scoped>
.settings-view { padding: 24px; max-width: 1440px; margin: 0 auto; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 20px; border-bottom: 1px solid var(--border); }
.header-left { display: flex; align-items: center; gap: 12px; }
.header-right { display: flex; align-items: center; gap: 8px; }
.header-title h1 { font-size: 20px; font-weight: 700; letter-spacing: -0.02em; }
.back-btn {
  background: none;
  border: 1px solid var(--border);
  color: var(--text-primary);
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition);
}
.back-btn:hover {
  background: var(--bg-card-hover);
  border-color: var(--border-light);
  transform: translateX(-2px);
}
.header-btn {
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text-primary);
  padding: 8px 18px;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all var(--transition);
}
.header-btn.logout:hover { background: var(--danger-glow); }
.page-title { font-size: 24px; font-weight: 700; margin-bottom: 24px; letter-spacing: -0.02em; }
.settings-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }
.settings-card.wide { grid-column: 1 / -1; }
.card-divider { border: none; border-top: 1px solid var(--border); margin: 18px 0; }
.answer-form { display: flex; align-items: flex-end; gap: 12px; flex-wrap: wrap; }
.answer-form .cred-row.compact { min-width: 120px; flex: 0 1 160px; }
.answer-list { display: flex; flex-direction: column; gap: 6px; margin-top: 12px; }
.answer-row { display: flex; gap: 12px; font-size: 13px; flex-wrap: wrap; }
.answer-name { color: var(--text-primary); min-width: 160px; }
.answer-values { color: var(--text-secondary); }
.settings-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px;
}
.settings-card h3 { font-size: 16px; font-weight: 600; margin-bottom: 18px; padding-bottom: 12px; border-bottom: 1px solid var(--border); }
.setting-item { display: flex; justify-content: space-between; align-items: center; }
.setting-info { display: flex; flex-direction: column; gap: 4px; }
.setting-label { font-size: 14px; font-weight: 500; }
.setting-desc { font-size: 12px; color: var(--text-muted); }
.theme-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 10px 18px;
  color: var(--text-primary);
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all var(--transition);
}
.theme-toggle:hover {
  border-color: var(--primary);
  background: var(--bg-card-hover);
}
.theme-icon { font-size: 18px; }
.shortcuts-list { display: flex; flex-direction: column; gap: 12px; }
.shortcut-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; }
.shortcut-keys { display: flex; gap: 4px; align-items: center; }
.shortcut-keys kbd {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 3px 8px;
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--text-primary);
}
.shortcut-desc { font-size: 13px; color: var(--text-secondary); }
.about-info { display: flex; flex-direction: column; gap: 8px; font-size: 14px; color: var(--text-secondary); }
.about-info strong { color: var(--text-primary); font-size: 16px; }
.cred-form { display: flex; flex-direction: column; gap: 14px; }
.cred-row { display: flex; flex-direction: column; gap: 6px; }
.cred-input {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  color: var(--text-primary);
  font-size: 14px;
}
.cred-input:focus { outline: none; border-color: var(--primary); }
.cred-check { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-secondary); }
.cred-actions { display: flex; align-items: center; gap: 12px; }
.cred-state { font-size: 13px; color: var(--text-muted); }
.cred-state.err { color: var(--danger, #e5484d); }
.cred-hint { font-size: 12px; color: var(--text-muted); line-height: 1.6; }
</style>
