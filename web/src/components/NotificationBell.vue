<template>
  <a-popover v-model:open="popoverVisible" placement="topRight" trigger="click" overlay-class-name="notification-popover">
    <template #content>
      <div class="notification-panel">
        <div class="notification-header">
          <span class="notification-title">通知</span>
          <a-button v-if="store.unreadCount > 0" type="link" size="small" @click="handleMarkAllRead">
            全部已读
          </a-button>
        </div>
        <div class="notification-list">
          <a-spin v-if="store.loading" />
          <template v-else-if="store.notifications.length">
            <div
              v-for="item in store.notifications"
              :key="item.id"
              class="notification-item"
              :class="{ unread: !item.is_read }"
            >
              <div class="notification-dot" :class="`severity-${item.severity}`" />
              <div class="notification-body">
                <div class="notification-item-title">{{ item.title }}</div>
                <div v-if="item.body" class="notification-item-text">{{ item.body }}</div>
                <div class="notification-item-meta">
                  <span v-if="item.source" class="notification-source">{{ item.source }}</span>
                  <span class="notification-time">{{ formatTime(item.created_at) }}</span>
                </div>
              </div>
              <button class="notification-dismiss" @click.stop="handleDismiss(item.id)">
                <X size="14" />
              </button>
            </div>
          </template>
          <a-empty v-else description="暂无通知" :image-style="{ height: '40px' }" />
        </div>
      </div>
    </template>
    <a-badge :count="store.unreadCount" :overflow-count="99" size="small">
      <Bell class="icon" size="16" />
    </a-badge>
  </a-popover>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { Bell, X } from 'lucide-vue-next'
import { useNotificationStore } from '@/stores/notification'

const store = useNotificationStore()
const popoverVisible = ref(false)
let pollTimer = null

onMounted(() => {
  store.loadUnreadCount()
  pollTimer = setInterval(() => store.loadUnreadCount(), 60000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})

function handleMarkAllRead() {
  store.markAllRead()
}

function handleDismiss(id) {
  store.removeNotification(id)
}

function formatTime(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diffMs = now - d
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin}分钟前`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}小时前`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay < 7) return `${diffDay}天前`
  return d.toLocaleDateString()
}

// 打开 popover 时加载通知列表
import { watch } from 'vue'
watch(popoverVisible, (v) => {
  if (v) store.loadNotifications({ limit: 30 })
})
</script>

<style scoped>
.icon {
  cursor: pointer;
  color: var(--gray-600);
  transition: color 0.2s;
}

.icon:hover {
  color: var(--gray-900);
}
</style>

<style>
.notification-popover .ant-popover-inner {
  padding: 0;
  width: 360px;
}

.notification-popover .ant-popover-inner-content {
  padding: 0;
}
</style>

<style scoped>
.notification-panel {
  max-height: 480px;
  display: flex;
  flex-direction: column;
}

.notification-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--gray-150);
}

.notification-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-1000);
}

.notification-list {
  overflow: auto;
  max-height: 420px;
}

.notification-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--gray-100);
  cursor: default;
  transition: background 0.15s;
}

.notification-item:hover {
  background: var(--gray-25);
}

.notification-item.unread {
  background: var(--main-50);
}

.notification-item.unread:hover {
  background: var(--main-25);
}

.notification-dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 50%;
  background: var(--gray-300);
}

.notification-dot.severity-info {
  background: var(--blue-400);
}

.notification-dot.severity-warning {
  background: var(--orange-400);
}

.notification-dot.severity-error {
  background: var(--red-500);
}

.notification-body {
  flex: 1;
  min-width: 0;
}

.notification-item-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--gray-1000);
  line-height: 1.4;
}

.notification-item-text {
  margin-top: 2px;
  font-size: 12px;
  color: var(--gray-600);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.notification-item-meta {
  display: flex;
  gap: 8px;
  margin-top: 4px;
  font-size: 11px;
  color: var(--gray-400);
}

.notification-source {
  padding: 0 4px;
  border-radius: 3px;
  background: var(--gray-100);
}

.notification-dismiss {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--gray-400);
  cursor: pointer;
  opacity: 0;
  transition: all 0.15s;
}

.notification-item:hover .notification-dismiss {
  opacity: 1;
}

.notification-dismiss:hover {
  background: var(--gray-100);
  color: var(--gray-700);
}
</style>
