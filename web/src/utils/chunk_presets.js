export const CHUNK_PRESET_OPTIONS = [
  {
    value: 'general',
    label: 'General',
    description: '通用：适合大多数文档'
  },
  {
    value: 'qa',
    label: 'QA',
    description: '问答：适合FAQ题库'
  },
  {
    value: 'book',
    label: 'Book',
    description: '书籍：适合教材手册'
  },
  {
    value: 'laws',
    label: 'Laws',
    description: '法规：适合法律规范'
  },
  {
    value: 'semantic',
    label: 'Semantic',
    description: '语义：智能语义切分'
  },
  {
    value: 'separator',
    label: 'Separator',
    description: '分隔：按分隔符切分'
  }
]

export const CHUNK_PRESET_LABEL_MAP = Object.fromEntries(
  CHUNK_PRESET_OPTIONS.map((item) => [item.value, item.label])
)

export const CHUNK_PRESET_DESCRIPTION_MAP = Object.fromEntries(
  CHUNK_PRESET_OPTIONS.map((item) => [item.value, item.description])
)

export const getChunkPresetDescription = (presetId) =>
  CHUNK_PRESET_DESCRIPTION_MAP[presetId] || CHUNK_PRESET_DESCRIPTION_MAP.general
