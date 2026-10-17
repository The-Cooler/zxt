<template>
  <div class="chunk-params-config">
    <div class="params-info" v-if="!graphOnly">
      <p>调整分块参数可以控制文本的切分方式，影响检索质量和文档加载效率。</p>
    </div>
    <a-form :model="localParams" name="chunkConfig" autocomplete="off" layout="vertical">
      <div class="graph-only-info" v-if="graphOnly">
        <p>为已入库文件补充知识图谱。系统会读取该文件已经入库的全部分块，逐块调用模型抽取实体和关系，任务提交后会在后台执行。</p>
        <p>生成图谱不会重新分块，也不会重新写入向量；失败时文档仍可正常检索。</p>
      </div>

      <template v-else>

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
      </template>
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
