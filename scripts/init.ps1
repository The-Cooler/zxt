# 自学通初始化脚本（Windows PowerShell）
# 创建唯一的 Docker 运行配置 .env，并预拉取开发环境所需镜像。

Write-Host "🚀 初始化自学通项目..." -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan

if (Test-Path ".env") {
    Write-Host "✅ .env 已存在，保留当前配置。" -ForegroundColor Green
} else {
    Copy-Item ".env.template" ".env"
    Write-Host "✅ 已根据 .env.template 创建 .env。" -ForegroundColor Green
    Write-Host "⚠️  启动前请编辑 .env：" -ForegroundColor Yellow
    Write-Host "   1. 至少填写一个模型供应商 API Key（默认是 SILICONFLOW_API_KEY）"
    Write-Host "   2. 将 NEO4J_PASSWORD 修改为至少 8 位密码"
    Write-Host "   3. 正式部署时修改 PostgreSQL 和 MinIO 默认密码"
}

Write-Host ""
Write-Host "📦 拉取 Docker 镜像..." -ForegroundColor Cyan
Write-Host "=========================" -ForegroundColor Cyan

$images = @(
    "python:3.12-slim",
    "node:24-slim",
    "neo4j:5.26",
    "minio/minio:RELEASE.2023-03-20T20-16-18Z",
    "ghcr.io/astral-sh/uv:0.7.2",
    "nginx:alpine",
    "pgvector/pgvector:pg16",
    "redis:7-alpine"
)

foreach ($image in $images) {
    Write-Host "🔄 正在拉取 ${image}..." -ForegroundColor Yellow
    try {
        & scripts/pull_image.ps1 $image
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ 已拉取 ${image}" -ForegroundColor Green
        } else {
            Write-Host "❌ 拉取 ${image} 失败" -ForegroundColor Red
            exit 1
        }
    } catch {
        Write-Host "❌ 拉取 ${image} 失败：$_" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "🎉 初始化完成！" -ForegroundColor Green
Write-Host "==========================" -ForegroundColor Green
Write-Host "确认 .env 中的必填项后运行：docker compose up -d --build" -ForegroundColor Cyan
