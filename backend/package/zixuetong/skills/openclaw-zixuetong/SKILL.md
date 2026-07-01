---
name: openclaw-zixuetong
description: 与自学通知识库平台交互，查询 RAG 知识库，管理学习计划，并共享知识
version: 1.0.0
---

# 自学通知识库集成

本技能使 OpenClaw 能够与自学通知识库平台进行交互。

## 可用操作

### 查询知识库

当用户询问自学通知识库中可能包含的信息时，使用 `query_openclaw` 工具。支持语义检索和知识图谱查询。

查询建议：
- 使用关键词而非完整问题进行查询
- 如果首次查询结果不相关，尝试换用同义词或更具体的术语
- 可以通过 `db_name` 参数指定特定知识库

### 共享知识

当您获得了自学通用户可能受益的新知识时，使用 `share_knowledge_to_openclaw` 工具将其推送。共享的知识会被 OpenClaw 学习并可以在后续查询中使用。

## 知识库结构

- 自学通维护多个知识库 (KBs)，每个都包含分块的文档和向量索引
- 知识库使用 LightRAG 进行检索，支持 local/global/hybrid/mix 模式
- 每个知识库有一个思维导图结构，显示主题层次结构
- 知识库文件支持 PDF、Word、Markdown 等多种格式

## 学习上下文

- 用户有学习计划和进度跟踪
- 学习提醒基于不活跃周期和计划截止日期生成
- 历史警告和错误模式被分析以改进未来建议
- OpenClaw 可以通过知识共享 API 将新知识推送到自学通的知识库中

## API 端点

自学通提供以下 REST API 端点供 OpenClaw 回调：

- `POST /api/openclaw/knowledge/query` — 查询知识库
- `POST /api/openclaw/knowledge/list` — 列出可访问的知识库
- `POST /api/openclaw/knowledge/push` — 推送知识到指定知识库

这些端点支持 API Key 认证（使用 `yxkey_` 前缀的 key 通过 `Authorization: Bearer` 头传递）。
