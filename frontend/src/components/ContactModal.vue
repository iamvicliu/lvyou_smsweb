<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal modal-md">
      <div class="modal-header">
        <h3>{{ contact ? '编辑联系人' : '添加联系人' }}</h3>
        <button class="modal-close" title="关闭" @click="emit('close')">×</button>
      </div>

      <div class="modal-body">
        <div class="field">
          <label>姓名</label>
          <input
            v-model="name"
            class="form-input"
            maxlength="32"
            placeholder="例如：妈妈、张师傅、物业前台"
            @keyup.enter="submit"
          />
        </div>

        <div class="field">
          <label>号码</label>
          <div v-for="(row, index) in rows" :key="index" class="phone-row">
            <select v-model="row.label" class="filter-select label-select" :disabled="loading">
              <option v-for="item in labelOptions(row.label)" :key="item" :value="item">{{ item }}</option>
            </select>
            <input
              v-model="row.phone"
              class="form-input"
              inputmode="tel"
              :placeholder="index === 0 ? '手机号' : '再加一个号码'"
              :disabled="loading"
            />
            <button
              v-if="rows.length > 1"
              type="button"
              class="row-remove"
              title="删掉这个号码"
              @click="rows.splice(index, 1)"
            >×</button>
          </div>
          <button
            v-if="rows.length < 8"
            type="button"
            class="add-row"
            @click="rows.push({ phone: '', label: '手机' })"
          >+ 再加一个号码</button>
        </div>

        <div class="field">
          <label>备注（可选）</label>
          <input
            v-model="note"
            class="form-input"
            maxlength="200"
            placeholder="例如：楼上邻居、只在晚上联系"
          />
        </div>

        <label class="fav-row">
          <input v-model="favorite" type="checkbox" />
          收藏，排在通讯录最前面
        </label>

        <p v-if="error || localError" class="msg bad">{{ error || localError }}</p>
      </div>

      <div class="modal-footer">
        <button class="btn-cancel" @click="emit('close')">取消</button>
        <button class="btn-confirm" :disabled="loading" @click="submit">
          {{ loading ? '保存中…' : '保存' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const LABELS = ['手机', '工作', '家庭', '主要', '其他']

const props = defineProps({
  contact: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' }
})

const emit = defineEmits(['close', 'save'])

const localError = ref('')
const name = ref(props.contact ? props.contact.name : '')
const note = ref(props.contact ? props.contact.note : '')
const favorite = ref(Boolean(props.contact && props.contact.favorite))
const rows = ref(
  props.contact && props.contact.phones && props.contact.phones.length
    ? props.contact.phones.map(p => ({ phone: p.phone, label: p.label || '手机' }))
    : [{ phone: '', label: '手机' }]
)

// An older row may carry a label that is not in the fixed list; keep it
// selectable instead of silently resetting it to 手机.
function labelOptions(current) {
  const value = String(current || '').trim()
  return value && !LABELS.includes(value) ? [...LABELS, value] : LABELS
}

function submit() {
  if (props.loading) return
  localError.value = ''
  const payload = {
    name: String(name.value || '').trim(),
    note: String(note.value || '').trim(),
    favorite: favorite.value,
    phones: rows.value
      .map(row => ({ phone: String(row.phone || '').trim(), label: String(row.label || '').trim() }))
      .filter(row => row.phone)
  }
  if (!payload.name) {
    localError.value = '请填写姓名'
    return
  }
  if (!payload.phones.length) {
    localError.value = '至少填一个号码'
    return
  }
  emit('save', payload)
}
</script>

<style scoped>
.field { display: flex; flex-direction: column; gap: 6px; }
.field > label { font-size: 12px; color: var(--text-secondary); }
.phone-row { display: flex; align-items: center; gap: 8px; }
.phone-row .form-input { flex: 1; min-width: 0; }
.label-select { width: 100px; flex: none; padding: 10px 30px 10px 10px; }
.row-remove {
  flex: none;
  width: 30px;
  height: 30px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  color: var(--text-muted);
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
}
.row-remove:hover { color: var(--danger); border-color: var(--danger); }
.add-row {
  align-self: flex-start;
  padding: 6px 12px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
  background: none;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
}
.add-row:hover { color: var(--primary); border-color: var(--primary); }
.fav-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
}
</style>
