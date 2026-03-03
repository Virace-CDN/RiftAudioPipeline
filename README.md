# RiftAudioPipeline

《英雄联盟》语音资源自动化流水线项目，目标是实现版本检测、资源差异处理、语音解包、打包与百度网盘上传的端到端自动化。

## 当前阶段

- 已完成项目目录骨架初始化。
- 已将百度官方 SDK 归档到 `third_party/baidu_sdk/`。
- 已建立百度 SDK 内部封装包：`src/rift_audio_pipeline/baidu/`。
- 已完成百度 OAuth、本地 token 管理、网盘核心 API 封装与单元测试。

## 快速开始

```bash
uv sync
uv run rift-audio-pipeline --output-path ./output
```

开发环境（含 `pytest`）：

```bash
uv sync --dev
```

## 依赖版本（已固定）

当前项目依赖已固定在 `pyproject.toml`：

- `httpx==0.28.1`
- `loguru==0.7.3`
- `python-dateutil==2.9.0.post0`
- `riotmanifest==2.1.0`
- `urllib3==2.6.3`
- `lol-audio-unpack` 跟踪 `v3-test` 分支（`@v3-test`）

## 低磁盘模式建议（GitHub Actions）

```bash
uv run rift-audio-pipeline \
  --output-path ./temp/lol_output \
  --temp-dir ./temp/mini_game \
  --local-bin-dir ./temp/downloaded_bins \
  --unpack-workers 1 \
  --low-disk-mode
```

- 运行时最小游戏环境会放在项目根目录 `temp/mini_game`，便于外部检查。
- `DataUpdater` / `BinUpdater` 执行完成后，会自动清理 LCU WAD 与 `bin_input`，降低峰值空间。
- `--low-disk-mode` 在模拟目录中启用实体级流式处理：`解包一个 -> 打包一个 -> 上传一个 -> 清理一个`。
- 流式模式会在每个实体完成后清理对应 WAD、音频目录与已上传压缩包，显著降低峰值占用。
- 若传入真实本地游戏目录（`--game-path`），会自动回退为高吞吐批量模式（批量解包后统一打包上传）。

## 百度 OAuth（本地授权码模式）

首次授权（授权码模式）：

```bash
uv run rift-baidu-oauth auth-url --dev-config .dev.baidu
```

浏览器授权后，拿到 `code` 再执行：

```bash
uv run rift-baidu-oauth exchange-code --code <授权码> --dev-config .dev.baidu
```

刷新 token：

```bash
uv run rift-baidu-oauth refresh-token --dev-config .dev.baidu
```

## 百度网盘工作目录约束

- `BaiduPanClient` 默认仅允许在配置的工作目录内执行常规操作（列表、创建、上传、下载、复制、重命名、删除）。
- 若路径超出工作目录，会给出“超限提示”并拒绝执行。
- 仅 `move_path` 允许将工作目录内产物移动到外部目录，并产生超限告警，便于最终发布落地。

## 上传目录与索引规则

- 上传目录按资源类型与目标分组组织：`VO|SFX|MUSIC/<champions|maps>/`。
- 同实体同类型存在旧版本时，旧文件会自动归档到：`OLD/<champions|maps>/`。
- 每次索引有变化时会回传两份索引文件：
  - `upload_manifest.json`：机器可读索引（幂等校验基线）。
  - `upload_manifest_readable.txt`：人类可读索引（便于网盘内检索与排查）。
- `upload_manifest.json` 内含 `database` 视图（按 `target_group + resource_type + entity_key` 聚合多版本），用于将索引作为长期数据库维护。
- 首次执行可接受远端索引缺失并自动初始化目录与索引；差异更新流程若远端缺失 `upload_manifest.json` 会直接终止，避免在索引失真状态继续上传。

## 差异更新日志

- 每次 diff 更新会产出并上传两份日志到 `update_logs/<目标版本>/`：
  - `*.json`：结构化日志，包含版本区间、WAD 变化、二次筛选明细、上传结果与原因。
  - `*.txt`：人类可读日志，便于网盘 Web 端检索与追踪。
