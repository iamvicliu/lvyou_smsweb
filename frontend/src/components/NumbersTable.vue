<script setup>
import { storeToRefs } from 'pinia'

import { useDevicesStore } from '../stores'
import { numberParts, operatorLabel, simTone, simToneHint } from '../utils/format'

const devicesStore = useDevicesStore()
const { filteredNumbers } = storeToRefs(devicesStore)
</script>

<template>
  <div class="records-scroll records-table-only">
    <table v-if="filteredNumbers.length" class="records-table">
      <thead>
        <tr>
          <th style="width:190px">号码</th>
          <th style="width:150px">运营商</th>
          <th>设备</th>
          <th style="width:160px">IP</th>
          <th style="width:80px">槽位</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="n in filteredNumbers" :key="String(n.deviceId) + '-' + String(n.slot)">
          <td class="mono">
            <template v-if="numberParts(n.number).number">
              {{ numberParts(n.number).number }}
              <span v-if="numberParts(n.number).note" class="num-note">{{ numberParts(n.number).note }}</span>
            </template>
            <template v-else>{{ numberParts(n.number).note }}</template>
          </td>
          <td :class="simTone(n.operator)" :title="simToneHint(n.operator)">
            {{ operatorLabel(n.operator) || '-' }}
          </td>
          <td>{{ n.deviceName }}</td>
          <td class="mono">{{ n.ip }}</td>
          <td>SIM{{ n.slot }}</td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty-row">暂无号码数据</div>
  </div>

  <div v-if="filteredNumbers.length" class="record-list">
    <div
      v-for="n in filteredNumbers"
      :key="'m' + String(n.deviceId) + '-' + String(n.slot)"
      class="record-item"
    >
      <div class="record-top">
        <span class="mono number">
          {{ numberParts(n.number).number || numberParts(n.number).note }}
        </span>
        <span v-if="numberParts(n.number).number && numberParts(n.number).note" class="num-note">{{ numberParts(n.number).note }}</span>
        <span class="slot-chip">SIM{{ n.slot }}</span>
      </div>
      <div class="record-sub">
        <span>{{ n.deviceName }}</span>
        <span class="sep">·</span>
        <span class="mono">{{ n.ip }}</span>
        <template v-if="operatorLabel(n.operator)">
          <span class="sep">·</span>
          <span :class="simTone(n.operator)">{{ operatorLabel(n.operator) }}</span>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.number { font-size: 14px; color: var(--text-primary); }
.num-note { margin-left: 6px; font-family: inherit; font-size: 12px; color: var(--text-muted); }
.bad { color: var(--danger); font-weight: 600; }
.warn { color: var(--warning); }
.slot-chip {
  margin-left: auto;
  font-size: 11px;
  font-weight: 600;
  color: var(--primary);
  background: var(--primary-glow);
  border-radius: 999px;
  padding: 1px 8px;
}
</style>
