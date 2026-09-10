# 自学通 / 自学通

自学通是基于 自学通 二次开发的个人自学平台，面向长期学习资料整理、知识库沉淀、知识图谱梳理和 AI 辅导。项目基于 LangGraph v1、Vue 3、FastAPI、LightRAG、PostgreSQL/pgvector 和 Neo4j 构建，开发环境通过 Docker Compose 统一管理。

当前版本仍保留 自学通 的智能体平台底座，但产品方向已经收敛为个人学习与知识管理：把 PDF、Word、Markdown、网页等资料转成可检索知识库，结合学习助手、个人工作区和知识图谱持续推进学习计划。

## 当前能力

- 学习助手：空会话展示 workspace 中的学习计划，围绕用户画像、知识库和计划推进学习主题。
- 知识库/RAG：支持文档上传、解析、分块、向量检索、重排、问答测试和评估。
- 网页资料入库：支持 URL 读取、同域页面发现、Markdown 清洗、人工预览编辑和提交入库。
- 知识图谱：支持 Neo4j 图谱浏览、实体关系管理，以及从普通资料中识别系统级关系并人工校对。
- 个人工作区：管理用户文件、智能体产物、Markdown/TXT 编辑、图片/PDF/代码预览和下载。
- 微信互通：通过独立的 ClawBot 微信 iLink Bot 接口扫码连接，将微信文字消息交给当前学习助手处理。
- 扩展能力：支持 Tools、MCP Servers、SubAgents、Skills 管理，供智能体在运行时调用。
- 平台能力：个人单用户最高权限、模型配置、任务中心、系统设置、文件存储和运行监控。

更完整的功能边界见 [自学通功能.md](自学通功能.md)，正式用户文档见 [docs](docs/index.md)。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3, Vite, Pinia, Ant Design Vue, Less |
| 后端 | Python 3.12+, FastAPI, Uvicorn, ARQ |
| Agent | LangGraph v1, deepagents, Tools, MCP, Skills, SubAgents |
| 外部集成 | ClawBot（微信 iLink Bot） |
| 知识库 | LightRAG, PostgreSQL/pgvector |
| 图谱 | Neo4j |
| 存储 | PostgreSQL, Redis, MinIO, 本地 `saves` |
| 文档解析 | Docling, Scrapling, PaddleX, RapidOCR, DeepSeek OCR |
| 部署 | Docker, Docker Compose |

## 目录结构

```text
.
├── backend/                  # FastAPI 服务、可复用 zixuetong 包、后端测试
│   ├── server/               # API 入口、路由和 worker 入口
│   ├── package/zixuetong/         # Agent、service、repository、knowledge、storage 等核心代码
│   └── test/                 # unit / integration / e2e 测试
├── web/                      # Vue 3 前端应用
├── docs/                     # VitePress 用户与开发文档
├── docker/                   # API/Web/Docs 镜像和沙盒 provisioner
├── saves/                    # 开发环境持久化数据、日志、知识库和 workspace 文件
├── models/                   # 本地模型挂载目录
├── scripts/                  # 初始化、镜像拉取等辅助脚本
├── ARCHITECTURE.md           # 稳定架构地图
├── AGENTS.md                 # 编码代理协作约束
├── CLAUDE.md                 # Claude/Codex 类代理可读的项目约束
├── CONTRIBUTING.md           # 贡献说明
├── Plan.md                   # 阶段性产品计划归档
├── fix_plan.md               # 已处理 Bug 修复计划归档
└── 自学通功能.md               # 当前功能边界清单
```

## 快速启动

Docker 运行配置统一放在根目录 `.env`。Docker Compose、API 和 Worker 使用同一份配置，不再读取 `.env.docker`。

```bash
# Linux/macOS：创建 .env 并拉取依赖镜像
./scripts/init.sh

# Windows PowerShell：创建 .env 并拉取依赖镜像
.\scripts\init.ps1

# 也可以只复制模板后手动填写
cp .env.template .env

# 构建并启动服务；Compose 会自动加载根目录 .env
docker compose up --build -d

# 查看服务状态和日志
docker compose ps
docker logs api-dev --tail 100
docker logs web-dev --tail 100
```

启动前必须在 `.env` 中完成两件事：

1. 至少填写一个模型供应商 API Key，默认模板提供 `SILICONFLOW_API_KEY`。
2. 设置至少 8 位的 `NEO4J_PASSWORD`。

PostgreSQL、Redis、MinIO、Sandbox 等配置均有可直接用于本地开发的默认值。`.env.template` 已逐项注明每个变量是否必填、用途、默认值和启用条件；正式部署时应修改 PostgreSQL、Neo4j 和 MinIO 密码。

启动后访问：

| 服务 | 地址 |
|------|------|
| Web 应用 | http://localhost:5173 |
| API 文档 | http://localhost:5050/docs |
| 文档站 | http://localhost:5174 |
| Neo4j Browser | http://localhost:7474 |
| MinIO Console | http://localhost:9001 |

启动后可直接进入 Web 应用；当前版本面向个人单用户使用，不再提供平台登录、注册或管理员初始化流程。详细安装和故障排查见 [快速开始指南](docs/intro/quick-start.md)。

## 开发工作流

本项目的开发事实来源是 [docker-compose.yml](docker-compose.yml)。`api-dev`、`worker-dev`、`web-dev` 和 `docs-dev` 都挂载本地源码，通常修改代码后不需要重启容器。

常用命令：

```bash
# 启动开发环境
docker compose up -d

# 查看容器与日志
docker ps
docker logs api-dev --tail 100
docker logs worker-dev --tail 100
docker logs web-dev --tail 100

# 后端格式化与测试
make format
docker compose exec api uv run pytest

# 前端构建或检查
docker compose exec web pnpm run build
docker compose exec web pnpm run lint
```

修改不熟悉的模块前，先读 [ARCHITECTURE.md](ARCHITECTURE.md)。新增或修改后端行为时，测试放在 `backend/test`，并参考 [测试规范](docs/develop-guides/testing-guidelines.md)。

## 文档入口

- [项目简介](docs/intro/project-overview.md)：产品定位、技术架构和适用场景
- [知识库与知识图谱](docs/intro/knowledge-base.md)：资料导入、检索、图谱和网页读取
- [学习助手](docs/agents/learning-assistant.md)：学习画像、总计划和子计划文件约定
- [模型配置](docs/intro/model-config.md)：模型供应商与模型列表配置
- [扩展管理](docs/agents/agents-config.md)：Agent、Tools、MCP、Skills、SubAgents
- [部署说明](docs/advanced/deployment.md)：生产部署与上线建议
- [开发路线图](docs/develop-guides/roadmap.md)：近期看板、已落地版本记录和后续规划

## 根目录文档约定

- `README.md` 是项目入口，只保留当前事实、启动方式和文档导航。
- `ARCHITECTURE.md` 只维护稳定架构边界，不记录易变实现细节。
- `自学通功能.md` 维护当前功能边界和裁剪注意事项。
- `Plan.md` 与 `fix_plan.md` 是历史计划归档，不作为当前待办的唯一来源。
- 正式用户文档统一放在 `docs/`，开发过程中的临时方案文档放在 `docs/vibe/`。

## 许可与贡献

贡献流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。提交信息建议遵循 Conventional Commits，并使用清晰的中文说明变更目的、影响范围和验证方式。
