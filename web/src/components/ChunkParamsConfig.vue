<template>
  <div class="chunk-params-config">
    <div class="params-info">
      <p>调整分块参数可以控制文本的切分方式，影响检索质量和文档加载效率。</p>
    </div>
    <a-form :model="localParams" name="chunkConfig" autocomplete="off" layout="vertical">
      <a-form-item v-if="showIndexMode" label="入库模式" name="index_mode">
        <a-radio-group v-model:value="indexMode" class="index-mode-group">
          <a-radio-button
            v-for="option in indexModeOptions"
            :key="option.value"
            :value="option.value"
            class="index-mode-option"
          >
            {{ option.label }}
          </a-radio-button>
        </a-radio-group>
        <p class="param-description">{{ selectedIndexModeDescription }}</p>
      </a-form-item>

      <div class="graph-only-info" v-else-if="graphOnly">
        <p>为已入库文件补充知识图谱。生成过程会调用模型抽取节点和关系，任务提交后会在后台执行。</p>
      </div>

      <div class="chunk-row" v-if="graphOnly || indexMode !== 'fast'">
        <a-form-item label="最多节点" name="max_graph_nodes">
          <a-input-number
            v-model:value="localParams.max_graph_nodes"
            :min="1"
            :max="1000"
            style="width: 100%"
          />
          <p class="param-description">限制本次新增的知识图谱节点数量</p>
        </a-form-item>
        <a-form-item label="最多关系" name="max_graph_relations">
          <a-input-number
            v-model:value="localParams.max_graph_relations"
            :min="1"
            :max="3000"
            style="width: 100%"
          />
          <p class="param-description">限制本次新增的知识图谱关系数量</p>
        </a-form-item>
      </div>

      <a-form-item v-if="showPreset" name="chunk_preset_id">
        <template #label>
          <span class="chunk-preset-label">
            分块策略
            <a-tooltip :title="presetDescription">
              <QuestionCircleOutlined class="chunk-preset-help-icon" />
            </a-tooltip>
          </span>
        </template>
        <a-select
          v-model:value="localParams.chunk_preset_id"
          :options="presetOptions"
          style="width: 100%"
        />
        <p class="param-description">
          预设策略对齐 RAGFlow：General、QA、Book、Laws。
          <span v-if="allowPresetFollowDefault">留空时沿用知识库默认策略。</span>
        </p>
      </a-form-item>

      <div class="chunk-row" v-if="showChunkSizeOverlap">
        <a-form-item label="Chunk Size" name="chunk_size">
          <a-input-number
            v-model:value="localParams.chunk_size"
            :min="100"
            :max="10000"
            style="width: 100%"
          />
          <p class="param-description">每个文本片段的最大字符数</p>
        </a-form-item>
        <a-form-item label="Chunk Overlap" name="chunk_overlap">
          <a-input-number
            v-model:value="localParams.chunk_overlap"
            :min="0"
            :max="1000"
            style="width: 100%"
          />
          <p class="param-description">相邻文本片段间的重叠字符数</p>
        </a-form-item>
      </div>
      <a-form-item
        v-if="showQaSplit"
        class="qa-separator-item"
        label="分隔符 (Separator)"
        name="qa_separator"
      >
        <a-input
          v-model:value="localParams.qa_separator"
          placeholder="输入分隔符，例如 \n\n\n 或 ---"
          style="width: 100%"
        />
        <p class="param-description">支持 \n、\t 等转义字符。留空则不启用预分割</p>
      </a-form-item>
    </a-form>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { QuestionCircleOutlined } from '@ant-design/icons-vue'
import {
  CHUNK_PRESET_OPTIONS,
  CHUNK_PRESET_LABEL_MAP,
  getChunkPresetDescription
} from '@/utils/chunk_presets'

const props = defineProps({
  tempChunkParams: {
    type: Object,
    required: true
  },
  showQaSplit: {
    type: Boolean,
    default: true
  },
  showChunkSizeOverlap: {
    type: Boolean,
    default: true
  },
  showPreset: {
    type: Boolean,
    default: true
  },
  allowPresetFollowDefault: {
    type: Boolean,
    default: false
  },
  databasePresetId: {
    type: String,
    default: 'general'
  },
  graphOnly: {
    type: Boolean,
    default: false
  }
})

// 使用 computed 包装，直接返回原始对象供表单修改
// 表单修改会直接作用于 tempChunkParams（父组件的ref），实现双向绑定
const localParams = computed(() => props.tempChunkParams)

const indexModeOptions = [
  {
    value: 'fast',
    label: '快速入库',
    description: '速度最快，仅支持向量检索，不生成知识图谱。'
  },
  {
    value: 'standard',
    label: '标准入库',
    description: '使用系统默认图谱抽取策略，兼顾检索和知识图谱。'
  },
  {
    value: 'graph',
    label: '图谱入库',
    description: '构建知识图谱，并限制本次新增的节点和关系数量。'
  }
]

const modeGraphDefaults = {
  standard: {
    max_graph_nodes: 5,
    max_graph_relations: 10
  },
  graph: {
    max_graph_nodes: 300,
    max_graph_relations: 800
  }
}

const applyModeGraphDefaults = (mode) => {
  const defaults = modeGraphDefaults[mode] || modeGraphDefaults.standard
  const otherDefaults = mode === 'graph' ? modeGraphDefaults.standard : modeGraphDefaults.graph
  const nodes = props.tempChunkParams.max_graph_nodes
  const relations = props.tempChunkParams.max_graph_relations

  if (!nodes || nodes === otherDefaults.max_graph_nodes) {
    props.tempChunkParams.max_graph_nodes = defaults.max_graph_nodes
  }
  if (!relations || relations === otherDefaults.max_graph_relations) {
    props.tempChunkParams.max_graph_relations = defaults.max_graph_relations
  }
}

const indexMode = computed({
  get: () => props.tempChunkParams.index_mode || 'standard',
  set: (value) => {
    props.tempChunkParams.index_mode = value
    if (value !== 'fast') {
      applyModeGraphDefaults(value)
    }
  }
})

const selectedIndexModeDescription = computed(() => {
  return (
    indexModeOptions.find((option) => option.value === indexMode.value)?.description ||
    indexModeOptions[1].description
  )
})

const showIndexMode = computed(() => !props.graphOnly)

const presetOptions = computed(() => {
  const options = []
  const defaultPresetLabel = CHUNK_PRESET_LABEL_MAP[props.databasePresetId] || 'General'

  if (props.allowPresetFollowDefault) {
    options.push({
      value: '',
      label: `沿用知识库默认（${defaultPresetLabel}）`
    })
  }

  options.push(...CHUNK_PRESET_OPTIONS.map(({ value, label }) => ({ value, label })))

  return options
})

const effectivePresetId = computed(
  () => props.tempChunkParams.chunk_preset_id || props.databasePresetId || 'general'
)
const presetDescription = computed(() => getChunkPresetDescription(effectivePresetId.value))
</script>

<style scoped>
.chunk-params-config {
  width: 100%;
}

.params-info {
  margin-bottom: 16px;
}

.params-info p {
  margin: 0;
  color: var(--gray-500);
  font-size: 14px;
  line-height: 1.5;
}

.chunk-row {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
}

.chunk-row > .ant-form-item {
  flex: 1;
  margin-bottom: 0;
}

.index-mode-group {
  display: flex;
  width: 100%;
}

.index-mode-option {
  flex: 1;
  text-align: center;
}

.qa-separator-item {
  margin-top: 8px;
  margin-bottom: 0;
}

.param-description {
  font-size: 12px;
  color: var(--gray-400);
  margin: 4px 0 0 0;
  line-height: 1.4;
}

.chunk-preset-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.chunk-preset-help-icon {
  color: var(--gray-500);
  cursor: help;
  font-size: 14px;
}
</style>
