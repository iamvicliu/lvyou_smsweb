<template>
  <div class="sms-section">
    <div class="section-header">
      <h2>消息发送</h2>
      <div class="mode-tabs">
        <button :class="['mode-tab', { active: mode === 'sms' }]" @click="emit('update:mode', 'sms')">短信</button>
        <button :class="['mode-tab', { active: mode === 'dial' }]" @click="emit('update:mode', 'dial')">拨号</button>
      </div>
    </div>

    <div v-show="mode === 'sms'" class="send-form">
      <div class="sender-cell">
        <SenderSelect :numbers="numbers" :value="sender" @update:value="emit('update:sender', $event)" />
      </div>
      <div class="number-cell">
        <input
          :value="toPhone"
          class="form-input"
          list="saved-phone-list"
          inputmode="tel"
          placeholder="收件人号码，发过一次就会记住"
          @input="emit('update:toPhone', $event.target.value)"
        />
        <div v-if="savedPhones.length" class="saved-row">
          <span class="saved-label">常用</span>
          <button
            v-for="phone in savedPhones.slice(0, 4)"
            :key="phone"
            type="button"
            class="saved-chip"
            :title="phone + '（右键或长按可移出常用）'"
            @click="emit('update:toPhone', phone)"
            @contextmenu.prevent="forgetPhone(phone)"
          >{{ maskPhone(phone) }}</button>
        </div>
      </div>
      <button class="btn-send" :disabled="loading || !sender || !toPhone || !content" @click="emit('send')">发送</button>
      <textarea :value="content" class="form-textarea" placeholder="短信内容..." rows="2" @input="emit('update:content', $event.target.value)"></textarea>
    </div>

    <div v-show="mode === 'dial'" class="send-form">
      <div class="sender-cell">
        <SenderSelect :numbers="numbers" :value="sender" @update:value="emit('update:sender', $event)" />
      </div>
      <div class="number-cell">
        <input
          :value="dialPhone"
          class="form-input"
          list="saved-phone-list"
          inputmode="tel"
          placeholder="拨打的号码"
          @input="emit('update:dialPhone', $event.target.value)"
        />
        <div v-if="savedPhones.length" class="saved-row">
          <span class="saved-label">常用</span>
          <button
            v-for="phone in savedPhones.slice(0, 4)"
            :key="phone"
            type="button"
            class="saved-chip"
            :title="phone + '（右键或长按可移出常用）'"
            @click="emit('update:dialPhone', phone)"
            @contextmenu.prevent="forgetPhone(phone)"
          >{{ maskPhone(phone) }}</button>
        </div>
      </div>
      <button class="btn-send" :disabled="loading || !sender || !dialPhone" @click="emit('dial')">拨号</button>
      <textarea :value="ttsText" class="form-textarea" placeholder="TTS内容（可选）..." rows="2" @input="emit('update:ttsText', $event.target.value)"></textarea>
    </div>

    <datalist id="saved-phone-list">
      <option v-for="phone in savedPhones" :key="phone" :value="phone"></option>
    </datalist>
  </div>
</template>

<script setup>
import SenderSelect from './SenderSelect.vue'
import { usePhonebook } from '../composables/usePhonebook'

defineProps({
  mode: { type: String, default: 'sms' },
  numbers: { type: Array, default: () => [] },
  sender: { type: String, default: '' },
  toPhone: { type: String, default: '' },
  content: { type: String, default: '' },
  dialPhone: { type: String, default: '' },
  ttsText: { type: String, default: '' },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits([
  'update:mode',
  'update:sender',
  'update:toPhone',
  'update:content',
  'update:dialPhone',
  'update:ttsText',
  'send',
  'dial'
])

const { savedPhones, forgetPhone } = usePhonebook()

// Numbers are personal data: the chips show only the last four digits, the
// full value stays in the input and the tooltip.
function maskPhone(phone) {
  const value = String(phone || '')
  return value.length > 7 ? `${value.slice(0, 3)}****${value.slice(-4)}` : value
}
</script>

<style scoped>
/* Two rows: picker + recipient + send on top, message body underneath. */
.send-form {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
}
.sender-cell { min-width: 0; }
.number-cell { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; min-width: 0; }
.number-cell .form-input { flex: 1; min-width: 170px; padding: 9px 12px; }
.saved-row { display: flex; align-items: center; gap: 5px; flex-wrap: wrap; }
.saved-label { font-size: 11px; color: var(--text-muted); }
.saved-chip {
  background: var(--bg-input); border: 1px solid var(--border);
  color: var(--text-secondary); border-radius: 999px;
  padding: 3px 9px; font-size: 11px; line-height: 1.4; cursor: pointer;
  font-family: 'JetBrains Mono', 'SF Mono', ui-monospace, monospace;
}
.saved-chip:hover { border-color: var(--primary); color: var(--primary); }
.btn-send {
  height: 38px;
  padding: 0 22px;
  border: none;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  color: white;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all var(--transition);
}
.btn-send:hover:not(:disabled) { transform: translateY(-1px); box-shadow: var(--shadow-glow); }
.btn-send:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }
.form-textarea {
  grid-column: 1 / -1;
  width: 100%;
  min-height: 52px;
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 9px 12px;
  color: var(--text-primary);
  font-family: inherit;
  font-size: 14px;
  line-height: 1.5;
  resize: vertical;
  outline: none;
  transition: border-color var(--transition), box-shadow var(--transition);
}
.form-textarea:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-glow); }
@media (max-width: 720px) {
  .send-form { grid-template-columns: 1fr; }
  /* Single column: keep the button after the body text, not between the
     number field and the message. */
  .send-form .form-textarea { order: 3; }
  .btn-send { order: 4; width: 100%; }
}
</style>
