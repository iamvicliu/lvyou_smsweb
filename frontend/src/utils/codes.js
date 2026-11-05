// Boards forward whatever the carrier sent. Verification codes are 4-8 digit
// runs; anything adjacent to a separator is a date or a time, and a 4-digit
// year in range is never a code.
const CODE_RE = /(?<!\d)(\d{4,8})(?!\d)/g
const SEPARATORS = '-/:.,'
// Without a keyword the message is a notice, an ad or a service number
// ("10086", "工号 OP2752631"). Highlighting those made every marketing SMS
// look actionable, so chips are only drawn for messages that announce a code.
// English words need word boundaries: a marketing SMS once matched "pin"
// inside a URL fragment ("#7lHPInY") and turned the service number 10085 into
// a verification code.
const KEYWORDS = /(验证码|校验码|动态码|确认码|验证代码|动态密码|授权码|登录码|口令)|\b(code|otp)\b/i

export function extractCodes(text) {
  const source = String(text || '')
  if (!KEYWORDS.test(source)) return []
  const out = []
  let match
  CODE_RE.lastIndex = 0
  while ((match = CODE_RE.exec(source))) {
    const code = match[1]
    const before = source[match.index - 1] || ''
    const after = source[match.index + code.length] || ''
    if (SEPARATORS.includes(before) || SEPARATORS.includes(after)) continue
    // "OP2752631" is an operator id, not a code.
    if (/[A-Za-z]/.test(before)) continue
    const value = Number(code)
    if (code.length === 4 && value >= 1990 && value <= 2099) continue
    out.push({ code, start: match.index, end: match.index + code.length })
  }
  return out
}

export function splitByCodes(text) {
  const source = String(text || '')
  const segments = []
  let cursor = 0
  for (const item of extractCodes(source)) {
    if (item.start > cursor) segments.push({ text: source.slice(cursor, item.start) })
    segments.push({ text: item.code, code: true })
    cursor = item.end
  }
  if (cursor < source.length) segments.push({ text: source.slice(cursor) })
  return segments
}
