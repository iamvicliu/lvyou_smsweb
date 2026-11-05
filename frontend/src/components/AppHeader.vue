<template>
  <header class="header">
    <div class="header-left">
      <div class="logo" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8z" />
          <path d="M12 6a2 2 0 100 4 2 2 0 000-4zm-4 8a4 4 0 118 0v1H8v-1z" />
        </svg>
      </div>
      <div class="header-title">
        <h1>控制台</h1>
        <p>管理中心</p>
      </div>
    </div>
    <nav class="header-nav">
      <button :class="['nav-link', { active: route.path === '/dashboard' }]" @click="router.push('/dashboard')">设备</button>
      <button :class="['nav-link', { active: route.path === '/numbers' }]" @click="router.push('/numbers')">号码</button>
      <button :class="['nav-link', { active: route.path === '/messages' }]" @click="router.push('/messages')">短信</button>
      <button :class="['nav-link', { active: route.path === '/calls' }]" @click="router.push('/calls')">通话</button>
      <button :class="['nav-link', { active: route.path === '/settings' }]" @click="router.push('/settings')">设置</button>
    </nav>
    <div class="header-right">
      <div class="header-icons">
        <button
          class="header-btn icon-btn"
          :class="{ 'privacy-on': masked }"
          :title="masked ? '已遮挡号码，点一下恢复显示' : '遮挡号码和验证码，方便截图'"
          @click="toggle"
        >
          <svg v-if="masked" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
            <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94"/>
            <path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19"/>
            <path d="M14.12 14.12a3 3 0 11-4.24-4.24"/><path d="M1 1l22 22"/>
          </svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
          </svg>
        </button>
        <button class="header-btn icon-btn" @click="emit('toggle-theme')" :title="isDark ? '切换到浅色模式' : '切换到深色模式'">
          <svg v-if="isDark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
            <circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
          </svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
            <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>
          </svg>
        </button>
      </div>
      <div class="header-actions">
        <button
          class="header-btn primary"
          :disabled="scanning"
          title="在局域网里搜索还没加入面板的板子"
          @click="emit('scan')"
        >
          <span v-if="scanning" class="spinner" style="width:14px;height:14px;border-width:2px;margin-right:6px;vertical-align:middle;"></span>
          {{ scanning ? '搜索中...' : '找板子' }}
        </button>
        <button
          class="header-btn"
          :disabled="loading"
          title="重新读取当前页面的数据"
          @click="emit('refresh')"
        >刷新数据</button>
        <button class="header-btn logout" @click="emit('logout')">退出</button>
      </div>
    </div>
  </header>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { usePrivacy } from '../stores/privacy'

defineProps({
  loading: { type: Boolean, default: false },
  scanning: { type: Boolean, default: false },
  isDark: { type: Boolean, default: true }
})

const emit = defineEmits(['scan', 'refresh', 'logout', 'toggle-theme', 'open-settings'])
const route = useRoute()
const router = useRouter()
const { masked, toggle } = usePrivacy()
</script>

<style scoped>
.header-icons,
.header-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.header-nav {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 0 12px;
}
.nav-link {
  background: transparent;
  color: var(--text-muted, #94a3b8);
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 7px 14px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}
.nav-link { transition: color var(--transition), background var(--transition), box-shadow var(--transition); }
.nav-link:hover:not(.active) {
  color: var(--primary);
  background: var(--primary-glow);
}
.nav-link.active {
  color: #fff;
  background: linear-gradient(135deg, var(--primary), var(--primary-dark, #059669));
  box-shadow: 0 4px 12px var(--primary-glow);
}
.nav-link:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }
.header-btn.privacy-on {
  color: var(--warning, #d97706);
  background: var(--warning-glow, rgba(217, 119, 6, 0.12));
  border-color: transparent;
}
@media (max-width: 640px) {
  .header-nav {
    order: 2;
    flex: 1 0 100%;
    margin: 0;
    gap: 2px;
    overflow-x: auto;
  }
  .nav-link { flex: 1 0 auto; padding: 7px 10px; }
}
</style>
