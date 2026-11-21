# ============================================================
# 前端开发环境一键启动脚本 (Windows PowerShell)
# 使用方法: .\scripts\dev.ps1
# ============================================================

Write-Host "=== 内容安全治理平台 - 前端开发环境 ===" -ForegroundColor Cyan

# 1. 检查 pnpm
if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
    Write-Host "错误: 未找到 pnpm, 请先安装 pnpm" -ForegroundColor Red
    exit 1
}

# 2. 安装依赖
Write-Host "[1/2] 安装依赖..." -ForegroundColor Yellow
pnpm install

# 3. 启动前端开发服务器
Write-Host "[2/2] 启动前端开发服务器..." -ForegroundColor Yellow
Write-Host "  前端: http://localhost:5173" -ForegroundColor Green
Write-Host "  后端 API 代理: /api -> http://localhost:5800" -ForegroundColor Green

pnpm dev
