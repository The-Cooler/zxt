import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  fetchNotifications,
  fetchUnreadCount,
  markRead as apiMarkRead,
  markAllRead as apiMarkAllRead,
  deleteNotification as apiDeleteNotification
} from '@/apis/notification_api'

export const useNotificationStore = defineStore('notification', () => {
  const notifications = ref([])
  const unreadCount = ref(0)
  const loading = ref(false)

  async function loadNotifications({ unreadOnly = false, limit = 50, offset = 0 } = {}) {
    loading.value = true
    try {
      const res = await fetchNotifications({ unread_only: unreadOnly, limit, offset })
      notifications.value = res.data || []
    } catch (e) {
      console.error('加载通知失败:', e)
    } finally {
      loading.value = false
    }
  }

  async function loadUnreadCount() {
    try {
      const res = await fetchUnreadCount()
      unreadCount.value = res.data?.count || 0
    } catch (e) {
      console.error('获取未读数失败:', e)
    }
  }

  async function markRead(notificationId) {
    try {
      await apiMarkRead(notificationId)
      unreadCount.value = Math.max(0, unreadCount.value - 1)
      const item = notifications.value.find((n) => n.id === notificationId)
      if (item) item.is_read = true
    } catch (e) {
      console.error('标记已读失败:', e)
    }
  }

  async function markAllRead() {
    try {
      await apiMarkAllRead()
      unreadCount.value = 0
      notifications.value.forEach((n) => (n.is_read = true))
    } catch (e) {
      console.error('全部已读失败:', e)
    }
  }

  async function removeNotification(notificationId) {
    try {
      await apiDeleteNotification(notificationId)
      const idx = notifications.value.findIndex((n) => n.id === notificationId)
      if (idx !== -1) {
        if (!notifications.value[idx].is_read) {
          unreadCount.value = Math.max(0, unreadCount.value - 1)
        }
        notifications.value.splice(idx, 1)
      }
    } catch (e) {
      console.error('删除通知失败:', e)
    }
  }

  return {
    notifications,
    unreadCount,
    loading,
    loadNotifications,
    loadUnreadCount,
    markRead,
    markAllRead,
    removeNotification
  }
})
