<template>
  <div class="clawbot-settings-section">
    <div class="section-title">ClawBot 微信互通</div>
    <p class="section-description">启用后，通过微信 iLink Bot 扫码连接。微信中的文字消息会交给当前学习助手处理，并把回复发回原会话。</p>

    <div class="section">
      <div class="card">
        <span class="label">启用微信互通</span>
        <a-switch :checked="configStore.config?.clawbot_enabled" @change="handleEnabledChange" />
      </div>
      <div v-if="configStore.config?.clawbot_enabled" class="card status-card">
        <span class="label">连接状态</span>
        <span :class="['status', status.connected ? 'connected' : 'disconnected']">{{ statusText }}</span>
      </div>
      <div v-if="configStore.config?.clawbot_enabled" class="card login-card">
        <a-button type="primary" :loading="connectLoading" @click="startConnect">{{ status.connected ? '重新连接微信' : '微信扫码连接' }}</a-button>
        <div v-if="qrContent" class="qr-content">
          <img v-if="qrImageSrc" :src="qrImageSrc" alt="ClawBot 微信连接二维码" />
          <a v-else :href="qrContent" target="_blank" rel="noopener noreferrer">{{ qrContent }}</a>
        </div>
        <span v-else class="hint">首次启用后会自动申请二维码；也可手动重新获取。</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import QRCode from 'qrcode'
import { useConfigStore } from '@/stores/config'
import { getClawBotStatus, requestClawBotLogin } from '@/apis/clawbot_api'

const configStore = useConfigStore()
const connectLoading = ref(false)
const qrContent = ref('')
const qrImageSrc = ref('')
const status = ref({ enabled: false, connected: false, awaiting_scan: false })

// 微信返回的 qrcode_img_content 是二维码内容（非微信环境不可直接渲染），
// 与 openclaw 官方实现一致：优先按图片处理，否则用该内容本地生成二维码。
const renderQrCode = async (content) => {
  if (!content) {
    qrImageSrc.value = ''
    return
  }
  if (content.startsWith('data:image/')) {
    qrImageSrc.value = content
    return
  }
  if (content.startsWith('<svg')) {
    qrImageSrc.value = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(content)}`
    return
  }
  try {
    qrImageSrc.value = await QRCode.toDataURL(content, { margin: 1, width: 220 })
  } catch (error) {
    console.error('二维码生成失败:', error)
    qrImageSrc.value = ''
  }
}

watch(qrContent, (value) => {
  void renderQrCode(value)
})
const statusText = computed(() => {
  if (status.value.connected) return '已连接'
  if (status.value.awaiting_scan) return '等待扫码'
  return '未连接'
})

const refreshStatus = async () => {
  try {
    const response = await getClawBotStatus()
    status.value = response.data || status.value
  } catch (error) {
    console.error('读取 ClawBot 状态失败:', error)
  }
}

const handleEnabledChange = async (enabled) => {
  await configStore.setConfigValue('clawbot_enabled', enabled)
  if (enabled) {
    await startConnect()
  } else {
    qrContent.value = ''
    await refreshStatus()
  }
}

const startConnect = async () => {
  try {
    connectLoading.value = true
    const response = await requestClawBotLogin()
    qrContent.value = response.data?.qrcode_content || response.data?.qrcode || ''
    await refreshStatus()
  } catch (error) {
    message.error(error.message || '获取微信连接二维码失败')
  } finally {
    connectLoading.value = false
  }
}

onMounted(refreshStatus)
</script>

<style lang="less" scoped>
.clawbot-settings-section {
  .section {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 10px 16px;
    background-color: var(--gray-0);
    border: 1px solid var(--gray-150);
    border-radius: 8px;
  }

  .card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
  }

  .login-card {
    align-items: flex-start;
    flex-direction: column;
  }

  .label { font-weight: 500; color: var(--gray-900); }
  .hint { color: var(--gray-600); font-size: 13px; }
  .status { font-size: 13px; }
  .connected { color: var(--color-success-600); }
  .disconnected { color: var(--color-warning-600); }
  .qr-content img { width: 220px; height: 220px; object-fit: contain; }
}
</style>
