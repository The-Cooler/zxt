<template>
  <a-drawer
    v-model:open="open"
    title="网页选择预览"
    width="92vw"
    class="web-reader-preview-drawer"
    @close="handleClose"
  >
    <div class="web-reader-preview-layout">
      <aside class="web-reader-sidebar" v-show="!sidebarCollapsed">
        <div class="sidebar-head">
          <div>
            <div class="sidebar-title">页面结构</div>
            <div class="sidebar-subtitle">勾选需要清洗并入库的页面</div>
          </div>
          <div class="sidebar-actions">
            <a-tag>{{ selectedUrls.length }} 页</a-tag>
            <a-button size="small" type="text" @click="sidebarCollapsed = true">
              收起
            </a-button>
          </div>
        </div>
        <a-tree
          v-if="treeData.length"
          checkable
          check-strictly
          block-node
          class="web-reader-tree"
          :tree-data="treeData"
          :checked-keys="checkedKeys"
          :selected-keys="activeUrl ? [activeUrl] : []"
          :default-expand-all="false"
          @check="handleCheck"
          @select="handleSelect"
        />
        <a-empty v-else description="暂无网页会话" />
      </aside>
      <div v-if="sidebarCollapsed" class="sidebar-collapsed-bar">
        <a-button size="small" type="text" @click="sidebarCollapsed = false">
          展开侧边栏
        </a-button>
      </div>

      <main class="web-reader-main">
        <div class="preview-toolbar">
          <div class="preview-meta">
            <div class="preview-title">{{ previewData?.title || activeUrl || '选择页面预览' }}</div>
            <div class="preview-url" :title="previewData?.url || activeUrl">
              {{ previewData?.url || activeUrl || '暂无页面' }}
            </div>
          </div>
          <a-button size="small" :loading="previewLoading" @click="loadPreview(activeUrl)">
            刷新预览
          </a-button>
        </div>
        <div class="preview-frame-shell">
          <a-spin v-if="previewLoading" />
          <iframe
            v-else-if="activeUrl"
            class="preview-frame"
            sandbox="allow-scripts allow-same-origin"
            :src="activeUrl"
          />
          <a-empty v-else description="选择左侧页面查看预览" />
        </div>
      </main>

      <aside class="web-reader-config" v-show="!configCollapsed">
        <div class="config-head">
          <span class="config-title">{{ activePanel === 'config' ? '入库参数' : '清洗结果' }}</span>
          <a-button size="small" type="text" @click="configCollapsed = true">
            收起
          </a-button>
        </div>
        <a-tabs v-model:activeKey="activePanel" size="small">
          <a-tab-pane key="config" tab="入库参数">
            <div class="sidebar-subtitle">先设置参数，再生成清洗结果</div>
            <ChunkParamsConfig
              :temp-chunk-params="localIndexParams"
              :show-qa-split="true"
              :show-chunk-size-overlap="!isGraphBased"
              :show-preset="true"
              :allow-preset-follow-default="true"
              :database-preset-id="databasePresetId"
            />
          </a-tab-pane>
          <a-tab-pane key="cleaned" tab="清洗结果">
            <div class="cleaned-panel">
              <div v-if="cleanedPages.length" class="cleaned-list">
                <div
                  v-for="page in cleanedPages"
                  :key="page.source_url"
                  class="cleaned-item"
                  :class="{ active: activeCleanedUrl === page.source_url }"
                  @click="loadCleanedPage(page.source_url)"
                >
                  <div class="cleaned-title" :title="page.title || page.filename">
                    {{ page.title || page.filename }}
                  </div>
                  <div class="cleaned-url" :title="page.source_url">{{ page.source_url }}</div>
                </div>
              </div>
              <a-empty v-else description="生成清洗结果后可在这里查看和编辑" />

              <div v-if="activeCleanedUrl" class="cleaned-editor">
                <div class="cleaned-editor-toolbar">
                  <a-segmented
                    v-model:value="cleanedViewMode"
                    :options="[
                      { label: '预览', value: 'preview' },
                      { label: '编辑', value: 'edit' }
                    ]"
                  />
                  <div class="cleaned-actions">
                    <a-button size="small" :loading="savingCleaned" @click="saveCleanedPage">
                      保存
                    </a-button>
                    <a-popconfirm title="从本次入库中移除该页面？" @confirm="deleteCleanedPage">
                      <a-button size="small" danger :loading="deletingCleaned">删除</a-button>
                    </a-popconfirm>
                  </div>
                </div>
                <a-spin v-if="cleanedLoading" />
                <MarkdownPreview
                  v-else-if="cleanedViewMode === 'preview'"
                  :content="cleanedContent"
                  compact
                  class="cleaned-markdown-preview"
                />
                <a-textarea
                  v-else
                  v-model:value="cleanedContent"
                  :auto-size="{ minRows: 18, maxRows: 28 }"
                  class="cleaned-textarea"
                />
              </div>
            </div>
          </a-tab-pane>
        </a-tabs>
      </aside>
      <div v-if="configCollapsed" class="config-collapsed-bar">
        <a-button size="small" type="text" @click="configCollapsed = false">
          展开配置
        </a-button>
      </div>
    </div>

    <template #footer>
      <div class="drawer-footer">
        <a-button @click="handleClose">取消</a-button>
        <a-button
          :loading="props.commitLoading"
          :disabled="!canCommit"
          @click="handleCommit"
        >
          {{ commitButtonText }}
        </a-button>
        <a-button
          type="primary"
          :loading="cleaning"
          :disabled="!props.sessionItem?.data?.session_id"
          @click="generateCleanedPages"
        >
          生成清洗结果
        </a-button>
      </div>
    </template>
  </a-drawer>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { fileApi } from '@/apis/knowledge_api'
import ChunkParamsConfig from '@/components/ChunkParamsConfig.vue'
import MarkdownPreview from '@/components/common/MarkdownPreview.vue'
import { buildWebReaderTree } from '@/utils/webReaderTree'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  sessionItem: {
    type: Object,
    default: null
  },
  isGraphBased: {
    type: Boolean,
    default: false
  },
  databasePresetId: {
    type: String,
    default: 'general'
  },
  defaultIndexParams: {
    type: Object,
    required: true
  },
  commitLoading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:visible', 'payload', 'commit'])

const open = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value)
})

const localIndexParams = reactive({ ...props.defaultIndexParams })
const checkedKeys = ref([])
const activeUrl = ref('')
const previewData = ref(null)
const previewLoading = ref(false)
const cleaning = ref(false)
const activePanel = ref('config')
const cleanedPages = ref([])
const activeCleanedUrl = ref('')
const cleanedContent = ref('')
const cleanedViewMode = ref('preview')
const cleanedLoading = ref(false)
const savingCleaned = ref(false)
const deletingCleaned = ref(false)
const sidebarCollapsed = ref(false)
const configCollapsed = ref(false)

const treeData = computed(() => {
  return buildWebReaderTree({
    rootPage: props.sessionItem?.data?.root_page,
    discoveredMap: props.sessionItem?.data?.discovered_map || {}
  })
})

const selectedUrls = computed(() =>
  checkedKeys.value.filter((url) => url !== props.sessionItem?.data?.root_page?.final_url)
)
const hasCleanedPages = computed(() => cleanedPages.value.length > 0)
const canCommit = computed(() => Boolean(props.sessionItem?.data?.session_id) && hasCleanedPages.value)
const commitButtonText = computed(() =>
  cleanedViewMode.value === 'edit' && activeCleanedUrl.value ? '保存并入库' : '入库'
)

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return
    Object.assign(localIndexParams, props.defaultIndexParams)
    checkedKeys.value = [...(props.sessionItem?.checkedUrls || [])]
    activeUrl.value = props.sessionItem?.data?.root_page?.final_url || ''
    cleanedPages.value = [...(props.sessionItem?.cleanedPages || [])]
    activeCleanedUrl.value = cleanedPages.value[0]?.source_url || ''
    cleanedContent.value = ''
    activePanel.value = cleanedPages.value.length ? 'cleaned' : 'config'
    previewData.value = null
    if (activeUrl.value) {
      loadPreview(activeUrl.value)
    }
    if (activeCleanedUrl.value) {
      loadCleanedPage(activeCleanedUrl.value)
    }
  }
)

const handleClose = () => {
  open.value = false
}

const handleCheck = (keys) => {
  checkedKeys.value = Array.isArray(keys) ? keys : keys?.checked || []
}

const handleSelect = (keys) => {
  const url = Array.isArray(keys) ? keys[0] : ''
  if (!url) return
  activeUrl.value = url
  loadPreview(url)
}

const loadPreview = async (url) => {
  if (!url || !props.sessionItem?.data?.session_id) return
  previewLoading.value = true
  try {
    previewData.value = await fileApi.previewWebReadPage(props.sessionItem.data.session_id, url)
  } catch (error) {
    console.error('网页预览失败:', error)
    message.error(error.message || '网页预览失败')
  } finally {
    previewLoading.value = false
  }
}

const loadCleanedPage = async (sourceUrl) => {
  if (!sourceUrl || !props.sessionItem?.data?.session_id) return
  activeCleanedUrl.value = sourceUrl
  cleanedLoading.value = true
  try {
    const result = await fileApi.getCleanedWebReadPage(props.sessionItem.data.session_id, sourceUrl)
    cleanedContent.value = result.content || ''
    cleanedViewMode.value = 'preview'
  } catch (error) {
    console.error('读取清洗结果失败:', error)
    message.error(error.message || '读取清洗结果失败')
  } finally {
    cleanedLoading.value = false
  }
}

const buildIndexPayload = () => {
  const payload = {}
  if (localIndexParams.chunk_preset_id) {
    payload.chunk_preset_id = localIndexParams.chunk_preset_id
  }
  payload.index_mode = localIndexParams.index_mode || 'standard'
  if (payload.index_mode !== 'fast') {
    payload.max_graph_nodes = localIndexParams.max_graph_nodes
    payload.max_graph_relations = localIndexParams.max_graph_relations
  }
  if (props.isGraphBased) {
    payload.qa_separator = localIndexParams.qa_separator || ''
    return payload
  }
  return { ...localIndexParams, ...payload }
}

const generateCleanedPages = async () => {
  const payload = {
    session_id: props.sessionItem?.data?.session_id,
    root_url: props.sessionItem?.data?.root_page?.final_url,
    selected_urls: selectedUrls.value,
    index_params: buildIndexPayload(),
    next_step: 'cleaned'
  }
  if (!payload.session_id) return

  cleaning.value = true
  try {
    await fileApi.updateWebReadSelection(payload.session_id, payload.selected_urls)
    const result = await fileApi.cleanWebReadSession(payload.session_id)
    cleanedPages.value = result.cleaned_pages || []
    activeCleanedUrl.value = cleanedPages.value[0]?.source_url || ''
    emit('payload', {
      ...payload,
      action: 'generated',
      cleaned_pages: cleanedPages.value,
      cleaned_count: result.cleaned_count || 0
    })
    message.success(`清洗完成，共生成 ${result.cleaned_count || 0} 个页面文件`)
    activePanel.value = 'cleaned'
    if (activeCleanedUrl.value) {
      await loadCleanedPage(activeCleanedUrl.value)
    }
  } catch (error) {
    console.error('网页清洗失败:', error)
    message.error(error.message || '网页清洗失败')
  } finally {
    cleaning.value = false
  }
}

const emitCleanedState = () => {
  emit('payload', {
    session_id: props.sessionItem?.data?.session_id,
    root_url: props.sessionItem?.data?.root_page?.final_url,
    selected_urls: selectedUrls.value,
    index_params: buildIndexPayload(),
    next_step: 'cleaned',
    action: 'updated',
    cleaned_pages: cleanedPages.value,
    cleaned_count: cleanedPages.value.length
  })
}

const saveCleanedPage = async () => {
  if (!activeCleanedUrl.value || !props.sessionItem?.data?.session_id) return
  savingCleaned.value = true
  try {
    const result = await fileApi.updateCleanedWebReadPage(
      props.sessionItem.data.session_id,
      activeCleanedUrl.value,
      cleanedContent.value
    )
    const updatedPage = result.page
    cleanedPages.value = cleanedPages.value.map((page) =>
      page.source_url === updatedPage.source_url ? updatedPage : page
    )
    emitCleanedState()
    cleanedViewMode.value = 'preview'
    message.success('清洗结果已保存，可点击“入库”提交到知识库')
    return true
  } catch (error) {
    console.error('保存清洗结果失败:', error)
    message.error(error.message || '保存清洗结果失败')
    return false
  } finally {
    savingCleaned.value = false
  }
}

const handleCommit = async () => {
  if (!canCommit.value) {
    message.error('请先生成清洗结果后再入库')
    return
  }

  if (cleanedViewMode.value === 'edit' && activeCleanedUrl.value) {
    const saved = await saveCleanedPage()
    if (!saved) {
      message.error('保存清洗结果失败，未提交入库')
      return
    }
  }

  emit('commit', {
    session_id: props.sessionItem?.data?.session_id,
    root_url: props.sessionItem?.data?.root_page?.final_url,
    selected_urls: selectedUrls.value,
    index_params: buildIndexPayload(),
    cleaned_pages: cleanedPages.value,
    cleaned_count: cleanedPages.value.length
  })
}

const deleteCleanedPage = async () => {
  if (!activeCleanedUrl.value || !props.sessionItem?.data?.session_id) return
  deletingCleaned.value = true
  try {
    const result = await fileApi.deleteCleanedWebReadPage(
      props.sessionItem.data.session_id,
      activeCleanedUrl.value
    )
    cleanedPages.value = result.cleaned_pages || []
    activeCleanedUrl.value = cleanedPages.value[0]?.source_url || ''
    cleanedContent.value = ''
    emitCleanedState()
    if (activeCleanedUrl.value) {
      await loadCleanedPage(activeCleanedUrl.value)
    }
    message.success('已移除该清洗结果')
  } catch (error) {
    console.error('删除清洗结果失败:', error)
    message.error(error.message || '删除清洗结果失败')
  } finally {
    deletingCleaned.value = false
  }
}
</script>

<style scoped>
.web-reader-preview-layout {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 16px;
  min-height: calc(100vh - 180px);
}

.web-reader-sidebar {
  width: 300px;
  min-height: 0;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-10);
  padding: 14px;
  overflow: auto;
}

.sidebar-collapsed-bar,
.config-collapsed-bar {
  display: flex;
  align-items: center;
  padding: 8px;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-10);
}

.web-reader-main {
  min-height: 0;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-10);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.web-reader-config {
  width: 420px;
  min-height: 0;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-10);
  padding: 14px;
  overflow: auto;
}

.sidebar-actions,
.config-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.config-head {
  justify-content: space-between;
  margin-bottom: 12px;
}

.config-title {
  font-size: 14px;
  font-weight: 600;
}

.web-reader-tree {
  max-height: calc(100vh - 280px);
  overflow: auto;

  :deep(.ant-tree-treenode) {
    display: flex;
    align-items: center;
    width: 100%;
    padding: 0;
    height: 32px;

    .ant-tree-switcher {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 20px;
      height: 32px;
      line-height: 32px;
    }

    .ant-tree-indent {
      display: flex;
      align-items: center;
      align-self: stretch;

      &-unit {
        width: 16px;
      }
    }

    .ant-tree-node-content-wrapper {
      display: flex;
      align-items: center;
      flex: 1;
      min-width: 0;
      height: 32px;
      line-height: 32px;
      padding: 0 6px;
      border-radius: 4px;
      transition: background-color 0.2s;

      .ant-tree-title {
        display: flex;
        align-items: center;
        flex: 1;
        min-width: 0;
        height: 100%;
        overflow: hidden;
        font-size: 13px;
        color: var(--gray-800);
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      &:hover {
        background-color: var(--gray-50);
      }

      &.ant-tree-node-selected {
        background-color: var(--main-50);
      }
    }

    .ant-tree-checkbox {
      margin-right: 6px;
    }
  }
}

.sidebar-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.sidebar-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-1000);
}

.sidebar-subtitle {
  margin-top: 4px;
  margin-bottom: 12px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--gray-500);
}

.web-reader-main {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.preview-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--gray-150);
}

.preview-meta {
  min-width: 0;
}

.preview-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--gray-1000);
}

.preview-url {
  overflow: hidden;
  color: var(--gray-500);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-frame-shell {
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: center;
  min-height: 480px;
  background: #fff;
}

.preview-frame {
  width: 100%;
  height: 100%;
  min-height: 480px;
  border: 0;
  background: #fff;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.cleaned-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cleaned-list {
  display: flex;
  max-height: 180px;
  flex-direction: column;
  gap: 8px;
  overflow: auto;
}

.cleaned-item {
  padding: 8px 10px;
  border: 1px solid var(--gray-150);
  border-radius: 6px;
  background: var(--gray-25);
  cursor: pointer;
}

.cleaned-item.active {
  border-color: var(--main-500);
  background: var(--main-50);
}

.cleaned-title {
  overflow: hidden;
  color: var(--gray-1000);
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cleaned-url {
  overflow: hidden;
  margin-top: 3px;
  color: var(--gray-500);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cleaned-editor {
  min-height: 360px;
  padding-top: 8px;
  border-top: 1px solid var(--gray-150);
}

.cleaned-editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.cleaned-actions {
  display: flex;
  gap: 8px;
}

.cleaned-markdown-preview {
  max-height: 520px;
  padding: 10px;
  border: 1px solid var(--gray-150);
  border-radius: 6px;
  overflow: auto;
  background: var(--gray-25);
}

.cleaned-textarea {
  font-family:
    'Menlo', 'Monaco', 'Consolas', 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei',
    monospace;
  font-size: 13px;
  line-height: 1.6;
}
</style>
