<template>
  <!-- One slim bar instead of four tall cards: the dashboard's job is the
       device list, so the counters only need to be glanceable. -->
  <div class="stats-bar">
    <div class="stat online">
      <span class="stat-dot"></span>
      <b>{{ online }}</b>
      <span class="stat-label">在线</span>
    </div>
    <div class="stat offline">
      <span class="stat-dot"></span>
      <b>{{ offline }}</b>
      <span class="stat-label">离线</span>
    </div>
    <div class="stat total">
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M17 2H7a2 2 0 00-2 2v16a2 2 0 002 2h10a2 2 0 002-2V4a2 2 0 00-2-2zm-5 19a1 1 0 110-2 1 1 0 010 2zm5-4H7V5h10v12z"/></svg>
      <b>{{ total }}</b>
      <span class="stat-label">设备</span>
    </div>
    <div class="stat sim">
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19 3H9l-6 6v10a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zm-2 14H7v-2h10v2zm0-4H7v-2h10v2zm0-4h-4V6h4v3z"/></svg>
      <b>{{ simCount }}</b>
      <span class="stat-label">SIM卡</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  online: { type: Number, default: 0 },
  offline: { type: Number, default: 0 },
  total: { type: Number, default: 0 },
  simCount: { type: Number, default: 0 },
  // Kept so DashboardView can pass the historical trend series; the slim bar
  // has no sparkline to draw.
  trendData: { type: Object, default: () => ({}) }
})
</script>

<style scoped>
.stats-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 22px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 9px 16px;
  margin-bottom: 14px;
}
.stat { display: flex; align-items: center; gap: 6px; }
.stat + .stat { position: relative; }
.stat b { font-size: 17px; font-weight: 700; letter-spacing: -0.02em; line-height: 1; }
.stat svg { width: 14px; height: 14px; opacity: 0.9; }
.stat-label { font-size: 12px; color: var(--text-muted); }
.stat-dot { width: 7px; height: 7px; border-radius: 50%; }
.stat.online .stat-dot { background: var(--success); box-shadow: 0 0 0 3px var(--success-glow); }
.stat.offline .stat-dot { background: var(--danger); box-shadow: 0 0 0 3px var(--danger-glow); }
.stat.online b { color: var(--success); }
.stat.offline b { color: var(--danger); }
.stat.total { color: var(--primary); }
.stat.sim { color: var(--warning); }
@media (max-width: 640px) {
  .stats-bar { gap: 2px 12px; padding: 8px 12px; }
  .stat b { font-size: 15px; }
  .stat-label { font-size: 11px; }
}
</style>
