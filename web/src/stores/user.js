import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUserStore = defineStore('user', () => {
  // 状态
  const userId = ref(null)
  const username = ref('')
  const userIdLogin = ref('')
  const phoneNumber = ref('')
  const avatar = ref('')
  const userRole = ref('')

  // 单人模式固定使用系统最高权限用户。
  const isLoggedIn = computed(() => true)
  const isAdmin = computed(() => true)
  const isSuperAdmin = computed(() => true)

  function getAuthHeaders() {
    return {}
  }

  async function getCurrentUser() {
    return {
      id: userId.value,
      username: username.value,
      user_id: userIdLogin.value,
      role: 'superadmin'
    }
  }

  return {
    // 状态
    userId,
    username,
    userIdLogin,
    phoneNumber,
    avatar,
    userRole,

    // 计算属性
    isLoggedIn,
    isAdmin,
    isSuperAdmin,

    // 方法
    getAuthHeaders,
    getCurrentUser
  }
})

