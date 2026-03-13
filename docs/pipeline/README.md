# Pipeline 文档索引

本目录只讨论 pipeline 本体，不重复解释 workflow dispatch、plane 接口或 fake GitHub 协议。

## Pipeline 负责什么

`rift_audio_pipeline.pipeline` 当前负责：

- 解析 manifests 与目标实体
- 下载、解包、比对、映射
- 生成单实体产物目录
- 产出上传任务和本地日志/收据

它不直接负责：

- workflow dispatch 鉴权
- 远端 `database.json` 初始化
- archive 上传线程调度
- 最终 `database.json` 重建与历史归档迁移

这些职责分别在 `control_plane/runtime_init.py`、`upload_worker.py`、`finalize_worker.py` 中完成。

## 当前文档

### `contracts/pipeline_module_contracts.md`

适合处理这些问题：

- 本仓和上游模块的职责边界
- 哪些能力属于 `pipeline/`，哪些应该留在 control plane / localdev
- 模块拆分时不该跨越的边界

### `testing/pipeline_real_data_testing.md`

适合处理这些问题：

- mock / 单测 / 真实数据测试怎么分层
- 真实数据测试入口怎么跑
- 结果应该怎么判读

## 推荐阅读顺序

1. `contracts/pipeline_module_contracts.md`
2. `testing/pipeline_real_data_testing.md`

如果你接的是完整 runtime worker 主线，而不是纯 pipeline，本目录之外还应该补读：

1. `../control_plane/README.md`
2. `../control_plane/database_v2_and_netdisk_layout.md`

## 当前验证建议

### 只改 pipeline 逻辑

- 先跑受影响单测
- 再补 `uv run pytest tests/test_pipeline_orchestrator.py -q`

### 改到打包 / 上传边界

除了 pipeline 自身测试，还要补：

- `uv run pytest tests/test_control_plane_upload_worker.py -q`
- `uv run pytest tests/test_control_plane_finalize_worker.py -q`

### 改到远端数据库或 archive active 规则

至少补：

- `uv run pytest tests/test_control_plane_state_db.py -q`
- `uv run pytest tests/test_control_plane_finalize_worker.py -q`
