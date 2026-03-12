# RiftAudioPipeline Runtime Worker 现状与后续计划（2026-03-11）

> 状态：当前主路径文档  
> 目的：只记录当前仓库已落地的 runtime worker 结构、明确仍需收口的债务，以及下一轮实施计划。  
> 适用范围：GitHub Actions、fake-github、本地 mock plane、百度上传补偿链路、Python 执行端 runtime worker 拆分。

---

## 1. 当前结论

当前仓库中的 runtime worker 主路径已经稳定为：

`workflow_dispatch.inputs.payload`
-> `dispatch-payload.json`
-> `job_runner`
-> `runtime_init`
-> `log_relay` + `pipeline-main` + `upload_worker`
-> `finalize_worker`

当前设计共识：

- `workflow_dispatch.inputs.payload` 仍不携带 plane bearer token、Access client id / secret；但现在允许在手动 workflow dispatch 场景下显式携带 `baidu.access_token`，仅用于绕过 `/api/baidu/token`。
- `job_runner` 现在分两种模式：有 `control_plane_base_url` 时启用完整 relay；为空时跳过 relay，只执行纯 pipeline 主线。
- `run_id` 在 GitHub Actions 场景下统一使用 `GITHUB_RUN_ID`；本地调试允许使用非 GitHub 真值，只要求链路内一致。
- `pipeline` 主线已经退回执行端职责，不再直接请求 plane。
- `database.json` 是百度远端索引快照，既是 init 输入，也是 finalize 输出；它不是本地任务队列。
- `state.sqlite3` 承担本地运行态、上传队列与收尾事实汇总职责，不替代 `database.json`。
- `faker_github`、`mock_server`、`mock_smoke`、`e2e_simulation` 仍位于顶层 `rift_localdev` 包，作为本地测试/联调入口；`workflow_dispatch` schema 与命令构造已经回收到 `rift_audio_pipeline.control_plane`，主线代码不再反向依赖 `rift_localdev`。
- GitHub artifact 不由 Python worker 处理，仍由 workflow 的 `actions/upload-artifact` 负责。

---

## 2. 当前运行结构

### 2.1 Workflow 入口

- workflow 会把 `github.event.inputs.payload` 写入 `dispatch-payload.json`。
- workflow 入口已经切到 `python -m rift_audio_pipeline.control_plane.job_runner`。
- Python 侧 runtime worker 主链的统一 supervisor 仍然是 `job_runner`。
- 若 workflow 未提供 `control_plane_base_url`，当前 supervisor 会直接跳过 relay，不再向 plane 发送生命周期日志。

### 2.2 `runtime_init`

`runtime_init` 当前负责：

1. 若 `inputs.payload.baidu` 存在，则优先使用手动传入的 `access_token`；否则回退到 plane `GET /api/baidu/token`。
2. 将 token 写入本地 `baidu-token.json`。
3. 下载或初始化本地 `database.json`。
4. 创建 `runtime/<run_id>/state.sqlite3`。
5. 将远端 `database.json` 快照导入 `remote_database_entries`。

### 2.3 `state.sqlite3`

当前最小状态库已经承担正式运行职责，核心表包括：

- `runtime_meta`
- `run_control`
- `upload_tasks`
- `new_file_facts`
- `sync_outbox`
- `remote_database_entries`

当前已落地的能力：

- 初始化 run 级控制状态。
- 记录远端索引快照。
- 追加上传任务。
- claim / complete / retry 上传任务。
- 记录本轮新增文件事实。
- 判断 upload drain。
- 标记 `drained` / `finalized`。
- 为 finalize 构造 `database.json` entries 与最终 report changes。

### 2.4 `pipeline-main`

当前 `pipeline-main` 仍由 `rift_audio_pipeline.pipeline.cli` 驱动，但职责已收敛为：

- 解析 manifest pair 与 targets。
- 执行 remote/local pipeline 主线。
- 产出本地 artifacts。
- 发送 relay 日志事件。
- 在存在 `state_db_path` 时，把 archive 上传任务写入 `state.sqlite3`。
- 在主线结束后封口 `run_control.task_production_open=0`。

主线不再负责：

- bootstrap control plane
- 主线内 heartbeat / report
- 主线内自启 relay 子进程
- 主线内直接 finalize 远端日志投递

### 2.5 `log_relay`

当前正式日志模型是：

- 主线发送
- relay 接收
- relay 转发

当前行为：

- `job_runner` 外部启动 relay。
- `pipeline-main` 通过 relay socket 发送 `start / event / terminal_summary / shutdown`。
- relay 继续负责 `heartbeat`、`/logs`、`/logs/finalize` 与失败终态推断。

文件观察型 `log_worker` 不再是当前主路径，不应继续扩展。

### 2.6 `upload_worker`

当前 `upload_worker` 已经是主路径组成部分，不再只是设计目标。

已落地能力：

- 从 `state.sqlite3` claim 上传任务。
- 执行单文件上传。
- 成功后记录 `new_file_facts`。
- 失败后写回重试时间。
- 在“生产封口 + 无未完成任务”时标记 `upload_phase_status='drained'` 并退出。

当前主路径里，archive 上传已经优先走 SQLite 队列，而不是直接在 orchestrator 中完成。

### 2.7 `finalize_worker`

当前 `finalize_worker` 已接入主路径，并承担统一收尾职责：

1. 等待 upload drain。
2. 从 SQLite 汇总新的 `database.json`。
3. 执行远端 `database.json -> database-日期前缀.json` 轮转。
4. 上传新的 `database.json`。
5. 按历史上限裁剪旧版本。
6. 通过 relay 发送最终 `report`。
7. 标记 `upload_phase_status='finalized'`。

---

## 3. 当前代码边界

### 3.1 已确认稳定的边界

- `dispatch payload` 仍采用 `inputs.payload` JSON 字符串 wrapper。
- `runtime_init` 是 `database.json` 的唯一 init 入口。
- `upload_worker` 是 archive 上传的正式执行器。
- `finalize_worker` 是 `database.json` 重建、远端轮转与最终 report 的正式执行器。
- `control_plane/runtime/` 现在承接非入口的 runtime 编排辅助逻辑；CLI 入口仍保持原模块路径不变。
- Python worker 不负责 GitHub artifact。

### 3.2 仍然存在的工程债务

以下问题不是“未完成主路径”，而是“当前主路径已可用，但仍有残留耦合与兼容分支”。

#### A. `job_runner` 仍然过重

当前 `job_runner` 同时承担：

- dispatch payload 读取
- `run_id` / runtime 路径解析
- `runtime_init` 调用
- relay 配置写入
- relay 进程启动
- `upload_worker` 进程启动
- pipeline command 构造
- pipeline env 注入
- pipeline 等待
- finalize 调用
- 最终结果汇总输出

这使它同时耦合了：

- 配置解析
- runtime layout 组装
- 子进程生命周期管理
- pipeline CLI 参数映射
- finalize 收尾顺序

当前它更像“编排器 + launcher + env builder + status collector”的混合体，而不是单纯 supervisor。

#### B. 过渡兼容残留仍在代码里

当前最主要的残留有：

- 顶层 `rift_localdev` 里的 `simulation` / `mock_smoke` 一类本地验证链路仍有“为了贴合当前主路径而补桥”的历史包袱，尚未完全统一到 job runner 级编排。

这些分支对现阶段有兼容价值，但会继续放大：

- 路径分叉
- 测试矩阵复杂度
- job runner 编排负担
- “当前主路径”与“旧兼容路径”混用风险

#### C. 命名与文档仍有历史残影

当前实现已经收敛到 `log_relay`，但仍需避免继续使用旧“文件观察型 log worker”语义描述当前架构。后续文档、测试命名与 CLI 说明应统一以 `relay` 为准。

---

## 4. 后续计划

### 4.1 第一优先级：删除过渡兼容残留

目标：让当前 runtime worker 主路径成为唯一主路径，减少双轨维护。

建议顺序：

1. 把 `rift_localdev` 中的 `mock_smoke`、`simulation` 等本地验证入口继续向 `job_runner -> upload_worker -> finalize_worker` 统一，而不是长期保留“半条主路径 + 补桥”的变体。
2. 继续把 `job_runner` 的 payload/command builder 与最终结果聚合抽到辅助模块，保持入口模块薄化。
3. 继续清理旧上传链路遗留概念，避免 `archive_publish.py` / `artifact_utils.py` 之外的历史命名继续混淆当前主路径。

完成标准：

- 主路径只有一套上传收尾路径。
- 旧 JSON 队列不再作为当前 runtime worker 主链的一部分。
- 本地 mock / simulation 入口与正式主路径的边界一致。

### 4.2 第二优先级：拆轻 `job_runner`

目标：把 `job_runner` 收敛成“顺序调度 + 结果聚合”的薄 supervisor。

建议拆分方向：

#### A. 提取运行计划对象

新增一个共享的 runtime plan / session 模型，集中承载：

- `run_id`
- runtime 目录布局
- relay 路径
- `state_db_path`
- token / database 文件路径
- pipeline CLI 参数
- 最终 report 所需的运行元信息

这样 `job_runner.main()` 不再自己拼接零散路径与命令。

#### B. 提取 launcher 层

把以下行为从 `job_runner.main()` 中拆成独立函数或模块：

- `prepare_relay(...)`
- `start_upload_worker(...)`
- `run_pipeline_main(...)`
- `run_finalize_worker(...)`
- `collect_run_result(...)`

要求：

- 每个 launcher 只负责一个进程或一个同步步骤。
- `job_runner.main()` 只表达顺序关系，不持有细节。

#### C. 提取 env / command builder

当前 `build_pipeline_command()` 和百度 env 注入仍属于“启动细节”。后续应抽成单独的 builder：

- 输入：runtime plan + dispatch payload
- 输出：pipeline command、pipeline env、标准化 metadata

这样 `job_runner` 就不再同时理解业务 payload 结构和子进程启动细节。

#### D. 统一 supervisor 输出模型

最终 `job_runner` 只输出一份统一的 run result：

- `run_id`
- `runtime_dir`
- `pipeline_returncode`
- `relay_returncode`
- `upload_returncode`
- `finalize_returncode`
- `database_file`
- `state_db_file`

输出模型独立后，后续无论本地模拟、GitHub Actions 还是未来 plane worker，都会更容易复用。

### 4.3 推荐的目标形态

理想的 runtime 拆分应为：

- `runtime_init`: 准备 token、`database.json`、`state.sqlite3`
- `log_relay`: 负责日志汇聚与转发
- `pipeline-main`: 负责计算与产物生成
- `upload_worker`: 负责消费上传队列
- `finalize_worker`: 负责 `database.json` 重建、轮转与最终 report
- `job_runner`: 只负责顺序调度、超时/退出码收集、最终摘要输出

也就是说，`job_runner` 不应继续增长为业务入口，而应退回到 supervisor。

---

## 5. 下一轮建议实施顺序

建议严格按以下顺序推进：

1. 先删除旧上传回退与 JSON 队列残留。
2. 再把 relay 启动/配置逻辑从 `pipeline.logging` 收口到 `control_plane`。
3. 然后提取 runtime plan / launcher / command builder，拆轻 `job_runner`。
4. 最后补针对“单一路径”后的测试与文档，确认旧路径断开后 mock / e2e 仍成立。

原因：

- 先删兼容残留，才能减少 `job_runner` 的分支数。
- 不先删双轨逻辑，`job_runner` 拆轻后仍会保留大量历史判断，收益有限。
- 先稳定边界，再做 supervisor 瘦身，测试面更清晰。

---

## 6. 本文档使用规则

本文档只记录：

- 当前仓库里已经存在的 runtime worker 主路径
- 当前仍存在的明确工程债务
- 下一轮应该实施的收口计划

本文档不再保留：

- 同一天早期阶段的施工快照
- 已失效的“未完成清单”
- 已被代码追平的旧设计待办
- 与当前主路径不一致的历史路线说明
