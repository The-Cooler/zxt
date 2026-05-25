<template>
  <div class="database-empty" v-if="!state.showPage">
    <a-empty>
      <template #description>
        <span> 点击右上角用户头像中的"系统设置"来启用知识图谱。 </span>
      </template>
    </a-empty>
  </div>
  <div class="graph-container layout-container" v-else>
    <PageHeader
      title="知识库"
      :active-key="knowledgeActiveView"
      :tabs="knowledgeViewItems"
      aria-label="知识库视图切换"
      :show-border="true"
    >
      <template #actions>
        <div class="db-selector">
          <div class="status-wrapper">
            <div class="status-indicator" :class="graphStatusClass"></div>
            <span class="status-text">{{ graphStatusText }}</span>
          </div>
          <span class="label">知识库: </span>
          <a-select
            v-model:value="state.selectedDbId"
            style="width: 200px"
            :options="state.dbOptions"
            @change="handleDbChange"
            :loading="state.loadingDatabases"
            mode="combobox"
            placeholder="选择或输入KB ID"
          />
        </div>
      </template>
    </PageHeader>

    <div class="graph-shoulder">
      <div class="graph-shoulder-left">
        <a-input
          v-model:value="state.searchInput"
          placeholder="输入要查询的实体 (*为全部)"
          style="width: 300px"
          @keydown.enter="onSearch"
          allow-clear
        >
          <template #suffix>
            <component
              :is="state.searchLoading ? LoadingOutlined : SearchOutlined"
              @click="onSearch"
            />
          </template>
        </a-input>
        <a-input
          v-model:value="sampleNodeCount"
          placeholder="查询数量"
          style="width: 100px"
          @keydown.enter="loadSampleNodes"
          :loading="graph.fetching"
        >
          <template #suffix>
            <component
              :is="graph.fetching ? LoadingOutlined : ReloadOutlined"
              @click="loadSampleNodes"
            />
          </template>
        </a-input>
      </div>
      <div class="graph-shoulder-right">
        <a-button v-if="isNeo4j" type="primary" @click="state.showModal = true">
          <BranchesOutlined /> 构建全局关系
        </a-button>
        <a-button v-else type="primary" @click="state.showUploadTipModal = true">
          <DatabaseOutlined /> 前往知识库详情
        </a-button>
        <a-button
          v-if="unindexedCount > 0"
          type="primary"
          @click="indexNodes"
          :loading="state.indexing"
        >
          <SyncOutlined v-if="!state.indexing" /> 为{{ unindexedCount }}个节点添加索引
        </a-button>
      </div>
    </div>

    <div class="container-outter">
      <GraphCanvas
        ref="graphRef"
        :graph-data="graph.graphData"
        :graph-info="formattedGraphInfo"
        :highlight-keywords="[state.searchInput]"
        @node-click="graph.handleNodeClick"
        @edge-click="graph.handleEdgeClick"
        @canvas-click="graph.handleCanvasClick"
        class="graph-canvas"
      >
        <template #content>
          <a-empty v-show="graph.graphData.nodes.length === 0" style="padding: 4rem 0" />
        </template>
      </GraphCanvas>
      <!-- 详情浮动卡片 -->
      <GraphDetailPanel
        :visible="graph.showDetailDrawer"
        :item="graph.selectedItem"
        :type="graph.selectedItemType"
        :nodes="graph.graphData.nodes"
        @close="graph.handleCanvasClick"
        style="width: 380px"
      />
    </div>

    <a-modal
      :open="state.showModal"
      title="构建全局关系"
      @ok="handleGraphFileConfirm"
      @cancel="handleModalCancel"
      :ok-text="graphUploadConfirmText"
      cancel-text="取消"
      :confirm-loading="state.processing || state.extracting"
      :ok-button-props="{ disabled: !canConfirmGraphUpload }"
      width="760px"
    >
      <div class="upload">
        <div class="note">
          <p>从普通文件中识别系统级实体关系，确认前可以手动调整。这里写入的是全局 Neo4j 图谱，不会修改单个知识库内的 LightRAG 图谱。</p>
        </div>
        <div class="upload-config">
          <div class="config-row">
            <label class="config-label">嵌入模型</label>
            <div class="config-field">
              <EmbeddingModelSelector
                v-model:value="state.embedModelName"
                :disabled="!embedModelConfigurable"
                :style="{ width: '100%' }"
              />
            </div>
          </div>
          <div v-if="!embedModelConfigurable" class="config-hint-row">
            * 图数据库已有数据或已设定模型，不可更改
          </div>
          <div class="config-row">
            <label class="config-label">批处理大小</label>
            <div class="config-field">
              <a-input-number
                v-model:value="state.batchSize"
                :min="1"
                :max="1000"
                style="width: 100%"
              />
            </div>
          </div>
          <div class="config-hint-row">默认值: 40，范围: 1-1000</div>
          <div class="config-row">
            <label class="config-label">识别上限</label>
            <div class="config-field">
              <a-input-number
                v-model:value="state.maxTriples"
                :min="1"
                :max="500"
                style="width: 100%"
              />
            </div>
          </div>
          <div class="config-hint-row">仅普通文件识别时生效，默认最多 200 条</div>
        </div>
        <a-upload-dragger
          class="upload-dragger"
          v-model:fileList="fileList"
          name="file"
          :fileList="fileList"
          :max-count="1"
          accept=".txt,.md,.docx,.html,.htm,.json,.csv,.xls,.xlsx,.pdf,.pptx,.jpg,.jpeg,.png,.bmp,.tiff,.tif"
          action="/api/knowledge/files/upload"
          :headers="getAuthHeaders()"
          @change="handleFileUpload"
          @drop="handleDrop"
        >
          <p class="ant-upload-text">选择用于识别全局关系的文件</p>
          <p class="ant-upload-hint">支持文本、Markdown、Office、PDF、图片等文件；知识库文档入库请前往文档知识库。</p>
        </a-upload-dragger>
        <a-alert
          v-if="state.extractionWarning"
          type="warning"
          show-icon
          :message="state.extractionWarning"
          class="extract-alert"
        />
        <div v-if="tripleDraft.length > 0" class="triple-editor">
          <div class="triple-editor-header">
            <div>
              <div class="triple-editor-title">识别结果</div>
              <div class="triple-editor-subtitle">共 {{ validTripleCount }} 条有效关系，可在写入前调整</div>
            </div>
            <a-button @click="addTripleRow">
              <PlusOutlined /> 新增关系
            </a-button>
          </div>
          <a-table
            :columns="tripleColumns"
            :data-source="tripleDraft"
            :pagination="{ pageSize: 8, size: 'small' }"
            row-key="key"
            size="small"
          >
            <template #bodyCell="{ column, record, index }">
              <template v-if="column.dataIndex === 'h'">
                <a-input v-model:value="record.h" placeholder="头实体" />
              </template>
              <template v-else-if="column.dataIndex === 'r'">
                <a-input v-model:value="record.r" placeholder="关系" />
              </template>
              <template v-else-if="column.dataIndex === 't'">
                <a-input v-model:value="record.t" placeholder="尾实体" />
              </template>
              <template v-else-if="column.key === 'action'">
                <a-button
                  type="text"
                  danger
                  aria-label="删除关系"
                  @click="deleteTripleRow(record.key)"
                >
                  <DeleteOutlined />
                </a-button>
              </template>
            </template>
          </a-table>
        </div>
      </div>
    </a-modal>

    <!-- 知识库图谱说明弹窗 -->
    <a-modal
      :open="state.showUploadTipModal"
      title="知识库图谱说明"
      @cancel="() => (state.showUploadTipModal = false)"
      :footer="null"
      width="500px"
    >
      <div class="upload-tip-content">
        <a-alert
          :message="getUploadTipMessage()"
          type="info"
          show-icon
          style="margin-bottom: 16px"
        />
        <div v-if="!isNeo4j" class="upload-tip-actions">
          <p>当前选中的是单个知识库图谱。它由知识库文档入库自动构建，如需上传文档或重新入库，请前往对应的知识库详情页面。</p>
          <div class="action-buttons">
            <a-button type="primary" @click="goToDatabasePage">
              <DatabaseOutlined /> 前往知识库详情页
            </a-button>
          </div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { useConfigStore } from '@/stores/config'
import {
  SyncOutlined,
  SearchOutlined,
  ReloadOutlined,
  LoadingOutlined,
  DatabaseOutlined,
  PlusOutlined,
  DeleteOutlined,
  BranchesOutlined
} from '@ant-design/icons-vue'
import PageHeader from '@/components/shared/PageHeader.vue'
import { neo4jApi, unifiedApi } from '@/apis/graph_api'
import { useUserStore } from '@/stores/user'
import GraphCanvas from '@/components/GraphCanvas.vue'
import GraphDetailPanel from '@/components/GraphDetailPanel.vue'
import EmbeddingModelSelector from '@/components/EmbeddingModelSelector.vue'
import { useGraph } from '@/composables/useGraph'

const configStore = useConfigStore()
const cur_embed_model = computed(() => configStore.config?.embed_model)
const knowledgeActiveView = 'graph'
const knowledgeViewItems = [
  { key: 'documents', label: '文档知识库', path: '/database' },
  { key: 'graph', label: '知识图谱', path: '/graph' }
]
const modelMatched = computed(
  () =>
    !graphInfo?.value?.embed_model_name ||
    graphInfo.value.embed_model_name === cur_embed_model.value
)

const router = useRouter()
const graphRef = ref(null)
const graphInfo = ref(null)
const fileList = ref([])
const sampleNodeCount = ref(100)
const tripleDraft = ref([])

const graph = reactive(useGraph(graphRef))

const state = reactive({
  loadingGraphInfo: false,
  loadingDatabases: false,
  searchInput: '',
  searchLoading: false,
  showModal: false,
  showInfoModal: false,
  showUploadTipModal: false,
  processing: false,
  indexing: false,
  extracting: false,
  showPage: true,
  selectedDbId: 'neo4j',
  dbOptions: [],
  lightragStats: null,
  embedModelName: '',
  batchSize: 40,
  maxTriples: 200,
  extractionWarning: ''
})

const isNeo4j = computed(() => {
  return state.selectedDbId === 'neo4j'
})

const embedModelConfigurable = computed(() => {
  return graphInfo.value?.embed_model_configurable ?? true
})

// 检查是否有可用于识别的文件
const hasValidFile = computed(() => {
  return fileList.value.some((file) => file.status === 'done' && file.response?.file_path)
})

const uploadedGraphFile = computed(() => {
  return fileList.value.find((file) => file.status === 'done' && file.response?.file_path)
})

const validTripleCount = computed(() => serializeTripleDraft().length)

const canConfirmGraphUpload = computed(() => {
  if (!hasValidFile.value || !state.embedModelName) return false
  if (tripleDraft.value.length === 0) return true
  return validTripleCount.value > 0
})

const graphUploadConfirmText = computed(() => {
  if (tripleDraft.value.length > 0) return '写入全局图谱'
  return '识别关系'
})

const tripleColumns = [
  { title: '头实体', dataIndex: 'h', key: 'h', width: '30%' },
  { title: '关系', dataIndex: 'r', key: 'r', width: '28%' },
  { title: '尾实体', dataIndex: 't', key: 't', width: '30%' },
  { title: '', key: 'action', width: 64 }
]

// 计算未索引节点数量
const unindexedCount = computed(() => {
  return graphInfo.value?.unindexed_node_count || 0
})

const formattedGraphInfo = computed(() => {
  if (isNeo4j.value) {
    return {
      node_count: graphInfo.value?.entity_count || 0,
      edge_count: graphInfo.value?.relationship_count || 0
    }
  } else {
    return {
      node_count: state.lightragStats?.total_nodes || 0,
      edge_count: state.lightragStats?.total_edges || 0
    }
  }
})

const loadDatabases = async () => {
  state.loadingDatabases = true
  try {
    const res = await unifiedApi.getGraphs()
    if (res.success && res.data) {
      state.dbOptions = res.data.map((db) => ({
        label: `${db.name} (${db.type})`,
        value: db.id,
        type: db.type
      }))

      // If no selection or invalid selection, select first
      if (!state.selectedDbId || !state.dbOptions.find((o) => o.value === state.selectedDbId)) {
        if (state.dbOptions.length > 0) {
          state.selectedDbId = state.dbOptions[0].value
        }
      }
    }
  } catch (error) {
    console.error('Failed to load databases:', error)
  } finally {
    state.loadingDatabases = false
  }
}

const handleDbChange = () => {
  // Clear current data
  graph.clearGraph()
  state.searchInput = ''
  state.lightragStats = null

  if (isNeo4j.value) {
    loadGraphInfo()
  } else {
    // Also load stats for LightRAG or KB
    loadLightRAGStats()
  }
  loadSampleNodes()
}

const loadLightRAGStats = () => {
  unifiedApi
    .getStats(state.selectedDbId)
    .then((res) => {
      if (res.success) {
        state.lightragStats = res.data
      }
    })
    .catch((e) => console.error(e))
}

const loadGraphInfo = () => {
  state.loadingGraphInfo = true
  neo4jApi
    .getInfo()
    .then((data) => {
      console.log(data)
      graphInfo.value = data.data
      if (graphInfo.value?.embed_model_name) {
        state.embedModelName = graphInfo.value.embed_model_name
      } else {
        // Default if not set (though backend usually sends default)
        state.embedModelName = cur_embed_model.value
      }
      state.loadingGraphInfo = false
    })
    .catch((error) => {
      console.error(error)
      message.error(error.message || '加载图数据库信息失败')
      state.loadingGraphInfo = false
    })
}

const handleGraphFileConfirm = () => {
  if (tripleDraft.value.length > 0) {
    importTripleDraft()
    return
  }
  extractGraphTriples()
}

const extractGraphTriples = () => {
  if (!hasValidFile.value) {
    message.error('请先等待文件上传完成')
    return
  }

  const filePath = uploadedGraphFile.value?.response?.file_path
  if (!filePath) {
    message.error('文件路径获取失败，请重新选择文件')
    return
  }

  state.extracting = true
  state.extractionWarning = ''

  neo4jApi
    .extractEntities(filePath, null, state.maxTriples)
    .then((res) => {
      const data = res.data || {}
      tripleDraft.value = (data.triples || []).map((item, index) => toTripleDraftRow(item, index))
      if (data.truncated) {
        state.extractionWarning = '文件内容较长，系统已截取前半部分进行识别。'
      }
      message.success(`已识别 ${tripleDraft.value.length} 条关系`)
    })
    .catch((error) => {
      console.error(error)
      message.error(error.message || '关系识别失败')
    })
    .finally(() => {
      state.extracting = false
    })
}

const importTripleDraft = () => {
  const triples = serializeTripleDraft()
  if (triples.length === 0) {
    message.error('请至少保留一条完整关系')
    return
  }

  state.processing = true

  neo4jApi
    .addTriples(triples, 'neo4j', state.embedModelName, state.batchSize)
    .then((data) => {
      if (data.status === 'success') {
        message.success(data.message)
        state.showModal = false
        resetGraphUploadModal()
        setTimeout(() => {
          loadGraphInfo()
          loadSampleNodes()
        }, 500)
      } else {
        throw new Error(data.message)
      }
    })
    .catch((error) => {
      console.error(error)
      message.error(error.message || '写入全局图谱失败')
    })
    .finally(() => {
      state.processing = false
    })
}

const toTripleDraftRow = (item, index) => {
  const head = typeof item.h === 'object' ? item.h?.name : item.h
  const relation = typeof item.r === 'object' ? item.r?.type : item.r
  const tail = typeof item.t === 'object' ? item.t?.name : item.t
  return {
    key: `${Date.now()}-${index}`,
    h: String(head || ''),
    r: String(relation || ''),
    t: String(tail || '')
  }
}

const serializeTripleDraft = () => {
  return tripleDraft.value
    .map((row) => ({
      h: String(row.h || '').trim(),
      r: String(row.r || '').trim(),
      t: String(row.t || '').trim()
    }))
    .filter((row) => row.h && row.r && row.t)
}

const addTripleRow = () => {
  tripleDraft.value.push({
    key: `${Date.now()}-${tripleDraft.value.length}`,
    h: '',
    r: '',
    t: ''
  })
}

const deleteTripleRow = (rowKey) => {
  tripleDraft.value = tripleDraft.value.filter((row) => row.key !== rowKey)
}

const loadSampleNodes = () => {
  graph.fetching = true

  unifiedApi
    .getSubgraph({
      db_id: state.selectedDbId,
      node_label: '*',
      max_nodes: sampleNodeCount.value
    })
    .then((data) => {
      // Normalize data structure if needed
      const result = data.data
      graph.updateGraphData(result.nodes, result.edges)
      console.log(graph.graphData)
    })
    .catch((error) => {
      console.error(error)
      message.error(error.message || '加载节点失败')
    })
    .finally(() => (graph.fetching = false))
}

const onSearch = () => {
  if (state.searchLoading) {
    message.error('请稍后再试')
    return
  }

  if (isNeo4j.value && graphInfo?.value?.embed_model_name !== cur_embed_model.value) {
    // 可选：提示模型不一致
  }

  state.searchLoading = true

  unifiedApi
    .getSubgraph({
      db_id: state.selectedDbId,
      node_label: state.searchInput || '*',
      max_nodes: sampleNodeCount.value
    })
    .then((data) => {
      const result = data.data
      if (!result || !result.nodes || !result.edges) {
        throw new Error('返回数据格式不正确')
      }
      graph.updateGraphData(result.nodes, result.edges)
      if (graph.graphData.nodes.length === 0) {
        message.info('未找到相关实体')
      }
      console.log(data)
      console.log(graph.graphData)
    })
    .catch((error) => {
      console.error('查询错误:', error)
      message.error(`查询出错：${error.message || '未知错误'}`)
    })
    .finally(() => (state.searchLoading = false))
}

onMounted(async () => {
  await loadDatabases()
  loadGraphInfo() // Load default (Neo4j) info
  loadSampleNodes()
})

const handleFileUpload = ({ file, fileList: newFileList }) => {
  // 更新文件列表
  fileList.value = newFileList

  if (file.status === 'uploading' || newFileList.length === 0) {
    tripleDraft.value = []
    state.extractionWarning = ''
  }

  // 如果上传失败，显示错误信息
  if (file.status === 'error') {
    message.error(`文件准备失败: ${file.name}`)
  }

  // 如果上传成功，显示成功信息
  if (file.status === 'done' && file.response?.file_path) {
    message.success(`文件已准备: ${file.name}`)
  }

  console.log('File upload status:', file.status, file.name)
  console.log('File list:', fileList.value)
}

const handleDrop = (event) => {
  console.log(event)
  console.log(fileList.value)
}

const handleModalCancel = () => {
  state.showModal = false
  resetGraphUploadModal()
}

const resetGraphUploadModal = () => {
  fileList.value = []
  tripleDraft.value = []
  state.extractionWarning = ''
}

const graphStatusClass = computed(() => {
  if (state.loadingGraphInfo) return 'loading'
  return graphInfo.value?.status === 'open' ? 'open' : 'closed'
})

const graphStatusText = computed(() => {
  if (state.loadingGraphInfo) return '加载中'
  return graphInfo.value?.status === 'open' ? '已连接' : '已关闭'
})

// 为未索引节点添加索引
const indexNodes = () => {
  // 判断 embed_model_name 是否相同
  if (!modelMatched.value) {
    message.error(
      `向量模型不匹配，无法添加索引，当前向量模型为 ${cur_embed_model.value}，图数据库向量模型为 ${graphInfo.value?.embed_model_name}`
    )
    return
  }

  if (state.processing) {
    message.error('后台正在处理，请稍后再试')
    return
  }

  state.indexing = true
  neo4jApi
    .indexEntities('neo4j')
    .then((data) => {
      message.success(data.message || '索引添加成功')
      // 刷新图谱信息
      loadGraphInfo()
    })
    .catch((error) => {
      console.error(error)
      message.error(error.message || '添加索引失败')
    })
    .finally(() => {
      state.indexing = false
    })
}

const getAuthHeaders = () => {
  const userStore = useUserStore()
  return userStore.getAuthHeaders()
}

const getDatabaseName = () => {
  const selectedDb = state.dbOptions.find((db) => db.value === state.selectedDbId)
  return selectedDb ? selectedDb.label : state.selectedDbId
}

const getUploadTipMessage = () => {
  if (isNeo4j.value) {
    return '默认 Neo4j 图谱用于维护跨知识库、系统级实体关系。'
  } else {
    const selectedDb = state.dbOptions.find((db) => db.value === state.selectedDbId)
    const dbType = selectedDb?.type || '未知'
    const dbName = selectedDb?.label || getDatabaseName()
    return `当前选择的是 ${dbType.toUpperCase()} 类型的知识库"${dbName}"，该知识库的图谱由文档入库自动抽取；图谱页只查看和查询，构建请前往知识库详情。`
  }
}

const goToDatabasePage = () => {
  state.showUploadTipModal = false

  // 如果不是 Neo4j，需要找到对应的知识库 ID 并跳转
  if (!isNeo4j.value) {
    const selectedDb = state.dbOptions.find((db) => db.value === state.selectedDbId)
    if (selectedDb && selectedDb.type !== 'neo4j') {
      // 跳转到对应的知识库详情页面
      router.push(`/database/${state.selectedDbId}`)
    } else {
      // 如果找不到对应的数据库，跳转到数据库列表页面
      router.push('/database')
    }
  }
}
</script>

<style lang="less" scoped>
@graph-header-height: 50px;

.graph-container {
  padding: 0;
  background-color: var(--gray-0);

  .header-container {
    height: @graph-header-height;
  }
}

.db-selector {
  display: flex;
  align-items: center;

  .label {
    font-size: 14px;
    margin-right: 8px;
  }
}

.status-wrapper {
  display: flex;
  align-items: center;
  margin-right: 16px;
  font-size: 14px;
  color: var(--color-text-secondary);
}

.status-text {
  margin-left: 8px;
}

.status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;

  &.loading {
    background-color: var(--color-warning-500);
    animation: pulse 1.5s infinite ease-in-out;
  }

  &.open {
    background-color: var(--color-success-500);
  }

  &.closed {
    background-color: var(--color-error-500);
  }
}

@keyframes pulse {
  0% {
    transform: scale(0.8);
    opacity: 0.5;
  }
  50% {
    transform: scale(1.2);
    opacity: 1;
  }
  100% {
    transform: scale(0.8);
    opacity: 0.5;
  }
}

.upload {
  margin-bottom: 20px;

  .upload-dragger {
    margin: 0px;
  }

  .upload-config {
    margin: 24px 0;
    padding: 16px;
    background-color: var(--gray-0);
    border-radius: 4px;

    .config-row {
      display: flex;
      align-items: center;
      margin-bottom: 16px;

      &:last-of-type {
        margin-bottom: 0;
      }

      .config-label {
        width: 100px;
        flex-shrink: 0;
        font-size: 14px;
        color: var(--color-text);
        text-align: right;
        margin-right: 16px;
      }

      .config-field {
        flex: 1;
        min-width: 0;
      }
    }

    .config-hint-row {
      margin-bottom: 16px;
      padding-left: 116px;
      font-size: 12px;
      color: var(--color-text-secondary);
      line-height: 1.5;

      &:last-child {
        margin-bottom: 0;
      }
    }
  }
}

.note {
  color: var(--color-text-secondary);
  line-height: 1.6;

  p {
    margin: 0;
  }
}

.extract-alert {
  margin-top: 16px;
}

.triple-editor {
  margin-top: 16px;
  border: 1px solid var(--gray-100);
  border-radius: 8px;
  padding: 12px;
  background: var(--gray-0);
}

.triple-editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}

.triple-editor-title {
  color: var(--color-text);
  font-size: 14px;
  font-weight: 600;
}

.triple-editor-subtitle {
  margin-top: 2px;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.container-outter {
  width: 100%;
  height: calc(100vh - @graph-header-height - 60px);
  overflow: hidden;
  background: var(--gray-10);
  padding: 16px var(--page-padding);

  .graph-canvas {
    border: 1px solid var(--gray-100);
    border-radius: 8px;
    height: 100%;
  }

  .tags {
    display: flex;
    gap: 8px;
  }
}

.graph-shoulder {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px var(--page-padding) 0;

  &-left,
  &-right {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  :deep(.ant-input) {
    padding: 2px 0px;
  }

  button {
    box-shadow: none;
  }
}

.upload-tip-content {
  .upload-tip-actions {
    p {
      margin-bottom: 16px;
      color: var(--color-text-secondary);
    }
  }

  .action-buttons {
    display: flex;
    justify-content: center;
    margin-top: 20px;
  }
}
</style>
