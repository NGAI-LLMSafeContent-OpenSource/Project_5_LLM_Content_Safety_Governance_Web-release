# 大模型内容安全治理平台

以Vue与FastAPI组织标准定义、训练数据治理、输出评测、风险归因及跨课题工具调用。

发布单位：NGAI-LLMSafeContent。发布分支：`release/1.0`；更新日期：2026-11-21；自研代码许可：Apache-2.0，第三方保留原许可。

## 功能

- 数据输入、课题一语料工具任务执行/归档及治理会话
- 动态Benchmark、风险评测、归因/审核与结果导出
- 跨课题适配器、前后端界面及服务器部署入口

## 安装与快速开始

Python ≥3.11、Node.js 20/22、pnpm 9；完整业务另需课题一至四服务、合法模型/数据与对应配置。

从公开仓下载同一发布分支：

```bash
git clone --branch release/1.0 https://github.com/NGAI-LLMSafeContent-OpenSource/Project_5_LLM_Content_Safety_Governance_Web-release.git
cd Project_5_LLM_Content_Safety_Governance_Web-release
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell改用 .venv\Scripts\Activate.ps1
```

以下命令均以仓库根目录为起点，注释中的外部条件需先准备：

```bash
python -m pip install -r web/backend/requirements.txt
cp web/backend/.env.example web/backend/.env
# 编辑.env，填写自己的数据库、运行目录、服务地址与凭据
(cd web/backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 5800)
# 另一个终端
pnpm --dir web/frontend install --frozen-lockfile
pnpm --dir web/frontend build
pnpm --dir web/frontend dev --host 127.0.0.1
```

## 使用与输出

打开 `http://127.0.0.1:5173`，后端 `/health` 验证健康。先准备所选课题的服务和资产，再从对应功能页发起任务并查看会话、归档或导出结果。部署入口见 `scripts/server/`，后端与前端各自README保留原运行说明。

## 配置与外部依赖

本轮将最新主分支前后端、路由、服务和迁移一并原样导出，未保留对这些文件的发布专用改写。ModelScope源码同步不自动更新线上运行分支；其网关对部分HTTP方法的限制需独立部署层处理，不能单独改动该平台release源码。

真实凭据只在自己的运行环境或平台Secrets中配置，不提交.env、用户上传、模型权重或运行结果。原仓文件中的内网服务地址经发布负责人确认按原样保留，使用者应在本地配置自己的可达服务。

## 验证与已知问题

完成对应依赖准备后运行：

```bash
python tools/release_check.py
```

检查包含发布文件完整性、原仓文件一致性与声明的最小测试。它不会自动下载模型或申请API，也不代表全部真实业务/准确率验收。保留的原仓错误、未运行项及外部依赖见 [KNOWN_ISSUES.md](KNOWN_ISSUES.md)。

## 发布版本与文件清单

本版本以原开发仓主分支提交 `6bc46b61da700a2054520d8b4af65cfd8f63599e` 为源。功能实现与对应原文件保持一致；README、许可说明和发布辅助材料单独登记。当前功能的必要源码、配置、界面与运行资源保留，明确弃用的原型、历史结果和开发缓存不捆绑。

- [逐文件发布清单](RELEASE_FILES.md)
- [原仓文件与Git对象对应关系](SOURCE_ALIGNMENT.json)
- [完整文件SHA-256及权限](RELEASE_MANIFEST.json)，校验表为SHA256SUMS

校验值按Git存储字节生成；若原.gitattributes规定检出换行转换，请用Git对象或发布检查脚本校验，避免将LF/CRLF误认为源码变化。各公开平台release/1.0使用同一个提交，平台生成的运行分支不属于此发布清单。

## 反馈、贡献与许可证

请通过 [公开仓Issues](https://github.com/NGAI-LLMSafeContent-OpenSource/Project_5_LLM_Content_Safety_Governance_Web-release/issues) 提交复现步骤、环境和日志摘要，勿附真实凭据或用户数据。代码问题由课题维护者在原开发仓处理，发布负责人同步审核后的版本；不要仅修一个平台造成分歧。

自研代码采用[Apache-2.0](LICENSE)。模型、数据集、外部服务和第三方代码遵循各自许可与使用条件，见[第三方说明](THIRD_PARTY_NOTICES.md)。
