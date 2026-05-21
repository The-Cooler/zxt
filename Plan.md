# 使用 Scrapling 重构网页读取与子页面选择流程

## Summary

将现有“单 URL 抓取 HTML -> 当普通文件入库”的流程升级为“网页读取会话”：

- 使用 `scrapling` 替换当前 `httpx` 单页抓取工具，负责抓取页面、抽取正文、标题、主题、页面内同域 HTML 链接。
- 新增 URL 探索会话：初始页面先抓取并展示，用户逐层选择要继续探索/添加的跳转子页面。
- 后端维护发现字典：`{url: { base_url, similarity, topic, title, status, depth, selected }}`。
- 相似度使用知识库当前 embedding 模型计算“初始页正文摘要/正文”与“候选页正文摘要/正文”的余弦相似度。
- 最终入库仍复用现有 MinIO HTML/Markdown/LightRAG 流程，避免改动知识图谱构建主链路。

参考事实：Scrapling 当前 PyPI 最新为 `0.4.8`，发布于 2026-05-11，支持 Python 3.10+；Yuxi 后端 Python 版本为 `>=3.12,<3.14`，兼容。

## Key Changes

### 后端网页读取结构

新增 `backend/package/yuxi/knowledge/web_reader/` 模块：

- `models.py`
  - 定义 `WebPageSnapshot`：`url, final_url, title, topic, text, html, content_hash, links, depth, parent_url`。
  - 定义 `DiscoveredLink`：`url, base_url, similarity, topic, title, depth, status, selected`。
  - 定义 `WebReadSession`：`session_id, db_id, root_url, max_depth, root_snapshot, discovered_map, selected_urls, created_by`。
- `scrapling_reader.py`
  - 使用 `scrapling.fetchers.AsyncFetcher` 优先抓取页面。
  - 只接受 `text/html` / `application/xhtml+xml`。
  - 继续沿用现有 URL 安全规则：`YUXI_URL_WHITELIST`、`http/https`、禁止内网/localhost/link-local、最大 10MB、最多 5 次重定向。
  - 从页面中抽取标题、正文文本、原始 HTML、同域名 `<a href>` 链接；链接统一规范化、去 fragment、去重。
- `similarity.py`
  - 从当前知识库 `embed_info.model_id` 选择 embedding 模型。
  - 对 `root_text` 与候选页 `text` 做 embedding，计算 cosine similarity。
  - 文本过长时只取前 `12000` 字符；空正文返回 `0.0`。
- `session_store.py`
  - v1 使用 Redis 存储会话，key：`yuxi:web-read-session:{session_id}`，TTL 默认 24 小时。
  - 如果 Redis 不可用，返回明确错误，不落本地文件。

### 后端 API

在 `backend/server/routers/knowledge_router.py` 增加网页读取接口，保留现有 `/files/fetch-url` 兼容旧流程。

- `POST /api/knowledge/web-reader/sessions`
  - 入参：`{ url, db_id, max_depth?: number | null }`
  - 行为：抓取初始页，发现同域 HTML 链接，计算第一层候选与初始页相似度，创建 session。
  - 返回：`{ session_id, root_page, discovered_map }`
- `POST /api/knowledge/web-reader/sessions/{session_id}/expand`
  - 入参：`{ urls: string[] }`
  - 行为：只允许展开已发现且未超过 `max_depth` 的 URL；抓取这些页面，发现下一层同域 HTML 链接，加入 discovered_map；已存在 URL 不覆盖原始 `base_url`，但可追加 `parents`。
  - 返回：更新后的 `{ discovered_map }`
- `PUT /api/knowledge/web-reader/sessions/{session_id}/selection`
  - 入参：`{ selected_urls: string[] }`
  - 行为：标记用户准备入库的页面。
- `POST /api/knowledge/web-reader/sessions/{session_id}/commit`
  - 入参：`{ auto_index, parent_id?, chunk_params? }`
  - 行为：将 root 页面和 selected 子页面上传为 HTML 到 MinIO，构造 `_preprocessed_map`，然后复用现有 `add_documents` 的文件模式任务。
  - 返回：现有知识库任务格式 `{ status, task_id, message }`。

### 前端交互

改造 `web/src/components/FileUploadModal.vue` 的 URL 模式：

- “加载 URLs”改为“读取网页”。
- 每个初始 URL 创建一个读取会话卡片。
- 会话卡片展示：
  - 初始页面：URL、标题、主题、正文摘要、抓取状态。
  - 已发现链接表格：URL、来源页面 `base_url`、相似度、主题、深度、状态、是否选择入库。
  - 操作：`展开选中链接`、`添加选中页面到知识库`。
- 相似度显示为百分比，默认按相似度降序；低于 `0.35` 用弱提示，高于 `0.7` 用高相关提示。
- `max_depth` 为可选输入；为空表示不限制深度，但每次只展开用户当前选择的链接，不自动递归全站。
- 最终提交时只提交 root 页面 + 用户选中的子页面；未选中的已发现页面不入库。

新增或调整 `web/src/apis/knowledge_api.js`：

- `createWebReadSession(url, dbId, maxDepth)`
- `expandWebReadSession(sessionId, urls)`
- `updateWebReadSelection(sessionId, selectedUrls)`
- `commitWebReadSession(sessionId, payload)`

## Data Flow

1. 用户输入初始 URL，设置可选 `max_depth`。
2. 前端调用 `createWebReadSession`。
3. 后端用 Scrapling 抓初始页面，抽正文、主题、链接。
4. 后端抓取第一层同域 HTML 候选页，计算与初始页相似度，写入 discovered_map。
5. 前端展示候选链接，用户选择要展开或入库的链接。
6. 用户点击展开时，后端只抓取用户选择的链接，并把新发现链接合并进字典。
7. 用户点击添加到知识库时，后端把 root + selected 页面上传 MinIO，并复用现有文档处理任务。
8. 自动入库开启时，后续仍走 `Parser.aparse -> Markdown -> LightRAG.ainsert -> Neo4j/Milvus`。

## Implementation Notes

- 依赖添加到 `backend/package/pyproject.toml`：`scrapling>=0.4.8`。
- 保留现有 `url_fetcher.py`，但新流程不再直接使用它；可抽出公共安全校验函数，避免两套 URL 校验漂移。
- HTML 转 Markdown 仍由现有 `Parser.aparse` 处理；Scrapling 的正文抽取主要用于摘要、主题、相似度和链接发现，不直接替代入库内容。
- 主题生成 v1 不调用 LLM，规则为：优先 `<title>`，其次第一个 `h1`，再其次正文前 60 字；后续可扩展为 LLM 主题总结。
- 发现字典结构采用对象而不是数组，便于去重和增量更新：

```json
{
  "https://example.com/a": {
    "url": "https://example.com/a",
    "base_url": "https://example.com",
    "parents": ["https://example.com"],
    "similarity": 0.82,
    "topic": "页面主题",
    "title": "页面标题",
    "depth": 1,
    "status": "ready",
    "selected": false
  }
}
```

## Test Plan

- 后端 unit tests：
  - URL 白名单、协议、私有 IP、重定向、非 HTML Content-Type 拒绝。
  - 同域链接抽取、相对链接规范化、fragment 去重。
  - `max_depth = null` 时允许继续手动展开；设置数值时超过深度拒绝展开。
  - discovered_map 已存在 URL 时不重复抓取，保留首个 `base_url` 并追加 `parents`。
  - embedding 相似度空文本返回 `0.0`，正常文本返回 `0~1`。
- 后端 API tests：
  - 创建 session 返回 root_page 和 discovered_map。
  - expand 只接受已发现 URL。
  - selection 只允许选择 root 或 discovered_map 中的 URL。
  - commit 生成 MinIO HTML 和 `_preprocessed_map`，并提交 `knowledge_ingest` 任务。
- 前端验证：
  - URL 模式可创建会话、展示候选链接、显示相似度/主题。
  - 选择链接后可展开下一层。
  - 提交后任务中心出现知识库处理任务。
  - 自动入库开启时，LightRAG 知识库最终能在图谱页看到新实体/关系。

## Assumptions

- 子页面发现规则按用户确认：只发现同域名链接，只接受 HTML 页面。
- `max_depth` 可选；不设置时不自动无限爬取，只允许用户逐次选择当前已发现链接继续展开。
- 相似度默认复用当前知识库 embedding 模型。
- 入库内容使用原始 HTML 文件，继续由现有 Parser 转 Markdown，保证现有知识图谱流程稳定。
