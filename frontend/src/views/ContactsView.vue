<template>
  <div class="contacts-view">
    <AppHeader
      :loading="loading"
      :scanning="false"
      :is-dark="isDark"
      @refresh="reload"
      @logout="handleLogout"
      @toggle-theme="toggleTheme"
      @open-settings="$router.push('/settings')"
      @scan="$router.push('/dashboard')"
    />

    <section class="records-panel contacts-panel">
      <div class="panel-head">
        <span class="panel-title">通讯录 <b>{{ contacts.length }}</b></span>
        <div class="panel-filters">
          <input v-model="q" class="search-input" placeholder="搜索姓名 / 号码 / 备注" />
        </div>
        <button
          class="toolbar-btn"
          :class="{ active: onlyFavorite }"
          title="只显示标了收藏的联系人"
          @click="onlyFavorite = !onlyFavorite"
        >只看收藏</button>
        <button class="toolbar-btn" title="添加一个联系人和他的号码" @click="openCreate">添加联系人</button>
      </div>

      <div v-if="filtered.length" class="contact-grid">
        <article v-for="contact in filtered" :key="contact.id" class="contact-card">
          <div class="contact-head">
            <span class="contact-avatar">{{ initial(contact.name) }}</span>
            <div class="contact-title">
              <span class="contact-title-name">{{ contact.name }}</span>
              <span v-if="contact.note" class="contact-note" :title="contact.note">{{ contact.note }}</span>
            </div>
            <button
              class="star-btn"
              :class="{ on: contact.favorite }"
              :title="contact.favorite ? '取消收藏' : '收藏，排到通讯录最前面'"
              @click="toggleFavorite(contact)"
            >★</button>
          </div>

          <div class="contact-phones">
            <div v-for="item in contact.phones" :key="item.id" class="contact-phone-row">
              <span class="phone-tag">{{ item.label || '手机' }}</span>
              <span class="mono">{{ maskText(item.phone) }}</span>
              <button class="copy-btn" title="复制完整号码" @click="copyPhone(item.phone)">复制</button>
            </div>
          </div>

          <div class="contact-actions">
            <button class="btn-secondary mini" title="到首页用这张号码发短信" @click="goSend(contact)">发短信</button>
            <button class="btn-secondary mini" title="到首页用这张号码拨号" @click="goDial(contact)">拨号</button>
            <span class="contact-spacer"></span>
            <button class="btn-secondary mini" @click="openEdit(contact)">编辑</button>
            <button class="btn-secondary mini danger" @click="remove(contact)">删除</button>
          </div>
        </article>
      </div>
      <div v-else class="empty-row">
        <span v-if="loading" class="spinner spinner-muted"></span>
        <span>{{ loading ? '正在读取联系人…' : (q || onlyFavorite ? '没有匹配的联系人' : '还没有联系人，点右上角「添加联系人」') }}</span>
      </div>
    </section>

    <ContactModal
      v-if="showModal"
      :contact="editing"
      :loading="saving"
      :error="saveError"
      @close="closeModal"
      @save="save"
    />
    <ConfirmModal />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppHeader from '../components/AppHeader.vue'
import ContactModal from '../components/ContactModal.vue'
import ConfirmModal from '../components/ConfirmModal.vue'
import { useAuthStore, useDialogStore } from '../stores'
import { createContact, deleteContact, setContactFavorite, updateContact } from '../api/endpoints'
import { useContactsStore } from '../stores/contacts'
import { useTheme } from '../composables/useTheme'
import { useNotice } from '../composables/useNotice'
import { useToast } from '../composables/useToast'
import { maskText } from '../utils/format'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const dialogStore = useDialogStore()
const contactsStore = useContactsStore()
const { isDark, toggleTheme } = useTheme()
const { errText } = useNotice()
const toast = useToast()

const q = ref('')
const onlyFavorite = ref(false)
const loading = ref(true)
const saving = ref(false)
const saveError = ref('')
const showModal = ref(false)
const editing = ref(null)

const contacts = computed(() => contactsStore.list)

const filtered = computed(() => {
  const needle = q.value.trim().toLowerCase()
  return contacts.value.filter(contact => {
    if (onlyFavorite.value && !contact.favorite) return false
    if (!needle) return true
    return String(contact.name || '').toLowerCase().includes(needle)
      || String(contact.note || '').toLowerCase().includes(needle)
      || (contact.phones || []).some(item => String(item.phone || '').includes(needle))
  })
})

function initial(name) {
  return String(name || '?').trim().slice(0, 1).toUpperCase()
}

async function reload() {
  loading.value = true
  try {
    await contactsStore.load(true)
  } catch (e) {
    toast.showToast(errText(e, '读取通讯录失败'), 'error')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  saveError.value = ''
  showModal.value = true
}

function openEdit(contact) {
  editing.value = contact
  saveError.value = ''
  showModal.value = true
}

function closeModal() {
  if (saving.value) return
  showModal.value = false
  editing.value = null
  saveError.value = ''
}

async function save(payload) {
  saving.value = true
  saveError.value = ''
  try {
    if (editing.value) {
      await updateContact(editing.value.id, payload)
      toast.showToast('联系人已更新', 'success')
    } else {
      await createContact(payload)
      toast.showToast('联系人已添加', 'success')
    }
    showModal.value = false
    editing.value = null
    await contactsStore.load(true)
  } catch (e) {
    saveError.value = errText(e, '保存失败')
  } finally {
    saving.value = false
  }
}

async function toggleFavorite(contact) {
  try {
    await setContactFavorite(contact.id, !contact.favorite)
    await contactsStore.load(true)
  } catch (e) {
    toast.showToast(errText(e, '收藏失败'), 'error')
  }
}

async function remove(contact) {
  const ok = await dialogStore.confirm({
    title: '删除联系人',
    message: `删除「${contact.name}」和他的 ${contact.phones.length} 个号码？\n\n短信和通话记录不受影响，只是以后不再显示姓名。`,
    confirmText: '删除',
    danger: true
  })
  if (!ok) return
  try {
    await deleteContact(contact.id)
    toast.showToast('联系人已删除', 'success')
    await contactsStore.load(true)
  } catch (e) {
    toast.showToast(errText(e, '删除失败'), 'error')
  }
}

async function copyPhone(phone) {
  try {
    await navigator.clipboard.writeText(phone)
  } catch (e) {
    // Plain-http origins reject the async clipboard API; the textarea trick
    // still works there.
    const el = document.createElement('textarea')
    el.value = phone
    document.body.appendChild(el)
    el.select()
    document.execCommand('copy')
    el.remove()
  }
  toast.showToast('号码已复制', 'success')
}

function goSend(contact) {
  const phone = contact.phones[0] && contact.phones[0].phone
  if (!phone) return
  router.push({ path: '/dashboard', query: { to: phone, mode: 'sms' } })
}

function goDial(contact) {
  const phone = contact.phones[0] && contact.phones[0].phone
  if (!phone) return
  router.push({ path: '/dashboard', query: { to: phone, mode: 'dial' } })
}

async function handleLogout() {
  await authStore.logout()
  router.push('/login')
}

onMounted(async () => {
  if (!(await authStore.restore())) {
    router.push('/login')
    return
  }
  if (route.query.q) q.value = String(route.query.q)
  await reload()
})
</script>

<style scoped>
.contacts-view { padding: 24px; max-width: 1440px; margin: 0 auto; }
.contacts-panel { padding-bottom: 18px; }
.contact-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
  padding: 2px 0 8px;
}
.contact-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  transition: border-color var(--transition), transform var(--transition);
}
.contact-card:hover { border-color: var(--border-light); }
.contact-head { display: flex; align-items: center; gap: 10px; }
.contact-avatar {
  flex: none;
  width: 38px;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--primary-glow);
  color: var(--primary);
  font-size: 16px;
  font-weight: 700;
}
.contact-title { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.contact-title-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.contact-note {
  font-size: 12px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.star-btn {
  flex: none;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 50%;
  background: none;
  color: var(--border-light);
  font-size: 17px;
  cursor: pointer;
  transition: color var(--transition), background var(--transition);
}
.star-btn:hover { background: var(--bg-input); color: var(--warning, #f59e0b); }
.star-btn.on { color: var(--warning, #f59e0b); }
.contact-phones { display: flex; flex-direction: column; gap: 6px; }
.contact-phone-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}
.phone-tag {
  flex: none;
  min-width: 34px;
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--bg-input);
  color: var(--text-muted);
  font-size: 11px;
  text-align: center;
}
.copy-btn {
  margin-left: auto;
  padding: 2px 8px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: none;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
}
.copy-btn:hover { color: var(--primary); border-color: var(--border); }
.contact-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px solid var(--border);
}
.contact-spacer { flex: 1; }
.contact-actions .mini { padding: 4px 10px; font-size: 12px; }
.contact-actions .danger { color: var(--danger); }
.contact-actions .danger:hover { border-color: var(--danger); }
@media (max-width: 640px) {
  .contacts-view { padding: 14px; }
  .contact-grid { grid-template-columns: 1fr; padding: 2px 0 8px; }
}
</style>
