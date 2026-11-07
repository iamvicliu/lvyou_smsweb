// Same normalisation as backend/routes/contacts.py: people type spaces,
// dashes and brackets, and a lookup must still hit the stored number.
export function normalizePhone(value) {
  return String(value || '').replace(/[\s\-()（）.]+/g, '').trim()
}

// Boards report the same line as 13…, 8613…, +8613… or 008613… depending on
// the operator. Lookups compare this canonical form so a contact matches every
// variant of their number in the SMS and call history.
export function phoneKey(value) {
  let phone = normalizePhone(value)
  if (phone.startsWith('00')) phone = phone.slice(2)
  if (phone.startsWith('+')) phone = phone.slice(1)
  if (phone.startsWith('86') && phone.length === 13) phone = phone.slice(2)
  return phone
}

// Screenshot mode keeps the first three and last four digits so two numbers
// from the same operator stay distinguishable.
export function maskPhone(value) {
  const phone = String(value || '')
  if (phone.length < 8) return phone
  return `${phone.slice(0, 3)}****${phone.slice(-4)}`
}
