export function displayName(device) {
  return (device.alias || '').trim() || device.devId || device.ip
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
