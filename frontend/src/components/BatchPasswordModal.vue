<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal modal-lg">
      <div class="modal-header">
        <h3>批量修改板子密码</h3>
        <button class="modal-close" @click="emit('close')">×</button>
      </div>

      <div class="modal-body">
        <p class="lead">
          将修改选中的 <strong>{{ deviceCount }}</strong> 台板子的管理员密码，并把面板保存的密码一起更新。
        </p>
        <p class="hint">
          改完后面板原来拿到的控制令牌立即失效，板子会有 1-2 秒断连；
          扫描、配置读取、重启等操作会自动用新密码重新连接。
        </p>

        <div class="field">
          <label>新密码</label>
          <input
            v-model="password"
            class="form-input"
            type="password"
            autocomplete="new-password"
            placeholder="4-64 位，建议字母+数字"
            :disabled="loading"
          />
        </div>
        <div class="field">
          <label>再输一次</label>
          <input
            v-model="repeat"
            class="form-input"
            type="password"
            autocomplete="new-password"
            placeholder="确认新密码"
            :disabled="loading"
            @keyup.enter="submit"
          />
        </div>
        <p v-if="localError" class="msg bad">{{ localError }}</p>

        <div v-if="results.length" class="results">
          <div class="result-summary">
            <span class="ok">成功 {{ okCount }}</span>
            <span :class="['bad', { muted: !failedCount }]">失败 {{ failedCount }}</span>
          </div>
          <div v-for="r in results" :key="r.device_id" class="result-item">
            <span :class="['dot', r.ok ? 'ok' : 'bad']"></span>
            <span class="name">{{ r.name || r.ip }}</span>
            <span class="ip mono">{{ r.ip }}</span>
            <span class="note">{{ r.ok ? '已改并回连成功' : (r.note || '失败') }}</span>
          </div>
        </div>
      </div>

      <div class="modal-footer">
        <button class="btn-cancel" @click="emit('close')">{{ results.length ? '关闭' : '取消' }}</button>
        <button class="btn-confirm" :disabled="loading || results.length > 0" @click="submit">
          {{ loading ? '修改中…' : '开始修改' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  deviceCount: { type: Number, default: 0 },
  loading: { type: Boolean, default: false },
  results: { type: Array, default: () => [] }
})

const emit = defineEmits(['close', 'submit'])

const password = ref('')
const repeat = ref('')
const localError = ref('')

const okCount = computed(() => props.results.filter(r => r.ok).length)
const failedCount = computed(() => props.results.filter(r => !r.ok).length)

function submit() {
  localError.value = ''
  const value = password.value || ''
  if (value.length < 4 || value.length > 64) {
    localError.value = '新密码需为 4-64 个字符'
    return
  }
  if (value !== repeat.value) {
    localError.value = '两次输入的密码不一致'
    return
  }
  emit('submit', value)
}
</script>

<style scoped>
.lead { font-size: 14px; color: var(--text-primary); line-height: 1.6; }
.hint { font-size: 12px; color: var(--text-muted); line-height: 1.6; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field label { font-size: 12px; color: var(--text-secondary); }
.results { display: flex; flex-direction: column; gap: 6px; max-height: 240px; overflow-y: auto; }
.result-summary { display: flex; gap: 14px; font-size: 12px; }
.result-item {
  display: grid; grid-template-columns: 10px 1fr auto; align-items: center; gap: 8px;
  padding: 8px 10px; font-size: 12px;
  background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius-md);
}
.result-item .ip { color: var(--text-muted); }
.result-item .note { grid-column: 2 / -1; color: var(--text-muted); font-size: 11px; }
.dot { width: 8px; height: 8px; border-radius: 50%; }
.dot.ok { background: var(--success); }
.dot.bad { background: var(--danger); }
.name { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ok { color: var(--success); }
.bad { color: var(--danger); }
.muted { color: var(--text-muted); }
.msg.bad { color: var(--danger); font-size: 12px; }
</style>
