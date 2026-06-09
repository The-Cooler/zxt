export const getSuccessfulWebReaderItems = (items = []) => {
  return items.filter((item) => item.status === 'success' && item.data)
}

export const getUncleanedWebReaderItems = (items = []) => {
  return items.filter((item) => !item.cleanedPages?.length)
}

export const findWebReaderItemBySessionId = (items = [], sessionId) => {
  return items.find((item) => item.data?.session_id === sessionId) || null
}

export const buildWebReaderCommitPayload = (item, { autoIndex, parentId } = {}) => {
  return {
    auto_index: Boolean(autoIndex),
    parent_id: parentId || null,
    chunk_params: item?.indexParams || {}
  }
}
