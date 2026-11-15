import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { api } from '@/services/api'

export type ApiStatus = 'checking' | 'online' | 'offline'

export const useSystemStore = defineStore('system', () => {
  const apiStatus = ref<ApiStatus>('checking')
  const lastCheckedAt = ref<Date | null>(null)

  const statusLabel = computed(() => {
    if (apiStatus.value === 'online') return '业务服务正常'
    if (apiStatus.value === 'offline') return '业务服务未连接'
    return '正在检查服务'
  })

  async function checkApi() {
    apiStatus.value = 'checking'
    try {
      await api.health()
      apiStatus.value = 'online'
    } catch {
      apiStatus.value = 'offline'
    } finally {
      lastCheckedAt.value = new Date()
    }
  }

  return { apiStatus, lastCheckedAt, statusLabel, checkApi }
})
