# Control Plane 文档索引

本目录描述的是“Python 执行端如何和 workflow dispatch、本地 fake GitHub、mock plane、真实 plane 协作”，不是前端控制台或 Cloudflare Pages 设计稿。

## 当前主线

当前稳定运行链路：

`workflow_dispatch -> job_runner -> runtime_init -> pipeline-main -> upload_worker -> finalize_worker`

对应职责：

- `workflow_dispatch`
  - 解析 `inputs.payload`
  - 组装 `job_runner` 命令
- `runtime_init`
  - 获取百度 token
  - 下载或初始化 v2 `database.json`
  - 初始化 `state.sqlite3`
- `upload_worker`
  - 消费上传队列
  - 上传 archive 到 `archive_remote_root`
- `finalize_worker`
  - 生成 v2 `database.json`
  - 处理 `_old_versions/` 历史迁移
  - 上传并轮转 `meta_remote_root/database.json`

## 本目录文档

### `faker_github_api.md`

适合处理这些问题：

- workflow dispatch 请求体现在长什么样
- `inputs.payload` 里哪些字段会下沉到 CLI
- 本地 `rift-faker-github` 怎么启动、怎么鉴权、怎么 dry-run

### `database_v2_and_netdisk_layout.md`

适合处理这些问题：

- v2 `database.json` 的结构
- `archive_remote_root` 与 `meta_remote_root` 的边界
- `_old_versions/` 的迁移规则
- 新 `ALL` 与新单类型产物如何影响 active 集合

### `plane_required_interfaces_current.md`

适合处理这些问题：

- plane 至少要提供哪些 HTTP 接口
- `GET /api/baidu/token` / `bootstrap` / `heartbeat` / `logs` / `report` 的当前最小字段
- 哪些旧字段已经不该再依赖

### `runtime_worker_rearchitecture_2026-03-11.md`

适合处理这些问题：

- 当前 runtime worker 的模块边界
- `job_runner` 还背着哪些 supervisor 负担
- 未来继续瘦身时该从哪里下手

### `pipeline_protocol_contracts.md`

适合处理这些问题：

- `run.json` / `events.jsonl` / `error.json` / `artifacts.json`
- 本地补偿队列与运行产物协议
- pipeline 对 Worker / plane 暴露的当前字段语义

## 推荐阅读顺序

### 接 workflow / fake GitHub

1. `faker_github_api.md`
2. `database_v2_and_netdisk_layout.md`
3. `plane_required_interfaces_current.md`

### 接 runtime worker 主线

1. `runtime_worker_rearchitecture_2026-03-11.md`
2. `pipeline_protocol_contracts.md`
3. `database_v2_and_netdisk_layout.md`

### 接 mock / 本地联调

1. `faker_github_api.md`
2. `plane_required_interfaces_current.md`
3. `runtime_worker_rearchitecture_2026-03-11.md`

## 当前约束

- 当前正式数据库为 v2，默认不兼容旧 schema
- archive 与 meta 必须分根，不允许把 `database.json` 混到用户可见 archive 根
- 远端下载、创建、移动前，必须先确保目标目录存在；目录缺失时先递归创建
