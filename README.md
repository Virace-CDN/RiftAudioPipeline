# RiftAudioPipeline

`RiftAudioPipeline` 是一个围绕《英雄联盟》音频资源处理的 Python 项目。当前仓库已经具备一条可落地的远端执行主线：

`workflow_dispatch -> job_runner -> runtime_init -> pipeline-main -> upload_worker -> finalize_worker`

这条主线同时覆盖两种运行模式：

- 带 control plane 的完整 relay 模式
- 不带 control plane 的纯 pipeline smoke 模式

当前稳定事实是：

- workflow 手动触发时，`inputs.payload` 必须是 JSON 字符串
- 执行线程当前只要求百度 `access_token`
- runtime 初始化、上传、收尾、`database.json` 重建、历史文件迁移都已经在 Python 侧闭环
- `database.json` 当前按 v2 结构导出，不再默认兼容旧 schema

## 仓库结构

| 路径 | 作用 |
| --- | --- |
| `src/rift_audio_pipeline/baidu/` | 百度 OAuth、网盘 API 适配层 |
| `src/rift_audio_pipeline/control_plane/` | workflow dispatch、runtime init、job runner、relay、upload、finalize |
| `src/rift_audio_pipeline/pipeline/` | 核心 pipeline CLI、实体处理、打包与日志输出 |
| `src/rift_localdev/` | 本地联调工具，包括 fake GitHub、mock plane、mock smoke、e2e harness |
| `docs/control_plane/` | control plane / runtime worker / v2 数据库与网盘布局文档 |
| `docs/pipeline/` | pipeline 模块边界与真实数据测试文档 |
| `tests/` | 单测与本地回归测试 |
| `temp/` | 临时设计稿与草案，不作为正式文档入口 |

## 当前脚本入口

`pyproject.toml` 当前公开这些入口：

- `rift-baidu-oauth`
- `rift-audio-pipeline`
- `rift-faker-github`
- `rift-control-plane-init`
- `rift-control-plane-job`
- `rift-control-plane-log-worker`
- `rift-control-plane-upload-worker`
- `rift-control-plane-finalize-worker`
- `rift-mock-control-plane`
- `rift-mock-smoke`
- `rift-control-plane-e2e`

## 运行主线

### 1. workflow dispatch

- 入口：`rift_audio_pipeline.control_plane.workflow_dispatch`
- 责任：解析 `inputs.payload`，把结构化 payload 翻译成 `job_runner` 命令
- 文档：`docs/control_plane/faker_github_api.md`

### 2. runtime init

- 入口：`rift_audio_pipeline.control_plane.runtime_init`
- 责任：
  - 获取百度 `access_token`
  - 下载或初始化 v2 `database.json`
  - 初始化 `state.sqlite3`
  - 在下载前先确保远端 `meta_remote_root` 目录存在

### 3. pipeline-main

- 入口：`rift_audio_pipeline.pipeline.cli`
- 责任：
  - 解析 manifests / targets
  - 执行下载、提取、比对与打包准备
  - 生成 upload task 和日志产物

### 4. upload worker

- 入口：`rift_audio_pipeline.control_plane.upload_worker`
- 责任：
  - 消费 `state.sqlite3` 中的上传任务
  - 打包 archive 并上传到 `archive_remote_root`
  - 上传前先确保远端父目录存在
  - 成功后写入 `new_file_facts`

### 5. finalize worker

- 入口：`rift_audio_pipeline.control_plane.finalize_worker`
- 责任：
  - 等待 upload phase drained
  - 基于 `remote_database_entries + new_file_facts` 生成 v2 `database.json`
  - 当本轮新 `ALL` 覆盖旧单类型时，把旧 `VO / SFX / MUSIC` 移到 `_old_versions/`
  - 上传并轮转 `meta_remote_root/database.json`
  - 在创建、列目录、移动前先确保目标远端目录存在

## `database.json` v2

当前正式数据库与网盘布局说明见：

- `docs/control_plane/database_v2_and_netdisk_layout.md`

关键规则摘要：

- active archive 统一放在 `archive_remote_root/{champions,maps}/`
- `database.json`、日志、收据、轮转快照统一放在 `meta_remote_root/`
- 新 `ALL` 出现时，只迁移同实体、版本更低的旧 `VO / SFX / MUSIC`
- 旧 `ALL` 之后出现更新版本的单类型时，两者都保留 active
- `_old_versions/` 只作为历史归档目录，不再计入 active `database.json`

## GitHub Actions 变量

`/.github/workflows/pipeline.yml` 当前依赖这些 Actions variables / secrets：

| 名称 | 类型 | 是否当前必需 | 作用 |
| --- | --- | --- | --- |
| `RIFT_CONTROL_PLANE_BASE_URL` | Actions variable | 条件必需 | 提供后启用完整 relay；留空则进入纯 pipeline smoke |
| `RIFT_CONTROL_PLANE_BEARER_TOKEN` | Actions secret | 否 | plane Bearer token |
| `RIFT_CONTROL_PLANE_ACCESS_CLIENT_ID` | Actions secret | 否 | Cloudflare Access client id |
| `RIFT_CONTROL_PLANE_ACCESS_CLIENT_SECRET` | Actions secret | 否 | Cloudflare Access client secret |

补充说明：

- relay 关闭时，必须在 `inputs.payload.baidu` 中显式提供 `access_token`
- 若提供 plane base URL 且未提供 `baidu`，`runtime_init` 会请求 `GET /api/baidu/token`

## 阅读顺序

如果你是第一次接手当前仓库，推荐顺序：

1. `docs/README.md`
2. `docs/control_plane/README.md`
3. `docs/control_plane/faker_github_api.md`
4. `docs/control_plane/database_v2_and_netdisk_layout.md`
5. `docs/control_plane/plane_required_interfaces_current.md`
6. `docs/pipeline/README.md`

## 本地验证

当前高价值的最小验证命令：

```bash
uv run pytest tests/test_baidu_pan.py \
  tests/test_control_plane_state_db.py \
  tests/test_control_plane_finalize_worker.py \
  tests/test_control_plane_upload_worker.py \
  tests/test_control_plane_job_runner.py \
  tests/test_pipeline_orchestrator.py -q
```

如果只验证 workflow dispatch / inputs 协议：

```bash
uv run pytest tests/test_faker_github.py tests/test_github_actions_workflow.py tests/test_control_plane_job_runner.py -q
```
