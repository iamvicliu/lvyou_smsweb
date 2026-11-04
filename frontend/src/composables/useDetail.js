import { ref } from 'vue'

import { dialDevice, fetchDeviceDetail, saveDeviceSim } from '../api/endpoints'
import { useDevicesStore } from '../stores'
import { useLoading } from './useLoading'
import { useNotice } from './useNotice'
import { usePhonebook } from './usePhonebook'

// Device detail modal + inline SIM number edit/save. Singleton state shared by
// the device table row action and DetailModal.
const showDetailModal = ref(false)
const deviceDetail = ref(null)

// The number the operator calls to identify an unknown SIM. It lives in the
// shared phone book, so the dashboard recipient field and the quick-dial
// buttons never drift apart or ask for the same number twice.
const { primaryPhone, savedPhones, rememberPhone, forgetPhone } = usePhonebook()
const myPhone = primaryPhone
const setMyPhone = rememberPhone

export function useDetail() {
  const loading = useLoading()
  const { setNotice, errText } = useNotice()
  const devicesStore = useDevicesStore()

  async function showDetail(device) {
    loading.value = true
    try {
      const response = await fetchDeviceDetail(device.id)
      deviceDetail.value = response.data
      showDetailModal.value = true
    } catch (e) {
      setNotice(errText(e, '获取详情失败'), 'err')
    } finally {
      loading.value = false
    }
  }

  function closeDetailModal() {
    showDetailModal.value = false
    deviceDetail.value = null
  }

  async function saveSimSingle() {
    const id = deviceDetail.value && deviceDetail.value.device && deviceDetail.value.device.id
    if (!id) return
    loading.value = true
    try {
      const res = await saveDeviceSim(id, {
        sim1: deviceDetail.value.device.sim1number || '',
        sim2: deviceDetail.value.device.sim2number || ''
      })
      const board = res.data && res.data.board
      if (board === 'updated') setNotice('已保存，卡号已同步到板子', 'ok')
      else if (board === 'label') setNotice('已保存标签（只存面板，不写入板子）', 'ok')
      else setNotice('已保存到面板（板子暂时没同步）', 'ok')
      await devicesStore.refresh()
    } catch (e) {
      setNotice(errText(e, '保存失败'), 'err')
    } finally {
      loading.value = false
    }
  }

  function updateDetailSim(field, value) {
    if (deviceDetail.value && deviceDetail.value.device) {
      deviceDetail.value.device[field] = value
    }
  }

  // Dial the operator's own phone from one slot: the caller ID on the phone is
  // the SIM's number, which is the only reliable way to read it when the
  // carrier does not store MSISDN on the card. 20s cap so an unanswered call
  // cannot hold the line.
  async function quickDial(slot) {
    const device = deviceDetail.value && deviceDetail.value.device
    if (!device) return
    const phone = String(myPhone.value || '').trim()
    if (!/^\+?[0-9]{5,15}$/.test(phone)) {
      setNotice('请先填写你的手机号', 'err')
      return
    }
    loading.value = true
    try {
      const res = await dialDevice({
        deviceId: device.id,
        slot,
        phone,
        tts: '',
        duration: 20,
        tts_times: 0,
        after_action: 0
      })
      if (res && res.data && res.data.ok === false) {
        throw new Error(res.data.error || '拨号失败')
      }
      setNotice(`卡${slot} 已拨出，看你手机上的来电号码`, 'ok')
    } catch (e) {
      setNotice(errText(e, '拨号失败'), 'err')
    } finally {
      loading.value = false
    }
  }

  return {
    showDetailModal,
    deviceDetail,
    myPhone,
    savedPhones,
    setMyPhone,
    forgetPhone,
    showDetail,
    closeDetailModal,
    saveSimSingle,
    updateDetailSim,
    quickDial
  }
}
