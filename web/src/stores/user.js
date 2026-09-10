import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  // 状态
  const userId = ref('system-owner')
  const username = ref('系统所有者')
  const phoneNumber = ref('')
  const avatar = ref('')
  const userRole = ref('owner')

  async function getCurrentUser() {
    return {
      user_id: userId.value,
      username: username.value,
      role: userRole.value
    }
  }

  return {
    // 状态
    userId,
    username,
    phoneNumber,
    avatar,
    userRole,

    // 方法
    getCurrentUser
  }
})

