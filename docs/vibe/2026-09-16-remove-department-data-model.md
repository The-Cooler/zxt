# 单用户部门数据模型清理

> 日期：2026-09-16

## 目标

将数据库中的智能体配置从旧部门作用域收敛为个人单用户结构，删除不再承担业务职责的部门模型和字段。

## 范围

- 删除 `Department` ORM 模型和 `departments` 表。
- 删除 `User.department_id`、角色、密码、手机号、头像、登录时间和软删除字段。
- 删除 `AgentConfig.department_id`，配置直接按 `agent_id` 分组。
- 删除固定个人配置作用域常量及默认部门初始化。
- 为已有 PostgreSQL 数据库清理旧外键、字段、索引和表，并建立单用户配置唯一约束。
- 更新受影响的调用、测试和开发路线记录。

## 验收标准

- 新数据库不创建 `departments` 表，`users` 和 `agent_configs` 不含 `department_id`。
- `users` 只保留系统 owner 的 `id`、`username`、`user_id` 和 `created_at`。
- 同一智能体的配置名称保持唯一，且最多存在一个默认配置。
- 智能体配置的列表、创建、读取、更新、默认切换和删除不再依赖部门作用域。

## Checklist

- [x] 创建独立 jj 节点
- [x] 清理系统 owner 实体属性
- [x] 清理 repository 与服务调用
- [x] 增加已有 PostgreSQL 结构迁移
- [x] 更新相关测试
- [x] 更新路线记录
- [ ] Docker 检查、测试与 Lint（Docker Desktop 当前未运行，无法连接 Docker 引擎）
