export const isIndexedWithoutGraph = (record, kbType) => {
  const normalizedKbType = String(kbType || '').toLowerCase()
  if (normalizedKbType !== 'lightrag') return false

  const status = record?.status
  if (status !== 'done' && status !== 'indexed') return false

  return record?.processing_params?.index_mode === 'fast'
}
