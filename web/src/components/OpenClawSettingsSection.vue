<template>
  <div class="openclaw-settings-section">
    <div class="section-title">OpenClaw 集成</div>
    <p class="section-description">
      配置 OpenClaw Gateway 连接，启用后可接收学习提醒、共享知识，并将知识库暴露为 MCP 服务。
    </p>

    <div class="section">
      <div class="card">
        <span class="label">启用 OpenClaw 集成</span>
        <a-switch
          :checked="configStore.config?.openclaw_enabled"
          @change="handleChange('openclaw_enabled', $event)"
        />
      </div>

      <div class="card" style="flex-direction: column; align-items: stretch">
        <div class="label" style="margin-bottom: 6px">Gateway WebSocket URL</div>
        <a-input
          :value="configStore.config?.openclaw_gateway_url || ''"
          placeholder="ws://your-openclaw-gateway:8080/ws"
          @change="handleChange('openclaw_gateway_url', $event.target.value)"
          allow-clear
        />
        <div class="hint">OpenClaw Gateway 的 WebSocket 连接地址</div>
      </div>

      <div class="card" style="flex-direction: column; align-items: stretch">
        <div class="label" style="margin-bottom: 6px">API Key</div>
        <a-input-password
          :value="configStore.config?.openclaw_api_key || ''"
          placeholder="输入 OpenClaw 认证 API Key"
          @change="handleChange('openclaw_api_key', $event.target.value)"
          allow-clear
        />
        <div class="hint">用于 Gateway 认证的 API Key（可选）</div>
      </div>
    </div>

    <div v-if="configStore.config?.openclaw_enabled" class="section-title" style="margin-top: 16px">
      连接状态
    </div>
    <div v-if="configStore.config?.openclaw_enabled" class="section">
      <div class="card">
        <span class="label">Gateway 状态</span>
        <OpenClawStatusBadge />
      </div>
      <div class="card">
        <a-button
          type="default"
          size="small"
          :loading="testingConnection"
          @click="handleTestConnection"
        >
          测试连接
        </a-button>
        <a-button
          type="default"
          size="small"
          :loading="triggeringReminder"
          @click="handleTriggerReminder"
        >
          手动触发提醒
        </a-button>
      </div>
    </div>

    <div class="section-title" style="margin-top: 16px">知识库 MCP 服务</div>
    <p class="section-description">
      自学通知识库已注册为内置 MCP 服务器
      <code>zixuetong-knowledge-mcp</code>，OpenClaw 可通过 MCP 协议直接查询知识库。
      在「扩展管理 → MCP」页面中启用或配置该服务。
    </p>

    <div class="section-title" style="margin-top: 16px">智能提醒机制</div>
    <p class="section-description">
      学习提醒由 OpenClaw 智能体根据用户学习内容难度和进度动态决定。
      不同主题有不同的提醒节奏——例如背单词可能每天提醒，而高难度数学可能需要数天消化。
      用户也可以在对话中告诉学习助手"在 xxx 时间提醒我学习"。
    </p>
    <p class="section-description">
      微信推送通过 OpenClaw ClawBot 插件实现。若推送失败，系统会自动发送站内通知告知管理员。
    </p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { useConfigStore } from '@/stores/config'
import { testOpenClawConnection, triggerReminder } from '@/apis/openclaw_api'
import OpenClawStatusBadge from '@/components/OpenClawStatusBadge.vue'

const configStore = useConfigStore()
const testingConnection = ref(false)
const triggeringReminder = ref(false)

const handleChange = (key, e) => {
  configStore.setConfigValue(key, e)
}

const handleTestConnection = async () => {
  testingConnection.value = true
  try {
    const res = await testOpenClawConnection()
    if (res.success) {
      message.success('连接测试成功')
    } else {
      message.error(res.data?.error || '连接测试失败')
    }
  } catch (e) {
    message.error(e.message || '连接测试失败')
  } finally {
    testingConnection.value = false
  }
}

const handleTriggerReminder = async () => {
  triggeringReminder.value = true
  try {
    await triggerReminder()
    message.success('学习提醒已触发')
  } catch (e) {
    message.error(e.message || '触发提醒失败')
  } finally {
    triggeringReminder.value = false
  }
}
</script>

<style lang="less" scoped>
.openclaw-settings-section {
  .section {
    background-color: var(--gray-0);
    padding: 10px 16px;
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    border: 1px solid var(--gray-150);
  }

  .card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;

    .label {
      margin-right: 20px;
      font-weight: 500;
      color: var(--gray-800);
      flex-shrink: 0;
      min-width: 140px;
    }
  }

  .hint {
    margin-top: 4px;
    font-size: 12px;
    color: var(--gray-400);
    line-height: 1.4;
  }

  code {
    padding: 1px 6px;
    border-radius: 4px;
    background: var(--gray-100);
    font-size: 12px;
    color: var(--gray-700);
  }
}
</style>
