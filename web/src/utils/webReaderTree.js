const pageTitle = (page) => page?.title || page?.topic || page?.final_url || page?.url || '未命名页面'

const formatSimilarity = (value) => {
  const percent = Math.round((Number(value) || 0) * 100)
  return `${percent}%`
}

export const buildWebReaderTree = ({ rootPage, discoveredMap } = {}) => {
  if (!rootPage?.final_url && !rootPage?.url) return []

  const rootUrl = rootPage.final_url || rootPage.url
  const nodes = new Map()
  const rootNode = {
    title: pageTitle(rootPage),
    key: rootUrl,
    url: rootUrl,
    page: rootPage,
    children: []
  }
  nodes.set(rootUrl, rootNode)

  for (const link of Object.values(discoveredMap || {})) {
    const url = link.url
    if (!url) continue
    // 在标题后添加相似度信息
    const similarityText = link.similarity ? ` (${formatSimilarity(link.similarity)})` : ''
    nodes.set(url, {
      title: `${pageTitle(link)}${similarityText}`,
      key: url,
      url,
      page: link,
      children: []
    })
  }

  for (const link of Object.values(discoveredMap || {})) {
    const url = link.url
    if (!url || !nodes.has(url)) continue
    const node = nodes.get(url)
    const parentUrl = (link.parents || []).find((parent) => nodes.has(parent)) || rootUrl
    const parentNode = nodes.get(parentUrl) || rootNode
    parentNode.children.push(node)
  }

  const sortNodes = (items) => {
    items.sort((a, b) => {
      const depthA = Number(a.page?.depth ?? 0)
      const depthB = Number(b.page?.depth ?? 0)
      if (depthA !== depthB) return depthA - depthB
      return String(a.title).localeCompare(String(b.title))
    })
    for (const item of items) {
      sortNodes(item.children)
    }
  }
  sortNodes(rootNode.children)

  return [rootNode]
}
