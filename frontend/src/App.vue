<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTheme } from './composables/useTheme'
import ToastContainer from './components/ToastContainer.vue'

const router = useRouter()
const { loadTheme } = useTheme()

onMounted(() => {
  loadTheme()
})
</script>

<template>
  <div class="app">
    <router-view v-slot="{ Component }">
      <transition name="fade" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
    <ToastContainer />
  </div>
</template>

<style>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
