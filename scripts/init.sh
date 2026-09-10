#!/bin/bash

# 自学通初始化脚本（Linux/macOS）
# 创建唯一的 Docker 运行配置 .env，并预拉取开发环境所需镜像。

set -e

echo "🚀 初始化自学通项目..."
echo "=================================="

if [ -f ".env" ]; then
    echo "✅ .env 已存在，保留当前配置。"
else
    cp .env.template .env
    echo "✅ 已根据 .env.template 创建 .env。"
    echo "⚠️  启动前请编辑 .env："
    echo "   1. 至少填写一个模型供应商 API Key（默认是 SILICONFLOW_API_KEY）"
    echo "   2. 将 NEO4J_PASSWORD 修改为至少 8 位密码"
    echo "   3. 正式部署时修改 PostgreSQL 和 MinIO 默认密码"
fi

echo ""
echo "📦 拉取 Docker 镜像..."
echo "========================="

images=(
    "python:3.12-slim"
    "node:24-slim"
    "neo4j:5.26"
    "minio/minio:RELEASE.2023-03-20T20-16-18Z"
    "ghcr.io/astral-sh/uv:0.7.2"
    "nginx:alpine"
    "pgvector/pgvector:pg16"
    "redis:7-alpine"
)

for image in "${images[@]}"; do
    echo "🔄 正在拉取 ${image}..."
    if bash scripts/pull_image.sh "$image"; then
        echo "✅ 已拉取 ${image}"
    else
        echo "❌ 拉取 ${image} 失败"
        exit 1
    fi
done

echo ""
echo "🎉 初始化完成！"
echo "=========================="
echo "确认 .env 中的必填项后运行：docker compose up -d --build"
