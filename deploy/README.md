# ModelScope 部署

使用仓库根目录 Dockerfile，类型 docker，对外监听 0.0.0.0:7860。账号须已完成实名认证与阿里云绑定，选择控制台实际可用的免费 CPU 配置。Docker 构建前端，FastAPI 同进程提供生产静态页面、SPA 路由和原有 /api 接口，/health 可用于健康检查。

本地 Docker 验证：`docker build -t topic5-web .`，然后 `docker run --rm -p 7860:7860 -v topic5-web-data:/mnt/workspace topic5-web`。访问 http://127.0.0.1:7860 与 /health。

默认使用 stub 与关键词检测，无需模型密钥；跨课题服务需独立部署并配置地址。数据库、任务产物位于 /mnt/workspace/topic5-web，可通过 STUDIO_DATA_DIR 配置。平台重建、迁移与持久化条件需自行核验；重要资料另做备份。不要把真实 .env、数据库或 API 密钥写入 Git；密钥使用 Studio Secrets。

先通过发布脚本更新 GitHub release/1.0，再同步所有平台；触发部署前核对实际构建分支与提交。检查构建日志、运行日志、首页、页面刷新、/health 与治理会话流程。

## 当前部署入口的范围

此Docker入口启动API和静态前端，默认stub及关闭技能运行是离线演示配置，不代表完整治理任务已执行。使用真实治理功能时，按原后端README启用实际Provider，并用独立进程或部署编排运行 `python -m app.workers.governance_task_worker`；Worker与API须使用相同DATABASE_URL、资产目录和上游配置。当前Docker CMD不会自动启动Worker。

当前Studio网关曾拒绝原生DELETE请求。`deploy/serve.py` 可以处理带X-HTTP-Method-Override头的POST，但本发布已恢复原仓前端源码；原前端不再因VITE_HTTP_METHOD_OVERRIDE构建变量而自动转换请求。因此，不能据此宣称该网关下的删除等操作已通过。需要在独立部署层解决传输限制，或使用支持原生HTTP方法的部署环境；不要只修改某个平台的release源码。

本轮只同步release/1.0文件，未主动触发线上重建。完整模型/跨课题、后台Worker、持久化及网关方法兼容均需在所选实际环境另行验收。
