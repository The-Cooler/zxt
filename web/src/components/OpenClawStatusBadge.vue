<template>
  <a-tooltip :title="tooltipText">
    <span class="openclaw-status" :class="statusClass" @click="handleClick">
      <span class="status-dot" />
      <span class="status-label">OpenClaw</span>
    </span>
  </a-tooltip>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getOpenClawStatus } from '@/apis/openclaw_api'

const enabled = ref(false)
const connected = ref(false)
const loaded = ref(false)

onMounted(async () => {
  try {
    const res = await getOpenClawStatus()
    enabled.value = res.data?.enabled || false
    connected.value = res.data?.connected || false
    loaded.value = true
  } catch {
    loaded.value = true
  }
})

const statusClass = computed(() => {
  if (!enabled.value) return 'disabled'
  if (connected.value) return 'connected'
  return 'disconnected'
})

const tooltipText = computed(() => {
  if (!enabled.value) return 'OpenClaw 未启用'
  if (connected.value) return 'OpenClaw 已连接'
  return 'OpenClaw 连接断开'
})

function handleClick() {
  // 点击可跳转到扩展页面查看详情
}
</script>

<style scoped>
.openclaw-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  cursor: default;
  transition: background 0.2s;
}

.openclaw-status.disabled {
  color: var(--gray-400);
}

.openclaw-status.disconnected {
  color: var(--orange-500);
  background: var(--orange-50);
}

.openclaw-status.connected {
  color: var(--green-600);
  background: var(--green-50);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.openclaw-status.connected .status-dot {
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.status-label {
  font-weight: 500;
}
</style>
