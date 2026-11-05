import { masked } from '../stores/privacy'

export function displayName(device) {
  return (device.alias || '').trim() || device.devId || device.ip
}

// Masking is applied at render time so the underlying data (and the clipboard
// copy of a verification code) stays intact while screenshots do not leak a
// number. Any digit run of four or more is treated as sensitive.
export function maskText(value) {
  const s = String(value ?? '')
  if (!masked.value) return s
  return s.replace(/\d{4,}/g, (run) => (
    run.length >= 7 ? `${run.slice(0, 3)}****${run.slice(-2)}` : '****'
  ))
}

export function prettyTime(ts) {
  if (!ts) return '-'
  const d = new Date(ts * 1000)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

// History rows store the slot as "sim1"/"sim2"; show the board's own number
// next to it so two SIMs of one device are distinguishable at a glance.
export function simLabel(slot, number) {
  const label = '卡' + (String(slot || '').slice(-1) === '2' ? '2' : '1')
  const digits = String(number || '').replace(/[^0-9+]/g, '')
  return digits ? `${label} · ${digits}` : label
}

// The board's SIM status string usually carries the signal at the end
// ("电信(46011) 69%"). Every view renders the signal as its own badge, so
// drop the duplicate here instead of showing "69%" twice.
export function operatorLabel(op) {
  return String(op || '').replace(/\s*\d{1,3}\s*%\s*$/, '').trim()
}

// The number field doubles as a note field ("13900000000电信米粉"), so split
// the leading digits from the free text to render the note quieter.
export function numberParts(raw) {
  const s = String(raw || '').trim()
  const m = s.match(/^([+\d][\d\s-]*)(.*)$/)
  if (!m) return { number: '', note: s }
  return { number: m[1].trim(), note: m[2].trim() }
}

// The board reports SIM state in the same field as the carrier name. States
// that mean "this card cannot be used" must look different from a carrier.
const SIM_BAD = ['拒绝', '卡异常', '异常', '受限', '未注册', '欠费', '停机', '故障', 'pin', 'puk']
const SIM_WARN = ['启动', '搜索', '注册中', '初始化', '飞行']
// 空卡槽不是故障：弱黄色提示"这里没插卡"，与红色错误、灰色正常区分开。
const SIM_NONE = ['无卡', '未插卡', '未检测到卡']

export function simTone(operator) {
  const s = operatorLabel(operator).toLowerCase()
  if (!s) return ''
  if (SIM_NONE.some(k => s.includes(k))) return 'none'
  if (SIM_BAD.some(k => s.includes(k))) return 'bad'
  if (SIM_WARN.some(k => s.includes(k))) return 'warn'
  return ''
}

export function simToneHint(operator) {
  const tone = simTone(operator)
  if (tone === 'bad') return '板子报告这张卡当前不可用（拒绝 / 卡异常 / 停机等）'
  if (tone === 'warn') return '这张卡还在注册网络，稍后再看'
  if (tone === 'none') return '这个卡槽没有插卡：不是故障，也不影响另一张卡'
  return ''
}

export function groupLabel(grp) {
  const g = String(grp || '').trim()
  if (!g || g.toLowerCase() === 'auto') return '未分组'
  return g
}

// ── 链路与运行指标 ─────────────────────────────────────────────────────────
// 998 心跳是唯一允许的持续信号（厂商文档禁止定时 stat）。这里只做展示，
// 判断逻辑在 backend/linkhealth.py，阈值同样来自厂商的 3×间隔+15 秒。
export function agoText(seconds) {
  const s = Number(seconds)
  if (!Number.isFinite(s) || s < 0) return ''
  if (s < 60) return '刚刚'
  const m = Math.floor(s / 60)
  if (m < 60) return `${m} 分钟前`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h} 小时前`
  return `${Math.floor(h / 24)} 天前`
}

export function linkView(link) {
  const h = link || {}
  const status = h.status || 'unknown'
  const ago = agoText(h.age)
  const interval = Number(h.interval) || 110
  if (status === 'ok') {
    return {
      tone: 'ok',
      label: `链路正常${ago ? ' · ' + ago : ''}`,
      hint: `板子到面板这一段正常，最近一次心跳 ${ago || '刚刚'}（约每 ${interval} 秒一次）`
    }
  }
  if (status === 'late') {
    return {
      tone: 'late',
      label: `链路延迟${ago ? ' · ' + ago : ''}`,
      hint: `心跳比平时慢：板子可能卡顿或网络不稳。正常间隔约 ${interval} 秒`
    }
  }
  if (status === 'down') {
    return {
      tone: 'down',
      label: `链路中断${ago ? ' · ' + ago : ''}`,
      hint: `超过 ${h.threshold || 345} 秒没有心跳：板子掉线，或它连不上面板（短信进不来通常是这个原因）`
    }
  }
  return {
    tone: 'unknown',
    label: '暂无心跳',
    hint: '面板还没收到这块板子的 998 心跳。点右上角「刷新数据」会读一次运行信息'
  }
}

// uptime 的单位是分钟，和 stat 返回的字段一致。
export function uptimeShort(minutes) {
  const m = Number(minutes)
  if (!Number.isFinite(m) || m < 0) return ''
  if (m < 60) return `${m} 分钟`
  const d = Math.floor(m / 1440)
  const h = Math.floor((m % 1440) / 60)
  if (d) return `${d} 天 ${h} 小时`
  return `${h} 小时`
}

export function memoryTone(value) {
  const v = Number(value)
  if (!Number.isFinite(v) || v < 0) return ''
  if (v < 20) return 'bad'
  if (v < 40) return 'warn'
  return ''
}
