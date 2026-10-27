import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const agentCount = ref(0)
  const todayProcessed = ref(0)

  return { agentCount, todayProcessed }
})
