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

export function simTone(operator) {
  const s = operatorLabel(operator).toLowerCase()
  if (!s) return ''
  if (SIM_BAD.some(k => s.includes(k))) return 'bad'
  if (SIM_WARN.some(k => s.includes(k))) return 'warn'
  return ''
}

export function simToneHint(operator) {
  const tone = simTone(operator)
  if (tone === 'bad') return '板子报告这张卡当前不可用（拒绝 / 卡异常 / 停机等）'
  if (tone === 'warn') return '这张卡还在注册网络，稍后再看'
  return ''
}

export function groupLabel(grp) {
  const g = String(grp || '').trim()
  if (!g || g.toLowerCase() === 'auto') return '未分组'
  return g
}
