/** 图谱已生成的文件不再提供「生成图谱」入口 */
const isGraphBuilt = (record) => record?.graph_status === 'built'

/**
 * 判断文件是否只完成了向量入库、尚未生成图谱。
 *
 * 以服务端记录的 graph_status 为准。不能从 processing_params.index_mode 推断：
 * 快速入库沿用文件此前保存的参数快照，重新入库后快照里的 index_mode
 * 可能仍是先前选择的 standard/graph。
 *
 * 入库是否完成同样独立判断：历史失败操作可能把 status 回退成
 * error_indexing，但向量表里仍有可检索的 chunk（vector_chunk_count > 0）。
 */
export const isIndexedWithoutGraph = (record, kbType) => {
  const normalizedKbType = String(kbType || '').toLowerCase()
  if (normalizedKbType !== 'lightrag') return false

  const status = record?.status
  const vectorCount = Number(record?.vector_chunk_count || 0)
  const indexed = status === 'done' || status === 'indexed' || vectorCount > 0
  if (!indexed) return false

  return !isGraphBuilt(record)
}

export { isGraphBuilt }
