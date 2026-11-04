<template>
  <div class="sender-picker">
    <CustomSelect
      :options="boardOptions"
      :value="boardValue"
      placeholder="选择板子"
      @update:value="pickBoard"
    />
    <div class="slot-chips">
      <button
        v-for="slot in slotOptions"
        :key="slot.slot"
        type="button"
        :class="['slot-chip', { active: value === slot.value }]"
        :disabled="!slot.number"
        :title="slot.title"
        @click="emit('update:value', slot.value)"
      >
        <span class="chip-name">{{ slot.label }}</span>
        <span class="chip-num">{{ slot.number || '无号码' }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import CustomSelect from './CustomSelect.vue'

const props = defineProps({
  numbers: { type: Array, default: () => [] },
  value: { type: String, default: '' }
})

const emit = defineEmits(['update:value'])

// A board with two usable cards needs two decisions, not one flat list of
// numbers; the picker is therefore board first, then card.
const boards = computed(() => {
  const map = new Map()
  for (const n of props.numbers) {
    const id = String(n.deviceId)
    if (!map.has(id)) {
      map.set(id, {
        value: id,
        label: `${n.deviceName || n.ip || id} · ${n.ip || ''}`.trim(),
        slots: {}
      })
    }
    map.get(id).slots[String(n.slot)] = n
  }
  return [...map.values()]
})

const boardOptions = computed(() => boards.value.map(b => ({ value: b.value, label: b.label })))

const current = computed(() => {
  const [deviceId, slot] = String(props.value || '').split('|')
  return { deviceId: deviceId || '', slot: slot || '' }
})

// The dropdown keeps its own board so that picking a board whose cards are all
// unregistered still shows that board instead of silently snapping back.
const pickedBoard = ref('')

const boardValue = computed(() => {
  if (current.value.deviceId) return current.value.deviceId
  if (pickedBoard.value) return pickedBoard.value
  // Nothing picked yet: preselect the first board so the card buttons below
  // are meaningful instead of a dead row.
  return boards.value[0]?.value || ''
})

const slotOptions = computed(() => {
  const board = boards.value.find(b => b.value === boardValue.value)
  if (!board) return []
  return [1, 2].map(slot => {
    const entry = board.slots[String(slot)]
    return {
      slot,
      value: `${board.value}|${slot}`,
      number: entry?.number || '',
      label: `卡${slot}`,
      title: entry
        ? `${entry.number}${entry.operator ? ' · ' + entry.operator : ''}`
        : `卡槽 ${slot} 没有登记号码`
    }
  })
})

function pickBoard(deviceId) {
  pickedBoard.value = deviceId
  const board = boards.value.find(b => b.value === deviceId)
  if (!board) return
  const firstFilled = [1, 2].find(slot => board.slots[String(slot)]?.number)
  if (!firstFilled) {
    // Both cards unregistered: leave the value alone so the send button stays
    // honest about there being no usable sender.
    emit('update:value', '')
    return
  }
  emit('update:value', `${deviceId}|${firstFilled}`)
}

// Keep the selection usable without extra clicks: pick the first card that has
// a number, and drop a selection whose board/slot disappeared after a refresh.
watch(
  () => [props.numbers, props.value],
  () => {
    const [deviceId, slot] = String(props.value || '').split('|')
    const stillValid = props.numbers.some(
      n => String(n.deviceId) === deviceId && String(n.slot) === slot
    )
    if (stillValid) return
    // Honour a board the operator just picked; only fall back to the first
    // usable board when there is no choice to respect.
    if (pickedBoard.value) {
      const board = boards.value.find(b => b.value === pickedBoard.value)
      const filled = board && [1, 2].find(s => board.slots[String(s)]?.number)
      if (filled) emit('update:value', `${board.value}|${filled}`)
      return
    }
    for (const board of boards.value) {
      const filled = [1, 2].find(s => board.slots[String(s)]?.number)
      if (filled) {
        emit('update:value', `${board.value}|${filled}`)
        return
      }
    }
    if (props.value) emit('update:value', '')
  },
  { immediate: true }
)
</script>

<style scoped>
.sender-picker { display: flex; align-items: center; gap: 10px; }
.sender-picker > :first-child { flex: 1; min-width: 0; }
.slot-chips { display: flex; gap: 8px; flex-shrink: 0; }
.slot-chip {
  display: flex; flex-direction: column; align-items: flex-start; gap: 2px;
  min-width: 104px; padding: 7px 12px; cursor: pointer;
  background: var(--bg-input); border: 1px solid var(--border);
  border-radius: var(--radius-md); color: var(--text-primary);
  transition: border-color 0.15s, background 0.15s;
}
.slot-chip:hover:not(:disabled) { border-color: var(--border-light); }
.slot-chip.active { border-color: var(--primary); background: var(--primary-glow); }
.slot-chip:disabled { opacity: 0.45; cursor: not-allowed; }
.chip-name { font-size: 11px; color: var(--text-muted); }
.slot-chip.active .chip-name { color: var(--primary); }
.chip-num {
  font-size: 13px; max-width: 128px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
@media (max-width: 720px) {
  .sender-picker { flex-direction: column; align-items: stretch; }
  .slot-chips { width: 100%; }
  .slot-chip { flex: 1; min-width: 0; }
}
</style>
