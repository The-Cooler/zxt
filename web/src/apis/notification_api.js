import { apiGet, apiPost, apiDelete } from './base'

export async function fetchNotifications(params = {}) {
  return apiGet('/api/notifications', params)
}

export async function fetchUnreadCount() {
  return apiGet('/api/notifications/unread-count')
}

export async function markRead(notificationId) {
  return apiPost(`/api/notifications/${notificationId}/read`)
}

export async function markAllRead() {
  return apiPost('/api/notifications/read-all')
}

export async function deleteNotification(notificationId) {
  return apiDelete(`/api/notifications/${notificationId}`)
}
