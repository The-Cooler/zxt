<template>
  <div class="user-info-component">
    <a-dropdown :trigger="['hover']">
      <div class="user-info-dropdown" :data-align="showRole ? 'left' : 'center'">
        <div class="user-avatar"><BookOpen /></div>
        <div v-if="showRole" class="user-name">学习画像</div>
        <div v-if="slots.actions" class="user-info-actions">
          <slot name="actions" />
        </div>
      </div>
      <template #overlay>
        <a-menu>
          <a-menu-item key="user-profile" @click="openProfile">
            <div class="user-info-display">
              <div class="user-menu-username">用户画像</div>
              <div class="user-menu-details">
                <span class="user-menu-info">学习档案与偏好</span>
                <span class="user-menu-role">{{ userRoleText }}</span>
              </div>
            </div>
          </a-menu-item>
          <a-menu-divider />
          <a-menu-item key="docs" @click="openDocs" :icon="BookOpenIcon">
            <span class="menu-text">文档中心</span>
          </a-menu-item>
          <a-menu-item
            key="theme"
            @click="toggleTheme"
            :icon="themeStore.isDark ? SunIcon : MoonIcon"
          >
            <span class="menu-text">{{
              themeStore.isDark ? '切换到浅色模式' : '切换到深色模式 (Beta)'
            }}</span>
          </a-menu-item>
          <a-menu-divider v-if="userStore.isAdmin" />
          <a-menu-item
            v-if="userStore.isSuperAdmin"
            key="debug"
            @click="showDebug = true"
            :icon="TerminalIcon"
          >
            <span class="menu-text">调试面板（非生产环境）</span>
          </a-menu-item>
          <a-menu-item
            v-if="userStore.isAdmin"
            key="setting"
            @click="goToSetting"
            :icon="SettingsIcon"
          >
            <span class="menu-text">系统设置</span>
          </a-menu-item>
        </a-menu>
      </template>
    </a-dropdown>

    <a-modal v-model:open="profileModalVisible" title="学习用户画像" :footer="null" width="560px">
      <a-form layout="vertical" :model="learningProfile">
        <a-form-item label="学习方向">
          <a-textarea v-model:value="learningProfile.learning_direction" :rows="2" placeholder="例如：准备 Python 数据分析转岗" />
        </a-form-item>
        <a-form-item label="学习偏好">
          <a-textarea v-model:value="learningProfile.learning_preferences" :rows="2" placeholder="例如：偏好案例练习和项目驱动学习" />
        </a-form-item>
        <a-form-item label="已有知识水平">
          <a-textarea v-model:value="learningProfile.knowledge_level" :rows="2" placeholder="例如：掌握 Python 基础语法，尚未系统学习 pandas" />
        </a-form-item>
        <a-form-item label="薄弱点">
          <a-textarea v-model:value="learningProfile.weaknesses" :rows="2" placeholder="例如：统计学基础、复杂 SQL 查询" />
        </a-form-item>
        <a-form-item label="学习历史">
          <a-textarea v-model:value="learningProfile.learning_history" :rows="3" placeholder="记录已完成主题、当前计划和重要学习反馈" />
        </a-form-item>
      </a-form>
      <div class="actions-section">
        <a-space>
          <a-button type="primary" @click="saveProfile" :loading="profileSaving">保存画像</a-button>
          <a-button @click="profileModalVisible = false">关闭</a-button>
        </a-space>
      </div>
    </a-modal>

    <!-- 调试面板 Modal -->
    <DebugComponent v-model:show="showDebug" />
  </div>
</template>

<script setup>
import { computed, h, inject, ref, useSlots } from 'vue'
import { useUserStore } from '@/stores/user'
import { agentApi } from '@/apis/agent_api'
import DebugComponent from '@/components/DebugComponent.vue'
import { message } from 'ant-design-vue'
import { BookOpen, Moon, Settings, Sun, Terminal } from 'lucide-vue-next'
import { useThemeStore } from '@/stores/theme'

const userStore = useUserStore()
const themeStore = useThemeStore()
const slots = useSlots()
const BookOpenIcon = h(BookOpen, { size: '16' })
const SunIcon = h(Sun, { size: '16' })
const MoonIcon = h(Moon, { size: '16' })
const TerminalIcon = h(Terminal, { size: '16' })
const SettingsIcon = h(Settings, { size: '16' })
const showDebug = ref(false)
const profileModalVisible = ref(false)
const profileSaving = ref(false)
const learningProfile = ref({
  learning_direction: '',
  learning_preferences: '',
  knowledge_level: '',
  weaknesses: '',
  learning_history: ''
})
const { openSettingsModal } = inject('settingsModal', {})

defineProps({
  showRole: { type: Boolean, default: false },
  showButton: { type: Boolean, default: false }
})

const userRoleText = computed(() => '学习用户')
const openDocs = () => window.open('/docs/', '_blank', 'noopener,noreferrer')
const toggleTheme = () => themeStore.toggleTheme()
const goToSetting = () => openSettingsModal?.()

const openProfile = async () => {
  profileModalVisible.value = true
  try {
    learningProfile.value = await agentApi.getLearningProfile()
  } catch (error) {
    console.error('读取学习画像失败:', error)
    message.error('读取学习画像失败')
  }
}

const saveProfile = async () => {
  try {
    profileSaving.value = true
    learningProfile.value = await agentApi.updateLearningProfile(learningProfile.value)
    message.success('学习画像已保存')
  } catch (error) {
    console.error('保存学习画像失败:', error)
    message.error('保存学习画像失败')
  } finally {
    profileSaving.value = false
  }
}
</script>

<style lang="less" scoped>
.user-info-component {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--gray-800);
  font-family:
    -apple-system, BlinkMacSystemFont, 'Noto Sans SC', 'Roboto', 'HarmonyOS Sans SC', 'Segoe UI',
    'Helvetica Neue', Arial, sans-serif;
}

.user-info-dropdown {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;

  &[data-align='center'] {
    justify-content: center;
  }

  &[data-align='left'] {
    justify-content: flex-start;
  }
}

.user-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-info-actions {
  display: inline-flex;
  align-items: center;
  margin-left: auto;
}

.user-avatar {
  @avatar-size: 32px;
  width: @avatar-size;
  height: @avatar-size;
  min-width: @avatar-size;
  flex: 0 0 @avatar-size;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 16px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  box-shadow: 0 2px 8px var(--shadow-2);

  &:hover {
    opacity: 0.9;
  }

  .avatar-image {
    width: 100%;
    height: 100%;
    display: block;
    box-sizing: border-box;
    object-fit: cover;
    border-radius: 50%;
    border: 2px solid var(--gray-150);
  }
}

.user-role-badge {
  position: absolute;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  right: 0;
  bottom: 0;
  border: 2px solid var(--gray-0);

  &.superadmin {
    background-color: var(--color-warning-500);
  }

  &.admin {
    background-color: var(--color-info-500); /* 蓝色，管理员 */
  }

  &.user {
    background-color: var(--color-success-500); /* 绿色，普通用户 */
  }
}

.user-info-display {
  line-height: 1.4;
}

.user-menu-username {
  font-weight: 600;
  color: var(--gray-900);
  font-size: 14px;
  display: block;
  margin-bottom: 2px;
}

.user-menu-details {
  display: flex;
  gap: 12px;
  align-items: center;
}

.user-menu-info {
  font-size: 12px;
  color: var(--gray-600);
}

.user-menu-role {
  font-size: 12px;
  color: var(--gray-500);
}

.login-icon {
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 50%;
  transition:
    background-color 0.2s,
    color 0.2s;
  color: var(--gray-900);

  &:hover {
    background-color: var(--main-10);
    color: var(--main-color);
  }
}

.profile-modal {
  :deep(.ant-modal-header) {
    padding: 40px 24px;
    border-bottom: 1px solid var(--gray-150);
  }

  :deep(.ant-modal-body) {
    padding: 24px;
  }
}

.profile-content {
  .avatar-section {
    text-align: center;
    margin-bottom: 32px;
    padding-bottom: 24px;
    border-bottom: 1px solid var(--gray-150);

    .avatar-container {
      display: inline-block;

      .avatar-display {
        margin-bottom: 16px;

        .large-avatar {
          width: 80px;
          height: 80px;
          display: block;
          box-sizing: border-box;
          border-radius: 50%;
          object-fit: cover;
          margin: 0 auto;
          border: 3px solid var(--gray-150);
          box-shadow: 0 2px 8px var(--shadow-2);
        }

        .default-avatar {
          width: 80px;
          height: 80px;
          border-radius: 50%;
          background: var(--gray-50);
          display: flex;
          margin: 0 auto;
          align-items: center;
          justify-content: center;
          border: 3px solid var(--gray-150);
          box-shadow: 0 2px 8px var(--shadow-2);

          // 确保图标居中
          :deep(svg) {
            color: var(--gray-400);
          }
        }
      }

      .avatar-actions {
        .avatar-tips {
          margin-top: 8px;
          font-size: 12px;
          color: var(--gray-500);
          line-height: 1.4;
        }
      }
    }
  }

  .info-section {
    margin-bottom: 24px;

    .info-item {
      display: flex;
      align-items: center;
      padding: 12px;
      border-bottom: 1px solid var(--gray-50);

      &:last-child {
        border-bottom: none;
      }

      .info-label {
        width: 120px;
        font-weight: 500;
        color: var(--gray-600);
        flex-shrink: 0;
      }

      .info-value {
        flex: 1;
        color: var(--gray-900);
        font-size: 14px;

        &.user-id {
          font-family: 'Monaco', 'Consolas', monospace;
          // background: var(--gray-50);
          // padding: 4px 8px;
          border-radius: 4px;
          display: inline-block;
        }
      }
    }
  }

  .actions-section {
    text-align: center;
    padding-top: 16px;
    border-top: 1px solid var(--gray-150);
  }
}

:deep(.ant-dropdown-menu) {
  padding: 8px 0;
}

:deep(.ant-dropdown-menu-title-content) {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--gray-900);
}

:deep(.ant-dropdown-menu-item svg) {
  margin-right: 4px;
  color: var(--gray-900);
  vertical-align: middle;
}

.menu-text {
  line-height: 20px;
}
</style>
