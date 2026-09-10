# 快速开始指南

欢迎使用自学通，这是一个面向个人长期学习的自学平台。
本指南将帮助你在几分钟内启动并运行系统，使你能够整理学习资料、构建个人知识库，并使用 AI 辅导推进学习计划。

## 环境要求

项目采用微服务架构设计，默认服务无需 GPU 支持。如果需要使用 OCR 功能，可以通过环境变量配置外部服务。

## 快速安装

### 步骤一：进入项目目录

```bash
# 在已获取的项目目录中执行
cd bishe
```

本文档面向当前项目目录维护，不依赖外部说明站点。

| 版本 | 适用场景 |
|------|----------|
| v0.6.x | 当前开发版本，包含最新特性 |
| main | 开发版本，包含最新特性（可能不稳定） |

### 步骤二：配置环境变量

项目只使用根目录 `.env` 作为 Docker 本地运行配置。Docker Compose、API 和 Worker 会读取同一份文件；`.env.docker` 已停止使用。

**方式一：使用初始化脚本（推荐）**

脚本会在 `.env` 不存在时复制 `.env.template`，并拉取当前 Compose 使用的基础镜像：

```bash
# Linux/macOS
./scripts/init.sh

# Windows PowerShell
.\scripts\init.ps1
```

脚本不会覆盖已有 `.env`。创建后请手动编辑 `.env`，至少完成：

1. 填写一个模型供应商 API Key；默认可填写 `SILICONFLOW_API_KEY`。
2. 将 `NEO4J_PASSWORD` 设置为至少 8 位密码。

**方式二：手动配置**

```bash
# Linux/macOS
cp .env.template .env

# Windows PowerShell
Copy-Item .env.template .env
```

`.env.template` 将配置分为以下类别，并在每个变量上方标注是否必填、默认值、用途和启用条件：

| 类别 | 是否必须修改 | 说明 |
|------|--------------|------|
| 模型供应商 API Key | 至少一项必填 | 后端必须检测到至少一个可用模型供应商 |
| `NEO4J_PASSWORD` | 必填 | 同时用于 Neo4j 初始化、健康检查和后端连接 |
| PostgreSQL | 本地开发可不改 | 默认用户、密码和数据库名由 Compose 统一使用 |
| Redis、MinIO | 本地开发可不改 | 使用 Compose 内部服务地址和开发默认凭据 |
| Sandbox | 可选 | 默认 Docker provisioner 可直接运行，仅高级部署需要修改 |
| Tavily、Langfuse | 按功能启用 | 分别用于联网搜索和模型调用观测 |
| ClawBot | 按功能启用 | 默认关闭，不影响基础系统启动 |

::: warning
`.env` 包含密码和 API Key，已被 `.gitignore` 忽略，不要提交。不要在 `.env.docker` 中保存密钥。
:::

::: tip API Key 获取
- **硅基流动**：访问 [cloud.siliconflow.cn](https://cloud.siliconflow.cn/i/Eo5yTHGJ)
- **Tavily**：访问 [app.tavily.com](https://app.tavily.com/) 获取搜索 API Key（可选）
:::

### 步骤三：启动服务

```bash
# 构建并启动所有服务
docker compose up --build -d
```

服务首次启动需要等待镜像拉取和编译，请耐心等待 2-3 分钟。

::: info 轻量模式（Lite Mode）
将 `.env` 中的 `LITE_MODE` 设置为 `true` 后，前后端会隐藏或跳过知识库与图谱入口和接口。当前 `docker-compose.yml` 仍会启动 Neo4j 容器并等待其健康检查；轻量模式目前不是精简容器数量的启动方案。
:::

### 步骤四：访问系统

服务启动后，访问以下地址：

| 服务 | 地址 |
|------|------|
| Web 界面 | http://localhost:5173 |
| API 文档 | http://localhost:5050/docs |

启动后可直接进入 Web 界面。当前版本面向个人单用户使用，不再提供平台登录、注册或管理员初始化流程。

## 故障排除

### 查看服务状态

```bash
# 查看所有容器状态
docker ps

# 实时查看后端日志
docker logs api-dev -f

# 实时查看前端日志
docker logs web-dev -f
```

### 常见问题

<details>
<summary><strong>Docker 镜像拉取失败</strong></summary>

如果网络原因导致镜像拉取失败，可以尝试：

```bash
# 手动拉取基础镜像
bash scripts/pull_image.sh python:3.12-slim
```

**离线环境部署方案**：

```bash
# 在有网络的环境导出镜像，注意检查镜像列表，不一定是最新的。
bash docker/save_docker_images.sh

# 传输到目标机器
scp docker_images_xxx.tar user@host:/path/

# 导入镜像
docker load -i docker_images_xxx.tar
```
</details>

<details>
<summary><strong>构建失败</strong></summary>

多数构建失败是由于网络问题。尝试配置代理：

```bash
# Linux/macOS
export HTTP_PROXY=http://IP:PORT
export HTTPS_PROXY=http://IP:PORT

# Windows PowerShell
$env:HTTP_PROXY="http://IP:PORT"
$env:HTTPS_PROXY="http://IP:PORT"
```

如果配置代理后反而失败，尝试移除代理后重试。
</details>

::: tip 调试面板
前端提供了调试面板（在头像菜单中可找到），可以查看详细的请求和响应信息。生产环境建议关闭此特性。
:::

## 下一步

- 了解如何配置模型：阅读 [模型配置](./model-config.md)
- 探索知识库功能：阅读 [知识库与知识图谱](./knowledge-base.md)
- 学习智能体开发：阅读 [智能体开发](../agents/agents-config.md)
- 深入了解配置系统：阅读 [配置系统详解](../advanced/configuration.md)
