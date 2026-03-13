# 文档总览

本目录只保留和当前仓库实现一致、能直接指导开发、联调、验证和排障的文档。  
`temp/` 中的文件可以作为草案或设计输入阅读，但正式文档入口以这里为准。

## 先看什么

### 想快速理解项目

1. `../README.md`
2. `control_plane/README.md`
3. `pipeline/README.md`

### 想接 workflow dispatch / control plane

1. `control_plane/faker_github_api.md`
2. `control_plane/database_v2_and_netdisk_layout.md`
3. `control_plane/plane_required_interfaces_current.md`
4. `control_plane/runtime_worker_rearchitecture_2026-03-11.md`

### 想接 pipeline 本体

1. `pipeline/README.md`
2. `pipeline/contracts/pipeline_module_contracts.md`
3. `pipeline/testing/pipeline_real_data_testing.md`

## 当前文档分层

### `control_plane/`

覆盖 Python 侧 runtime worker 主线：

- workflow dispatch 与本地 fake GitHub 协议
- `runtime_init / log_relay / upload_worker / finalize_worker`
- v2 `database.json` 与 netdisk 布局
- plane 最小必需接口

### `pipeline/`

覆盖 pipeline 本体：

- 模块边界
- 真实数据测试入口
- mock / 单测 / 真链路的分层验证方式

## 当前推荐事实源

| 主题 | 主文档 |
| --- | --- |
| workflow dispatch 协议 | `control_plane/faker_github_api.md` |
| v2 数据库与历史归档规则 | `control_plane/database_v2_and_netdisk_layout.md` |
| plane 最小接口 | `control_plane/plane_required_interfaces_current.md` |
| runtime worker 当前职责边界 | `control_plane/runtime_worker_rearchitecture_2026-03-11.md` |
| pipeline 模块边界 | `pipeline/contracts/pipeline_module_contracts.md` |
| 真实数据测试 | `pipeline/testing/pipeline_real_data_testing.md` |

## 当前约束

- 当前正式数据库只认 v2 schema，不再默认兼容旧 `database` / 旧 `entries list`
- 用户可见 archive 与 meta 文件必须分根：
  - `archive_remote_root` 放用户可见包
  - `meta_remote_root` 放 `database.json`、日志、收据、轮转快照
- 新 `ALL` 覆盖旧单类型时，需要把旧 `VO / SFX / MUSIC` 移到 `_old_versions/`
- 远端下载、创建、移动前，必须先确认目录存在；不存在时先创建

## 文档维护原则

- 索引页负责“读什么”和“先后顺序”，不复制底层协议细节
- 具体协议写进对应主题文档，不把实现细节散落在多个索引页
- 若某条规则已经落到代码和测试，应优先更新正式 `docs/`，不要只停留在 `temp/`
