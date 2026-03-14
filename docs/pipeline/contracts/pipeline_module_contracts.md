# Pipeline 模块契约

## 核心边界

只保留当前代码和测试仍然支持的稳定约束如下：

- `RiotManifest`
  - 只负责 manifest pair、manifest 下载、WAD 差异与路径回填。
- `lol-audio-unpack`
  - 只负责 `AppContext` 初始化与上游 `update / extract / mapping` 执行。
- `RiftAudioPipeline`
  - 只负责 pipeline 编排、目标筛选、日志留痕、打包上传与补偿。

对当前用户可见入口，需要额外记住两点：

- pipeline 对外只保留 `extract` / `mapping` 两种阶段选择；`update` 已收口为隐式前置步骤，不再单独暴露为开关。
- pipeline 适配层默认向上游注入 `WITH_BP_VO=True`，因此英雄产物会默认尝试附带大厅选用/禁用语音。

因此，本仓后续演进时不应再次在仓内重写：

- remote snapshot 三元组解析
- 上游 remote 实体调度主链
- `AppContext` 配置模型
- WAD 级下载与提取细节

## 推荐模块拆分

当前代码与设计已经收敛到以下模块边界：

- `src/rift_audio_pipeline/pipeline/models.py`
  - 只定义配置、阶段、目标、事件与摘要模型。
- `src/rift_audio_pipeline/pipeline/logging.py`
  - 只处理日志落地、错误快照、日志补偿上传。
- `src/rift_audio_pipeline/pipeline/remote.py`
  - 只适配 manifest pair 与 remote 执行链路。
- `src/rift_audio_pipeline/pipeline/local.py`
  - 只适配 local 模式执行。
- `src/rift_audio_pipeline/pipeline/orchestrator.py`
  - 只负责编排，不直接承载底层 SDK 细节。
- `src/rift_audio_pipeline/pipeline/cli.py`
  - 只做参数解析与 orchestration 入口。

## 核心数据模型

后续若继续扩展，应优先围绕这些模型保持稳定：

- `PipelineMode`
- `PipelineStage`
- `PipelineRunConfig`
- `ManifestPairRef`
- `ProcessingTarget`
- `EntityArtifacts`
- `PipelineEvent`
- `PipelineRunSummary`

这些对象的价值在于：

- 把模块之间的交互从裸字典收敛为显式契约。
- 减少上游结构变化直接污染本仓。
- 让 orchestrator、日志、上传层能够独立演进。

## 调用约束

后续代码评审时，可以用下面几条作为快速检查表：

- `models.py` 不做 IO。
- `logging.py` 不做 manifest diff。
- `remote.py` 不处理百度上传。
- `orchestrator.py` 不直接操作第三方底层实现细节。
- `cli.py` 不承载业务判断。
