# 内容安全治理平台 - 前端工程

基于数据价值的内容安全治理平台前端，Vue 3 + TypeScript + Vite 工程。

## 技术栈

| 层        | 技术                                        |
| --------- | ------------------------------------------- |
| 框架      | Vue 3.4 (Composition API, `<script setup>`) |
| 构建      | Vite 5                                      |
| 语言      | TypeScript (strict)                         |
| 状态管理  | Pinia                                       |
| 路由      | Vue Router 4                                |
| UI 组件库 | Element Plus                                |
| HTTP      | Axios                                       |
| 图表      | ECharts 5                                   |
| 后端      | FastAPI (Python, 位于 `../backend/`)        |

## 快速开始

```bash
# 1. 安装依赖
pnpm install

# 2. 启用 Git pre-commit hook（本机首次 clone / 拉取后执行一次）
pnpm setup:hooks

# 3. 启动开发服务器
pnpm dev          # http://localhost:5173

# 4. 构建生产版本
pnpm build

# 5. 类型检查
pnpm typecheck
```

## 本地服务矩阵

| 服务              | 默认地址                | 用途                              |
| ----------------- | ----------------------- | --------------------------------- |
| 前端 Vite         | `http://localhost:5173` | 本工程开发服务器                  |
| Project 5 后端    | `http://localhost:5800` | `/api` 代理目标，Swagger: `/docs` |
| Topic 3 Benchmark | `http://127.0.0.1:6006` | 后端输出评测上游服务              |
| Compliance 服务   | `http://127.0.0.1:6311` | 前端 `/compliance` 代理目标       |

前端通过 Vite 代理访问后端：

- `/api` -> `http://localhost:5800`
- `/compliance` -> `http://127.0.0.1:6311`

## 输出侧来源状态

输出内容治理页面区分真实服务、静态/预运行资产、演示样例和不可用状态，避免把服务失败误显示成真实实验结果。

| 状态                          | 含义                                                                   |
| ----------------------------- | ---------------------------------------------------------------------- |
| `benchmark` / `real`          | 来自课题 3 Benchmark 或 Cultural Gen 实时服务                          |
| `static` / `backend_snapshot` | 来自已配置的静态结果或本地快照                                         |
| `culture_assessment_static`   | 来自文化多样性评测 Benchmark 的静态数据集与 Direct vs 3-Agent 对比结果 |
| `demo_fixture`                | 明确标注的演示样例，不计入真实实验结果                                 |
| `unavailable` / `error`       | 上游服务不可用或请求失败，页面不静默生成 Mock 结果                     |

前端页面中的来源标签统一通过 `src/utils/outputHelpers.ts` 的 `dataSourceLabel` 维护。文化侧常用标签为 `Cultural Gen 实时`、`文化语料批次集合`、`静态资产`、`示例数据` 和 `服务不可用`，不要在单个页面内重复定义另一套文案。

当前输出侧真实运行依赖 Project 5 后端、Topic 3 Benchmark，以及文化多样性相关 Cultural Gen 服务。未启动上游服务时，页面应显示不可用或仅展示明确标注的静态资产。

测试数据选择按两条课题三轨道分流：风险 Benchmark 数据集只进入风险轨道；文化侧数据集只进入多样性轨道，不会发送至风险 Benchmark。`Project_3_Cultural_Generation_Tool` 的多民族文化样本集可进入多样性轨道并展示三维评分；文化语料生成工具的批次集合也可进入多样性轨道，并以 `corpus_static` 显式展示。`corpus_static` 只包含参考答案、评分规则和文化准确性审核结果，不等同于待测模型输出或正式“3 类 11 项”评测结果；已选数据面板支持按运行批次、民族和难度筛选批次样本。

`Project_3_Cultural_Diversity_Assessment_Tool` 的文化评测数据集以 `culture_assessment_static` 接入多样性轨道。该资产提供民族识别、文化差异度、综合通过率、L1/L2/L3 难度分档，以及 `普通 DeepSeek API vs 3-Agent` 的 30 条静态对比结果；它用于展示现阶段可执行评测口径，不宣称为完整文化标准体系分类树。

课题三文化语料实时生成已接入测试数据选择页右侧“文化语料实时生成”入口，并在 `src/api/output.ts` 提供启动、查询、读取样本和停止任务的调用封装。生成窗口只负责触发任务、展示进度、查看运行日志和同步批次集合，不再把单次生成结果作为第二个数据选择入口；用户需要在左侧数据集列表选择“文化语料生成批次集合”，再在右侧按运行批次、民族和难度筛选具体样本。实时生成面板参考 `Project_3_Cultural_Diversity_Corpus_Generation_Tool` 的 `http://127.0.0.1:8766/` 控制台，支持单样本生成、批量生成、运行批次、输出目录、Skill、知识库路径、Source 过滤、民族范围、L1/L2/L3 难度分布、随机种子、并发、模型和审核参数，用于小样本联调和可复现实验。若后端配置了 `CULTURAL_CORPUS_GENERATOR_BASE_URL`，任务生命周期由课题三 HTTP Job API `/api/generation/jobs` 管理；未配置时才使用 Project 5 本地联调适配器启动课题三脚本，页面会在任务卡片中显示接入模式。

测试数据选择页的左右数据区域采用随视口伸展的高面板布局：左侧数据集列表和右侧已选数据区都在各自区域内部滚动。文化语料实时生成作为右侧统计区下方的按钮入口，点击后以“文化语料生成工作台”弹窗打开；弹窗当前嵌入实时生成任务和批次历史复用，后续可继续承载原始项目中的模板配置、运行日志和样本预览能力，避免长期占用已选数据展示空间。

文化语料生成工作台的“批次历史与复用”通过 `/api/output/culture/corpus-samples?include_live_runs=true` 读取预跑批次和 Project 5 实时生成批次，按 `runId` 汇总样本量、民族分布、难度分布和预览样本。左侧数据集列表只保留“文化语料生成批次集合”这类集合资产；用户选择集合进入右侧已选数据后，再通过运行批次、民族和难度筛选具体样本。右侧运行批次默认只展示最近 30 个批次，并提供批次 ID 搜索，避免 `topic5_*` 实时生成批次无限增长导致下拉框不可用。进入评估页时按筛选条件重新加载匹配样本，若所选批次名以 `topic5_` 开头，评估查询会自动带上 `include_live_runs=true`。如果同时选择多个多样性数据源，当前评估优先使用文化语料批次集合，页面会在已选数据区域提示该优先级；评估页也会展示当前集合和筛选条件，避免用户不清楚实际评估样本来源。

文化语料批次集合的筛选和取样按“两层语义”处理：先用运行批次、民族、难度确定候选样本范围，再在候选范围内选择“使用当前筛选结果”或“从筛选结果随机取样”。“最多取样”只限制候选范围内的样本数量，不会覆盖批次、民族和难度筛选条件。

测试数据选择页的状态口径以“可进入轨道”为准：部分文化侧资产虽然原始状态来自待映射资产清单，但只要已具备读取适配并标记为 `selectable`，就会显示为可进入后续轨道；待映射统计仅统计尚不能直接进入流程的资产。

多样性评估页按文化侧资产类型切换展示口径：`Project_3_Cultural_Generation_Tool` 的动态文化样本集展示民族识别、文化类别、生成回答、参考答案、文化/语义/完整度三维评分和改进建议；文化语料批次集合展示运行批次、民族、难度、背景类型、文化知识点、参考答案、评分规则和审核结论，不套用三维模型评分。

选择文化评测 Benchmark 数据集时，多样性评估页以 `Project_3_Cultural_Diversity_Assessment_Tool` 控制台的静态展示口径为主：展示 Direct vs 3-Agent 的综合通过率、民族识别、文化差异度、L1/L2/L3 难度表现、分民族通过率、指标雷达图，以及 30 条样本级原问题/去民族化问题/回答/评测理由对照；多样性修正页同步展示 Direct 失败但 3-Agent 通过的样本，作为文化回答修正参考。

文化评测 Benchmark 的样本级回答对比采用“紧凑列表 + 点击详情”展示：列表只显示样本 ID、民族、难度、Direct/3-Agent 综合判定和优势摘要；点击样本后在右侧详情面板查看原问题、去民族化问题、两种回答、民族识别/文化差异度判定及评测理由，避免 30 条样本直接铺开导致页面拥挤。

多样性评估页的“数据实时评测”按钮通过 Project 5 后端代理访问 `Project_3_Cultural_Diversity_Assessment_Tool` 的 `culture_eval_console` 服务，默认地址为 `CULTURAL_ASSESSMENT_CONSOLE_BASE_URL=http://127.0.0.1:8877`。弹窗内保留 8877 控制台的核心任务控制口径：选择数据集、目标类型、运行后缀、limit、offset，点击“开始评测（按当前配置）”后轮询任务状态、进度、日志和结果摘要。弹窗中的可选数据集只来自测试数据选择页已选入多样性轨道的文化评测 Benchmark 数据集，不展示 8877 控制台的全部数据集。该功能需要先启动文化评测控制台。

测试数据选择页进入时会主动刷新文化评测 Benchmark 资产列表，避免后端服务重启或接口从不可用恢复后仍停留在旧资产状态。

多样性评估页提供“单条文化分析验证”入口，通过 `/api/output/culture/analyze` 代理 Cultural Gen 实时推理服务，用于检查文化侧服务连通性并查看民族识别、文化线索、知识依据和三维评分；该结果不写入正式评估样本。

多样性评估页将“样本个例”和“单条分析”合并在“文化样本验证与个例展示”模块内，通过页内分段 Tab 切换：默认展示批量样本个例，单条分析作为辅助验证工具收纳在同一模块下。样本表中的“复核”按钮会把当前样本带入单条分析接口，便于对个例进行文化侧服务连通性与推理结果核查。

多样性归因页当前定位为 Cultural Gen 解释性归因展示：基于动态文化样本集里的民族识别、文化线索、知识依据、文化/语义/完整度三维评分、错误示例和修正建议组织归因信息。该页面用于呈现已有文化生成项目的解释链路，不宣称为课题三正式 attribution 接口输出；文化语料批次集合缺少待测模型输出和三维评分，归因页会提示其更适合在评估页展示参考答案与评分规则。

多样性修正页当前定位为 Cultural Gen 修正建议展示：基于动态文化样本集里的生成回答、参考答案、错误示例、修正建议、改进项和三维最低分缺口组织修正案例；自定义输入仍通过 `/api/output/culture/analyze` 实时返回生成回答、错误分析和改进建议。该页面不混入 `Project_3_Compliance_Editing_Tool` 的通用合规编辑能力，避免把风险/合规改写误标为文化多样性专属修正。

多样性评估页和归因页的样例展示区域采用内部滚动容器，表头保持固定，避免大批量样本或归因卡片把页面整体向下拉长。

`Project_3_Cultural_Generation_Tool` 的动态文化样本集已接入测试数据选择页。Project 5 通过 `/api/output/culture/samples` 读取上游样本数据：默认走 `CULTURAL_GEN_DATA_BASE_URL=http://127.0.0.1:6323` 的 `/samples`，并兼容 `6322 /api/samples` 旧代理；单条分析仍走 `CULTURAL_GEN_BASE_URL=http://127.0.0.1:6322` 的 `/api/analyze`。选择该资产进入多样性轨道时，评估页加载 38 条真实样本，并展示文化适配、语义质量和完整度三维评分。

输出风险评估页采用双口径展示：

- 静态展示：展示 Topic 3 Benchmark 已产出的 `metrics / grouped_metrics / predictions`，页面会标注 `benchmark_static` 或 `backend_snapshot`。
- 动态运行：调用 Benchmark 任务接口进行现场验证，当前口径为单数据集 `binary` 风险评估，不等同于完整动态多标签评测。

风险标准确认页优先读取 `/api/output/risk-taxonomies/active` 返回的当前 Benchmark taxonomy，大类数、子类数、类别名称、类别定义和类别覆盖指标均以接口与静态结果为准；本地旧配置只作为 taxonomy 或静态结果不可用时的兜底说明。风险评估页的 C01-C17 类别表直接展示 Benchmark `per_category_metrics` 中的 `tp / fp / fn / precision / recall / f1`，不会再把类别指标显示成数据集明细。当上游 `/api/demo/predictions` 不可用时，页面会明确标注样本级预测接口不可用，而不是把它解释为数据集无样本。

## 当前源码地图

完整目录与文件用途以 [`docs/02-directory-structure.md`](./docs/02-directory-structure.md) 为准。README 只保留面向新同学的快速地图，避免目录树在多处重复维护。

```
web/frontend/
├── src/
│   ├── api/          # Axios 请求封装，模块级 API 函数
│   ├── assets/       # 全局样式和前端资源
│   ├── components/   # 页面组件：common / governance / home / definition / data-input / output / integration
│   ├── composables/  # 可复用 Composition API hooks
│   ├── router/       # 路由配置
│   ├── stores/       # Pinia 状态管理
│   ├── types/        # 全部类型定义、枚举、错误码
│   ├── utils/        # 工具函数、配置和 mock 数据
│   └── views/        # 路由级页面组件
├── docs/             # 工程规范文档
├── public/           # 静态资源（不经过编译）
└── scripts/          # 开发辅助脚本
```

当前路由级页面：

- `GovernanceView.vue`：统一治理会话主入口（独立全屏页面壳、最小会话创建与恢复）

治理会话首次发送非空请求时才创建；Tab 切换只进入该业务域空白状态。左栏展示统一服务端历史，刷新后恢复最近会话。浏览器仅保存客户端 ID、Schema 版本、业务域及最近会话 ID，不保存消息或结果。当前切片只保存请求，不执行治理能力。
- `HomeView.vue`：首页 Dashboard
- `DefinitionView.vue`：治理标准体系
- `DataInputView.vue`：输入语料治理
- `OutputView.vue`：输出内容治理
- `IntegrationView.vue`：课题集成

## 文档入口

建议按这个顺序阅读：

1. [`docs/00-project-constitution.md`](./docs/00-project-constitution.md)：项目铁律和术语
2. [`docs/02-directory-structure.md`](./docs/02-directory-structure.md)：当前目录结构和文件用途
3. [`docs/10-ownership-map.md`](./docs/10-ownership-map.md)：文件所有权边界
4. [`docs/05-api-contract.md`](./docs/05-api-contract.md)：前后端接口契约
5. [`docs/13-tooling-and-formatting.md`](./docs/13-tooling-and-formatting.md)：工具链、格式化和 Git hooks

文档索引见 [`docs/README.md`](./docs/README.md)。

## 分工约定

| 人员       | 模块                               | 主要文件范围                                                                                                                                                        |
| ---------- | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **董泓琳** | 输入语料治理                       | `components/data-input/`, `composables/data-input/`, `stores/input.ts`, `api/dataInput.ts`, `utils/input*`                                                          |
| **方子康** | 输出内容治理                       | `components/output/`, `composables/output/`, `stores/output.ts`, `api/output.ts`, `utils/output*`                                                                   |
| **共同**   | 统一治理入口、首页、治理标准、课题集成、基础设施 | `components/governance/`, `components/common/`, `components/home/`, `components/definition/`, `components/integration/`, `router/`, `stores/app.ts`, `stores/standard.ts`, `types/`, 样式文件 |

完整边界以 [`docs/10-ownership-map.md`](./docs/10-ownership-map.md) 为准。

## Git hooks（pre-commit）

仓库在根目录 `.husky/` 配置了 pre-commit：提交时仅对 **本次 staged 的前端文件** 自动跑 ESLint + Prettier（lint-staged），用于增量改善排版。

本机启用（每位开发者执行一次）：

```bash
cd web/frontend
pnpm install          # prepare 自动安装 husky 并设置本仓库 hooksPath
pnpm verify:hooks     # 确认 pre-commit 已就绪
```

验证是否生效：修改并 `git add` 任意 `src/` 下 `.vue` / `.ts` 后执行 `git commit`，应看到 `husky (pre-commit): 对 staged 前端文件执行 Prettier + ESLint...` 及 lint-staged 输出。

应急跳过：`HUSKY=0 git commit ...` 或 `git commit --no-verify`。

## 在开始写代码之前

1. `pnpm install` 安装依赖
2. `pnpm setup:hooks` 启用本机 pre-commit
3. `pnpm dev` 启动开发服务器，确认统一治理入口和旧业务页面可渲染、路由可切换
4. 对照 [`docs/10-ownership-map.md`](./docs/10-ownership-map.md) 确认自己负责的文件范围
5. 修改接口、目录或所有权边界时，同步更新对应文档

### 风险静态结果选择

风险评估页的静态结果按 Benchmark 资产的 `task + dataset_id + model_id` 组合加载。页面默认优先展示 `seed_v4_multilabel` 的 `multilabel_then_severity` 结果；切换结果时，指标和 predictions 使用同一组合查询，避免同名数据集下混入其他任务或模型的资产。
