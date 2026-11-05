<template>
  <aside class="live-feed">
    <div class="feed-head">
      <h2>实时短信</h2>
      <span class="live-dot" :class="{ idle: !loaded }"></span>
      <span class="live-text">{{ loaded ? '10 秒自动刷新' : '读取中…' }}</span>
      <button class="feed-link" title="打开短信记录页" @click="goAll">全部 →</button>
    </div>

    <div class="feed-list" :class="{ empty: !items.length }">
      <div v-if="error" class="feed-empty">
        <p>读取失败</p>
        <button class="feed-retry" @click="load">重试</button>
      </div>
      <div v-else-if="!items.length" class="feed-empty">
        <p>{{ loaded ? '暂无短信' : '加载中…' }}</p>
        <p v-if="loaded" class="hint">板子收到或发出短信后，这里会自动出现</p>
      </div>
      <template v-else>
        <article
          v-for="row in items"
          :key="row.id"
          :class="['feed-item', { fresh: freshIds.has(row.id) }]"
        >
          <div class="item-top">
            <span :class="['dir', row.direction === 'received' ? 'in' : 'out']">
              {{ row.direction === 'received' ? '收' : '发' }}
            </span>
            <span class="item-time">{{ shortTime(row.sms_time) }}</span>
            <span class="item-dev">{{ shortName(row.device_name) }} · 卡{{ String(row.sim_slot || '').slice(-1) === '2' ? 2 : 1 }}</span>
            <span class="item-num">{{ maskText(row.phone) }}</span>
          </div>
          <SmsContent
            class="item-body"
            :content="row.content"
            clamp
            :open="openId === row.id"
            @toggle="openId = openId === row.id ? 0 : row.id"
          />
        </article>
      </template>
    </div>

    <div class="feed-foot">
      <button class="feed-link" @click="goAll">查看全部短信 →</button>
    </div>
  </aside>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import SmsContent from './SmsContent.vue'
import { fetchSmsHistory } from '../api/endpoints'
import { maskText } from '../utils/format'

const LIMIT = 8
// Polling reads the panel's own database; it never talks to the boards, so the
// vendor's "do not poll the device" rule still holds.
const POLL_MS = 10000

const router = useRouter()
const items = ref([])
const loaded = ref(false)
const error = ref(false)
const openId = ref(0)
const freshIds = ref(new Set())

let timer = null
let firstLoad = true

// "X31-第三排" -> "第三排": the model prefix repeats on every row and pushes
// the number out of a 280px rail.
function shortName(name) {
  return String(name || '').replace(/^X31[-\s]*/i, '')
}

function shortTime(value) {
  const s = String(value || '')
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}:\d{2})/)
  if (!m) return s
  const today = new Date()
  const isToday =
    Number(m[1]) === today.getFullYear() &&
    Number(m[2]) === today.getMonth() + 1 &&
    Number(m[3]) === today.getDate()
  return isToday ? m[4] : `${m[2]}-${m[3]} ${m[4]}`
}

async function load() {
  if (document.hidden) return
  try {
    const data = await fetchSmsHistory({ page: 1, pageSize: LIMIT })
    const rows = data.items || []
    // Anything newer than the previous head gets a short highlight so a
    // message that lands while the page is open is noticed without a sound.
    if (!firstLoad && items.value.length) {
      const known = new Set(items.value.map(r => r.id))
      const added = rows.filter(r => !known.has(r.id)).map(r => r.id)
      if (added.length) {
        freshIds.value = new Set(added)
        setTimeout(() => { freshIds.value = new Set() }, 6000)
      }
    }
    items.value = rows
    error.value = false
    firstLoad = false
  } catch {
    // Keep the last good list on a transient failure instead of blanking it.
    error.value = !items.value.length
  } finally {
    loaded.value = true
  }
}

function goAll() {
  router.push('/messages')
}

function onVisible() {
  if (!document.hidden) load()
}

onMounted(() => {
  nextTick(load)
  timer = setInterval(load, POLL_MS)
  document.addEventListener('visibilitychange', onVisible)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  document.removeEventListener('visibilitychange', onVisible)
})
</script>

<style scoped>
.live-feed {
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 12px 14px 10px;
  min-height: 0;
}
.feed-head {
  display: flex;
  align-items: center;
  gap: 7px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}
.feed-head h2 { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--success);
  box-shadow: 0 0 0 3px var(--success-glow);
  margin-left: 2px;
}
.live-dot.idle { background: var(--text-muted); box-shadow: none; }
.live-text { font-size: 11px; color: var(--text-muted); }
.feed-link {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--primary);
  font-size: 12px;
  cursor: pointer;
  padding: 2px 0;
}
.feed-link:hover { color: var(--primary-dark); text-decoration: underline; }
.feed-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
  padding: 10px 2px 6px 0;
}
.feed-list.empty { justify-content: center; }
.feed-item {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 8px 10px;
  transition: background var(--transition), border-color var(--transition);
}
.feed-item:hover { background: var(--bg-card-hover); }
.feed-item.fresh {
  border-color: var(--primary);
  background: var(--primary-glow);
  animation: freshIn 0.35s ease-out;
}
@keyframes freshIn {
  from { transform: translateY(-4px); opacity: 0.4; }
  to { transform: none; opacity: 1; }
}
.item-top {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  row-gap: 2px;
  gap: 6px;
  font-size: 11px;
  color: var(--text-muted);
}
.dir {
  font-size: 10px;
  font-weight: 700;
  border-radius: 4px;
  padding: 1px 5px;
  flex: none;
}
.dir.in { color: var(--success); background: var(--success-glow); }
.dir.out { color: var(--primary); background: var(--primary-glow); }
.item-time { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; flex: none; }
/* Keep the board name readable; when it cannot fit next to the sender
   number, the number wraps to its own line instead of squeezing the name. */
.item-dev { color: var(--text-secondary); flex: 1 1 auto; min-width: 84px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.item-num {
  margin-left: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--text-muted);
  flex: none;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-body {
  margin-top: 5px;
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--text-primary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.item-body.open { display: block; -webkit-line-clamp: unset; }
.feed-empty {
  text-align: center;
  color: var(--text-muted);
  font-size: 12.5px;
  padding: 18px 6px;
}
.feed-empty .hint { margin-top: 6px; font-size: 11.5px; opacity: 0.8; }
.feed-retry {
  margin-top: 8px;
  border: 1px solid var(--border);
  background: var(--bg-input);
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
}
.feed-foot {
  border-top: 1px solid var(--border);
  padding-top: 8px;
  text-align: center;
}
</style>
