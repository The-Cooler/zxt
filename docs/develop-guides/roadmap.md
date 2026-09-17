# 开发路线图

路线图可能会经常变更，如果有强烈建议，请先在当前项目约定的协作渠道中讨论。

日志添加规范（For Agent）:

- 同一版本的多次功能更新时，应以功能为单位进行更新，比如之前添加了 A 功能的更新，在后续的更新中修复了因 A 功能引入的 bug，那么这个修复说明应该和 A 功能描述放在一起，而不是新增一条修复记录，功能更新同理。


### 看板

- Langfuse 增加 self-host 模式支持，补齐私有化部署与配置说明（已支持 cloud，待调试）
- 检索测试中，添加问答
- 集成 Memory，基于 deepagents 的文件后端实现，需要考虑定位
- 自学通-cli 相关的功能，放在后续版本中实现（不是类似于编程助手，而是管理平台的工，等各个 router 接口优化之后）
- 完善测试基准自动生成功能，目前的实现过于简单，无法覆盖实际需求
- 完善 Skills 的环境变量注入
- 拓宽检索的知识源，统一多知识源（channel），目前已知知识库/知识图谱/网页，可拓展：个人知识库、数据库、历史对话等
    - 前置任务，多知识库并行检索（扩展 query_kb）
    - 新增 query_keywords 工具，专门用于基于关键词命中的排序，也结合词频（和 BM25 的区别？）
- 调研将当前知识库映射为虚拟文件系统工具的可行性，先明确文件树映射、权限边界、内容读取与 Agent 工具调用形态，再决定是否实现
- 参考 AgenticRAG 方案扩展当前 Search 工具：等待虚拟文件系统构建完成后，改进 Search 返回递增文件序列 ID，新增 Find 与 Open 能力；Summary 暂缓
- 评估，基于 Agent 的评估，这里应该是结合 Langfuse 实现

### Bugs
- 目前的知识库的图片存在公开访问风险

### BREAKING CHANGE（不兼容变更，0.7 版本再实现）
- 将自定义provider 的实现逻辑，从文件移动到数据库中，并将相关处理代码，移出 config 文件，放到 provider 模块中
- 已补充方案文档：`docs/vibe/2026-04-18-custom-provider-db-refactor-plan.md`，明确采用“provider 一行、models 放 JSON、移除 provider 默认模型”的落地方案
- 优化知识库的 API 接口设计，使用 /{db_id}/xxx 的形式，整合 mindmap / eval 接口
- 移除 v1 版本的 provider 统一接口，改为 v2 版本的 provider 模块接口



## 版本记录

### 0.6.2 开发记录

<!-- 0.6.2 的内容请放在这里 -->
- 新增学习进度智能提醒：学习计划 Agent 在创建计划时安排该计划的提醒时间，用户可按计划修改或关闭；后台根据任务完成度与下一步任务生成提醒，同时发送站内通知，并在 ClawBot 已连接时主动推送微信消息。
- 收敛单用户数据库模型：移除旧部门表、用户与智能体配置中的 `department_id`、固定“个人配置作用域”以及账号登录/角色/软删除字段，系统 owner 仅保留业务归属所需的实体属性；智能体配置直接按 `agent_id` 管理。
- 移除嵌入模型选择器中的 V1 版本模型，仅保留 V2 版本模型，简化用户选择。
- 优化分块策略选择器：在选择器下拉菜单中为每个策略选项添加说明文字，帮助用户理解不同策略的适用场景。
- 简化网页读取输入：将多行 URL 输入改为单行输入框，一次只读取一个网页，简化用户操作流程。
- 优化网页读取私有地址判断：改进 DNS 解析逻辑，只阻止明确的内网私有地址（10.x/172.16-31.x/192.168.x）和本地回环地址，允许特殊保留地址段（如 VPN/代理使用的 198.18.x.x）；同时在 HTTP 请求时明确禁用代理，避免代理环境导致的误拦截。
- 优化网页读取错误提示：将私有地址访问错误改为中文提示，并给出友好的使用建议。
- 优化网页读取默认信息展示：优先显示页面标题而非主题，当有主题时作为补充信息展示。
- 移除废弃代码：删除过时的 `url_fetcher.py` 文件及其相关 API（`/files/fetch-url`），避免代码混淆和维护负担。
- 优化网页读取发现页面列表样式：修复树形结构节点的显示问题，统一字体大小、行高、对齐方式，规范复选框和节点内容的间距，确保横线分割和文字排版清晰整齐；修复已发现页面列表文字重叠问题，调整为三行布局（标题 13px/URL 12px/来源 11px），行高 1.4，间距清晰。
- 修复知识库文档详情加载卡死：为 `get_file_content` 添加 LightRAG 实例获取和 MinIO Markdown 读取的超时保护（30 秒/10 秒），避免因 LightRAG 表不存在或 MinIO 连接问题导致请求永久挂起。
- 新增 AI 动画演示 MVP：后端提供 `zixuetong.animation` 独立模块和 `/api/animation-demos` 接口，内置 `create_animation_demo` 工具可生成受限结构化动画 Artifact；前端在聊天消息中识别动画工具结果并渲染可播放、暂停、重播和调速的 2D 动画卡片。
- 优化知识库文档入库：新增快速入库、标准入库、图谱入库三种模式；快速入库仅写入 chunks 与向量，标准/图谱入库支持限制本次新增节点和关系数量，避免小文档生成过多图谱数据并改善入库耗时。
- 优化全局知识图谱构建：Neo4j 图谱支持从普通文件自动识别系统级实体关系，前端提供写入前的关系增删改校对流程；面向用户移除 JSONL 三元组文件入口，并明确单个知识库内 LightRAG 图谱仍由文档入库自动构建。
- 优化网页读取预览内容：清除预览 HTML 中的跳转链接、图片、视频等多媒体元素，移除 href/src/srcset/data-src 属性，避免预览时加载外部资源或触发跳转。：URL 导入支持读取初始网页、发现同域 HTML 子页面、按 embedding 相似度排序、手动选择展开和入库；提交前先将所选页面清洗为 Markdown 产物并保存到 MinIO，用户可查看、编辑或删除清洗结果，再复用现有知识库文档处理任务。
- 下放扩展管理权限：普通管理员现在可进入扩展管理并完整管理 Tools、MCP、SubAgent、Skills；同步放开 Skill 管理接口权限并补充权限测试。
- 调整 Agent 知识库默认选择：未显式配置知识库时默认启用当前用户可访问的全部知识库，显式保存空列表仍表示不启用知识库。
- 优化评估基准自动生成：默认参考 chunks 数量改为 1；多 chunk 场景复用知识库向量检索选择相似 chunks，不再对全量 chunks 重新计算 embedding，并移除前端 Embedding 模型选择。
- 修复知识库文档入库状态回退：当已解析文件缺失 `markdown_file` 解析产物时，索引流程会将文件状态恢复为未解析，便于重新解析而不是停留在索引失败。
- 优化 Agent 输入框文件 mention：用户级 workspace 文件候选改为从独立 workspace API 递归加载，不再依赖 active thread；插入时仍转换为 `/home/gem/user-data/workspace/` 沙盒虚拟路径，并修复附件上传后未立即刷新 mention 候选的问题。
- 调整知识库思维导图后端结构：将思维导图路由文件重命名为知识库语义更明确的 router，并把文件列表整理、提示词构建、AI JSON 解析等纯逻辑下沉到知识库 utils。
- 收敛知识库评估后端结构：将评估指标、单题评估、答案生成提示词和自动基准生成算法下沉到 `knowledge/eval`，`EvaluationService` 保留任务、文件和持久化编排职责。
- 新增个人工作区预览与管理：提供独立于对话 thread 的用户级 workspace API，并增加“工作区”页面，用于浏览个人 workspace 文件、预览 Markdown/文本/代码/图片/PDF；支持新建文件夹、上传文件、下载文件、删除文件/文件夹和多选删除；工作区预览支持 Markdown/TXT 在右侧预览框内切换编辑并保存，其他格式和非工作区预览默认只读；知识库与团队空间入口先展示到占位层级；默认创建 `agents/AGENTS.md`，并在 Agent 执行时将其内容追加到系统提示词。
- 收敛为个人单用户模式：移除平台登录、注册、JWT、OIDC、API Key 管理和用户数量统计残留；前端默认系统所有者拥有最高权限，后端保留唯一系统 owner 作为对话、工作区和文件数据归属键。
- 扩展管理界面交互逻辑重构：将 MCP / Subagents / Skills 三个标签页从「左侧边栏 + 右侧详情面板」布局重构为「卡片式网格布局 + 路由跳转二级页面」布局，工具标签页改为卡片网格布局 + 弹窗详情（保持弹窗内容不变）。新增共享组件 `ExtensionCard`、`ExtensionCardGrid`、`ExtensionToolbar`、`ExtensionDetailLayout`，详情页（`McpDetailView`、`SubagentDetailView`、`SkillDetailView`）使用居中宽度限制，路由规划为 `/extensions/mcp/:name`、`/extensions/subagent/:name`、`/extensions/skill/:slug`。
- 统一卡片样式：`ExtensionCard` 新增 `tags` prop 支持传入 `[{label, color}]` 数组，内部使用 `<a-tag bordered=false size=small>` 渲染，与知识库卡片标签风格统一；知识库列表页 `DataBaseView` 改用 `ExtensionCard` + `ExtensionCardGrid` 替代原有自定义卡片，移除冗余 card 样式。
- 调整应用主导航：`AppLayout` 从默认窄栏升级为默认展开的侧边栏，保留折叠态图标导航；侧边栏样式收敛为 14px 文本 + 18px 图标的标准紧凑密度，并统一导航项、任务中心、GitHub、用户信息的图标与文字对齐。折叠态改为仅通过显式按钮展开，避免空白区域误触发。
- 合并智能体对话导航：移除 `AgentChatComponent` 内部聊天侧边栏，将新建对话入口和对话历史移动到 `AppLayout` 主侧边栏，并通过共享线程 store 统一管理历史列表、当前线程、重命名、删除、置顶和分页加载。
- 新增独立模型配置模块：增加 `model_providers` 表、独立管理接口和”模型配置”页面，支持 provider 基础信息、可配置模型列表端点、远端候选模型、`enabled_models` 的早期配置验证；启动时会补齐内置 provider 模板，`provider_type` 暂统一默认为 `openai`，该模块暂不接入现有运行时模型选择逻辑。远端模型加载默认使用 `/models` 获取 chat/通用模型，provider 声明 `embedding` 能力时使用 `/embeddings/models` 获取 embedding 候选，rerank 模型列表端点按供应商文档显式配置后加载；修复路由请求模型未接收 `embedding_base_url`/`rerank_base_url` 导致前端已填写仍被后端校验拦截的问题。补充手动添加模型能力：`enabled_models[i]` 新增可选 `source: "manual"|"remote"` 字段（默认 `remote`），管理员可通过”+ 手动添加”入口录入远端清单未覆盖的模型（典型：自部署 embedding/rerank），手动模型在前端跳过”远端不存在”的 stale 警告并显示「手动」标签；type 选项受 `provider.capabilities` 约束，后端在 `_normalize_payload` 与 `update_provider_config` 双层一致性校验中拦截越权写入。
- 统一前端 Markdown 预览渲染：新增共享 `MarkdownPreview` 组件与 `markdown_preview` 渲染工具，替换 Agent 消息、文件预览、知识库 chunk、任务工具结果、聊天导出等场景中的旧 `md-editor-v3/marked` 预览；支持 KaTeX、任务列表、frontmatter 卡片、Shiki 代码高亮、DOMPurify 清洗和浅层渲染缓存，并抽取 HTML 转义与代码语言归一化工具。Skill 详情页复用 `AgentFilePreview`，统一文件预览、编辑、保存和全屏交互。
- 优化远程 Skill 批量安装：`remote_skill_install_service.py` 新增 `install_remote_skills_batch()`，利用 `npx skills add --skill A --skill B --skill C` 原生多 skill 支持，将安装 N 个 skill 的仓库克隆次数从 2N 降至 1；配套新增路由 `POST /remote/install-batch`、前端 `installRemoteSkillsBatch()` API 方法和批处理 UI 逻辑。
- 调整内置 `ChatbotAgent` 为学习助手：新增只读学习计划概览接口，空会话展示当前用户 workspace 中登记的学习计划；提示词约束新主题先匹配历史计划、候选知识库需确认后再写入 Markdown 计划。
- 移除 OpenClaw Gateway 集成及其 WebSocket/RPC 配置、学习提醒调度器、历史警告学习、双向知识共享和 Agent 工具；保留通用站内通知能力。
- 新增独立 ClawBot 微信互通：后端直接调用微信 iLink Bot HTTP 接口，不依赖 OpenClaw Gateway 或插件宿主；支持系统设置扫码连接、状态查询、微信文字消息接收及学习助手回复。
- 更新正式文档：补充网页读取会话、清洗结果编辑、入库模式、学习助手文件约定和导航入口，并移除面向用户的 JSONL 三元组导入说明。
- 新增树状对话：用户可从指定消息创建子线程；线程元数据保存父线程、分支消息和分支点上下文快照；子线程首次提问继承该快照，前端侧栏按父子关系展示对话树，并提供“从此处分支”操作。该实现采用元数据关系和显式上下文快照，暂不包含 DAG 多父合并、引用边或画布编辑能力。

---

历史版本发布记录已迁移到 [版本变更记录](./changelog.md)。

维护说明：
- roadmap 仅保留未来规划（看板/Bugs/里程碑方向）。
- 具体版本发布内容统一维护在 changelog。
