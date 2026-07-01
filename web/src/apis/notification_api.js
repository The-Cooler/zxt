import { apiGet, apiPost, apiDelete } from './base'

export async function fetchNotifications(params = {}) {
  return apiGet('/notifications', params)
}

export async function fetchUnreadCount() {
  return apiGet('/notifications/unread-count')
}

export async function markRead(notificationId) {
  return apiPost(`/notifications/${notificationId}/read`)
}

export async function markAllRead() {
  return apiPost('/notifications/read-all')
}

export async function deleteNotification(notificationId) {
  return apiDelete(`/notifications/${notificationId}`)
}
