# 课题五：大模型内容安全治理平台

发布单位：NGAI-LLMSafeContent。版本：1.0.0。发布日期：2026-10-27。许可证：Apache-2.0。

本版发布Vue前端和FastAPI后端的实际源码，可在全新目录构建前端、初始化空SQLite数据库并启动健康检查。最小模式使用stub解释器与关键词配置，无需模型密钥；不提供跨课题模型和数据服务。

## 前置工具

Python 3.11+（含venv及pip）、Node.js 20或22、pnpm 9。可用`npm install -g pnpm@9.15.9`准备pnpm。Debian/Ubuntu若缺venv或ensurepip，安装系统对应的python3-venv及python3-pip。所有命令从克隆后的仓库根目录运行。

## 后端安装和启动

```bash
python3 -m venv .venv
# Linux/macOS使用.venv/bin/python；Windows替换为.venv/Scripts/python.exe
.venv/bin/python -m pip install -r web/backend/requirements.txt
cd web/backend
# 无须复制真实开发.env；默认禁用开发数据包自动导入，使用stub解释器
../../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 5800
```

在浏览器访问http://127.0.0.1:5800/health，预期返回code=0及data.status=ok；交互API文档见/docs。数据库在后端工作目录自动创建，不需要开发备份；建议SQLite文件放在本地文件系统上。

## 前端安装和启动

在另一个终端、仓库根目录执行：

```bash
pnpm --dir web/frontend install --frozen-lockfile
pnpm --dir web/frontend build
pnpm --dir web/frontend dev --host 127.0.0.1
```

浏览器访问http://127.0.0.1:5173。开发服务器将/api请求代理到本机5800端口；生产部署请将前端dist部署到静态站点，并配置/api反向代理。dist与node_modules不作为源码提交。

## 最小运行验收

```bash
python3 scripts/release_smoke.py
```

脚本在临时环境安装锁定依赖，执行后端健康与治理会话测试，实际启动空数据库HTTP服务并检查/health，构建前端并验证静态页面可访问；不复用开发数据库或未公开配置。首次运行需联网下载公开依赖。

## 配置和能力边界

示例配置为web/backend/.env.example和web/frontend/.env.example。最小模式不使用生产模型、私有API或跨课题服务。stub输出只用于流程验证，不代表真实模型审查或安全评测结论。

课题一至四的检索、评测、生成、护栏等能力需另行部署对应服务、获取合法模型和样例，并在环境变量中配置相应地址与凭据；未提供这些依赖的能力不属于本版最小验收范围。不要将真实.env、账号凭据、数据库、内部端点、私有评测包或模型加入发布物。

本包不含Docker任务、医学样例、内部文档、完整数据集、模型或预跑产物，空资源列表属于初始状态。跨课题数据默认不自动扫描或导入；只有明确配置路径后才可启用对应能力。

依赖清单见web/backend/requirements.txt及web/frontend/package.json/pnpm-lock.yaml。第三方组件说明见THIRD_PARTY_NOTICES.md；源Commit、覆盖后的文件哈希及测试命令见RELEASE_MANIFEST.json与SHA256SUMS。
