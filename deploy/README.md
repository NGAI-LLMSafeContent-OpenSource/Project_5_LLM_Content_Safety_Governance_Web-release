# ModelScope 部署

使用仓库根目录 Dockerfile，类型 docker，对外监听 0.0.0.0:7860。账号须已完成实名认证与阿里云绑定，选择控制台实际可用的免费 CPU 配置。Docker 构建前端，FastAPI 同进程提供生产静态页面、SPA 路由和原有 /api 接口，/health 可用于健康检查。

本地 Docker 验证：`docker build -t topic5-web .`，然后 `docker run --rm -p 7860:7860 -v topic5-web-data:/mnt/workspace topic5-web`。访问 http://127.0.0.1:7860 与 /health。

默认使用 stub 与关键词检测，无需模型密钥；跨课题服务需独立部署并配置地址。数据库、任务产物位于 /mnt/workspace/topic5-web，可通过 STUDIO_DATA_DIR 配置。平台重建、迁移与持久化条件需自行核验；重要资料另做备份。不要把真实 .env、数据库或 API 密钥写入 Git；密钥使用 Studio Secrets。

先通过发布脚本更新 GitHub release/1.0，再同步所有平台；触发部署前核对实际构建分支与提交。检查构建日志、运行日志、首页、页面刷新、/health 与治理会话流程。
