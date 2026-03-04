# RiftAudioPipeline API 文档（含内部函数）

- 生成时间：2026-03-04 22:17:53
- 生成方式：基于 AST + Google 风格 Docstring 自动生成。
- 覆盖范围：`src/rift_audio_pipeline/**/*.py`、`scripts/*.py`、`main.py`（不含 tests 与 third_party）。

## 模块总览
| 模块 | 类数量 | 函数/方法数量 |
| --- | --- | --- |
| `main.py` | 0 | 0 |
| `scripts/run_daily_pipeline.py` | 0 | 0 |
| `scripts/test_baidu_pan_live.py` | 0 | 1 |
| `scripts/test_manifest_update_logic_live.py` | 1 | 6 |
| `scripts/test_pipeline_first_diff_live.py` | 0 | 14 |
| `scripts/test_single_unit_download_unpack_live.py` | 0 | 3 |
| `src/rift_audio_pipeline/__init__.py` | 0 | 0 |
| `src/rift_audio_pipeline/__main__.py` | 0 | 0 |
| `src/rift_audio_pipeline/asset_downloader.py` | 0 | 9 |
| `src/rift_audio_pipeline/audio_processor.py` | 1 | 11 |
| `src/rift_audio_pipeline/baidu/__init__.py` | 0 | 0 |
| `src/rift_audio_pipeline/baidu/cli.py` | 0 | 7 |
| `src/rift_audio_pipeline/baidu/oauth.py` | 5 | 27 |
| `src/rift_audio_pipeline/baidu/pan.py` | 4 | 32 |
| `src/rift_audio_pipeline/baidu/sdk.py` | 0 | 2 |
| `src/rift_audio_pipeline/bin_extractor.py` | 0 | 7 |
| `src/rift_audio_pipeline/cli.py` | 0 | 2 |
| `src/rift_audio_pipeline/config.py` | 1 | 1 |
| `src/rift_audio_pipeline/game_dir_builder.py` | 0 | 9 |
| `src/rift_audio_pipeline/manifest_ops.py` | 8 | 41 |
| `src/rift_audio_pipeline/packer.py` | 0 | 14 |
| `src/rift_audio_pipeline/pipeline/__init__.py` | 0 | 0 |
| `src/rift_audio_pipeline/pipeline/orchestrator.py` | 2 | 21 |
| `src/rift_audio_pipeline/pipeline/upload.py` | 2 | 32 |
| `src/rift_audio_pipeline/pipeline/utils.py` | 0 | 13 |

- 函数/方法总数：**252**
- 公开函数/方法：**88**
- 内部函数/方法：**164**
- 说明：内部函数判定规则为名称以 `_` 开头（含内部类的方法）。

## 模块 `main.py`
- 模块说明：兼容旧入口文件。
- 类数量：0
- 函数/方法数量：0

## 模块 `scripts/run_daily_pipeline.py`
- 模块说明：每日任务脚本入口。
- 类数量：0
- 函数/方法数量：0

## 模块 `scripts/test_baidu_pan_live.py`
- 模块说明：百度网盘 API 真实联调脚本。
- 类数量：0
- 函数/方法数量：1
- 函数索引：`main`

### 函数 `main`

#### `main() -> int`
- 可见性：公开函数
- 源码位置：`scripts/test_baidu_pan_live.py:19`
- 作用：执行百度网盘 API 联调流程。
- 实现方式：
  1. 调用 `load_baidu_app_credentials` 并写入 `app_credentials`。
  2. 调用 `resolve_token_store` 并写入 `token_store`。
  3. 调用 `token_store.load_token` 并写入 `oauth_token`。
  4. 调用 `BaiduCredentials` 并写入 `client_credentials`。
  5. 调用 `BaiduPanClient` 并写入 `client`。
  6. 调用 `strftime` 并写入 `run_id`。
  7. 调用 `Path` 并写入 `local_sample`。
  8. 调用 `Path` 并写入 `local_download`。
- 参数：
参数：无。
- 返回类型：`int`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`load_baidu_app_credentials`、`resolve_token_store`、`token_store.load_token`、`BaiduCredentials`、`BaiduPanClient`、`strftime`、`Path`、`print`、`client.get_quota`、`int`、`client.create_directory`、`local_sample.parent.mkdir`、`local_sample.write_text`、`client.upload_file`、`client.rename_path`、`client.copy_path`、`client.move_path`、`client.get_file_version_info`、`client.download_file`、`client.list_files`

## 模块 `scripts/test_manifest_update_logic_live.py`
- 模块说明：Manifest 更新判定真实联调测试。
- 类数量：1
- 函数/方法数量：6
- 类索引：`LiveCase`
- 函数索引：`_http_get_json`、`_fetch_manifest_url_from_repo`、`_build_latest_versions`、`_build_previous_state`、`_run_case`、`main`

### 类 `LiveCase`
- 可见性：公开类
- 源码位置：`scripts/test_manifest_update_logic_live.py:33`
- 作用：真实联调用例定义。
- 装饰器：`dataclass(frozen=True, slots=True)`
- 字段：
| 字段 | 类型 | 默认值 |
| --- | --- | --- |
| `name` | `str` | `-` |
| `latest_version` | `str` | `-` |
| `previous_version` | `str | None` | `-` |
| `expected_should_update` | `bool | None` | `-` |
| `expected_reason` | `str | None` | `-` |
- 方法数量：0

### 函数 `_http_get_json`

#### `_http_get_json(url: str) -> dict[str, Any]`
- 可见性：内部函数
- 源码位置：`scripts/test_manifest_update_logic_live.py:43`
- 作用：执行 HTTP GET 并解析 JSON。
- 实现方式：
  1. 调用 `Request` 并写入 `request`。
  2. 在上下文管理器中执行资源操作。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `url` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`Request`、`urlopen`、`json.loads`、`decode`、`response.read`

### 函数 `_fetch_manifest_url_from_repo`

#### `_fetch_manifest_url_from_repo(version: str) -> str`
- 可见性：内部函数
- 源码位置：`scripts/test_manifest_update_logic_live.py:58`
- 作用：从 Morilli 历史仓库读取指定版本的 manifest URL。
- 实现方式：
  1. 调用 `_http_get_json` 并写入 `payload`。
  2. 调用 `replace` 并写入 `encoded_content`。
  3. 根据条件分支选择不同处理路径。
  4. 返回 `base64.b64decode(encoded_content).decode('utf-8').strip()` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_http_get_json`、`replace`、`strip`、`RuntimeError`、`str`、`decode`、`quote`、`payload.get`、`base64.b64decode`

### 函数 `_build_latest_versions`

#### `_build_latest_versions(version: str, manifest_url: str) -> LatestVersions`
- 可见性：内部函数
- 源码位置：`scripts/test_manifest_update_logic_live.py:69`
- 作用：构建最新版本对象。
- 实现方式：
  1. 返回 `LatestVersions(game_version=version, game_manifest_url=manifest_url, lcu_version='16.4', lcu_manifest_url='https://example.invalid/lcu.manifest')` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `manifest_url` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`LatestVersions`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`LatestVersions`

### 函数 `_build_previous_state`

#### `_build_previous_state(version: str, manifest_url: str) -> LocalRunState`
- 可见性：内部函数
- 源码位置：`scripts/test_manifest_update_logic_live.py:80`
- 作用：构建历史状态对象。
- 实现方式：
  1. 返回 `LocalRunState(schema_version=1, game_version=version, game_manifest_url=manifest_url, lcu_version='16.3', lcu_manifest_url='https://example.invalid/lcu-old.manifest', checked_at=datetime.now(tz=timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `manifest_url` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`LocalRunState`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`LocalRunState`、`replace`、`isoformat`、`datetime.now`

### 函数 `_run_case`

#### `_run_case(case: LiveCase, manifest_urls: dict[str, str]) -> UpdateDecision`
- 可见性：内部函数
- 源码位置：`scripts/test_manifest_update_logic_live.py:95`
- 作用：执行单个测试用例。
- 实现方式：
  1. 调用 `_build_latest_versions` 并写入 `latest`。
  2. 返回 `evaluate_update_need_with_latest(region=TEST_REGION, latest_versions=latest, previous_state=previous_state)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `case` | `LiveCase` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `manifest_urls` | `dict[str, str]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`UpdateDecision`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_build_latest_versions`、`evaluate_update_need_with_latest`、`_build_previous_state`

### 函数 `main`

#### `main() -> int`
- 可见性：公开函数
- 源码位置：`scripts/test_manifest_update_logic_live.py:111`
- 作用：脚本主入口。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 遍历集合并执行批量处理。
  3. 执行 `print` 触发副作用逻辑。
  4. 执行 `print` 触发副作用逻辑。
  5. 执行 `print` 触发副作用逻辑。
  6. 执行 `print` 触发副作用逻辑。
  7. 遍历集合并执行批量处理。
  8. 根据条件分支选择不同处理路径。
- 参数：
参数：无。
- 返回类型：`int`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`print`、`_fetch_manifest_url_from_repo`、`LiveCase`、`_run_case`、`results.append`、`json.dumps`、`filter_wad_changes_by_bin_voice_paths`、`LIVE_OUTPUT_DIR.mkdir`、`detail_file.write_text`、`len`、`list`、`failed.append`

## 模块 `scripts/test_pipeline_first_diff_live.py`
- 模块说明：本地完整 Pipeline 联调脚本（首次/非首次 diff，单单位）。
- 类数量：0
- 函数/方法数量：14
- 函数索引：`_build_parser`、`_configure_log_level`、`_http_get_json`、`_fetch_manifest_url_from_repo`、`_limit_targets_to_units`、`_build_latest_versions_override`、`_is_champion_manifest_wad_path`、`_build_single_champion_smoke_filter`、`_patch_pipeline_for_local_live_test`、`_prepare_first_run_state`、`_prepare_diff_run_state`、`_build_pipeline_config`、`_collect_upload_archives`、`main`

### 函数 `_build_parser`

#### `_build_parser() -> ArgumentParser`
- 可见性：内部函数
- 源码位置：`scripts/test_pipeline_first_diff_live.py:50`
- 作用：构建命令行参数。
- 实现方式：
  1. 调用 `ArgumentParser` 并写入 `parser`。
  2. 执行 `parser.add_argument` 触发副作用逻辑。
  3. 执行 `parser.add_argument` 触发副作用逻辑。
  4. 执行 `parser.add_argument` 触发副作用逻辑。
  5. 执行 `parser.add_argument` 触发副作用逻辑。
  6. 执行 `parser.add_argument` 触发副作用逻辑。
  7. 执行 `parser.add_argument` 触发副作用逻辑。
  8. 执行 `parser.add_argument` 触发副作用逻辑。
- 参数：
参数：无。
- 返回类型：`ArgumentParser`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`ArgumentParser`、`parser.add_argument`、`str`

### 函数 `_configure_log_level`

#### `_configure_log_level(level: str) -> None`
- 可见性：内部函数
- 源码位置：`scripts/test_pipeline_first_diff_live.py:182`
- 作用：配置全局日志输出等级。
- 实现方式：
  1. 调用 `upper` 并写入 `normalized`。
  2. 执行 `logger.remove` 触发副作用逻辑。
  3. 执行 `logger.add` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `level` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`upper`、`logger.remove`、`logger.add`、`level.strip`

### 函数 `_http_get_json`

#### `_http_get_json(url: str) -> dict[str, Any]`
- 可见性：内部函数
- 源码位置：`scripts/test_pipeline_first_diff_live.py:197`
- 作用：执行 HTTP GET 并解析 JSON。
- 实现方式：
  1. 调用 `Request` 并写入 `request`。
  2. 在上下文管理器中执行资源操作。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `url` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`Request`、`urlopen`、`json.loads`、`decode`、`response.read`

### 函数 `_fetch_manifest_url_from_repo`

#### `_fetch_manifest_url_from_repo(version: str) -> str`
- 可见性：内部函数
- 源码位置：`scripts/test_pipeline_first_diff_live.py:212`
- 作用：读取指定版本 manifest URL（优先发布源，回退 Morilli 仓库）。
- 实现方式：
  1. 调用 `RiotGameData` 并写入 `releases`。
  2. 执行 `releases.load_game_data` 触发副作用逻辑。
  3. 调用 `get` 并写入 `release_items`。
  4. 遍历集合并执行批量处理。
  5. 使用异常处理分支兜底失败路径。
  6. 调用 `replace` 并写入 `encoded_content`。
  7. 根据条件分支选择不同处理路径。
  8. 返回 `base64.b64decode(encoded_content).decode('utf-8').strip()` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`RiotGameData`、`releases.load_game_data`、`get`、`replace`、`strip`、`_http_get_json`、`RuntimeError`、`getattr`、`version.strip`、`Request`、`str`、`decode`、`urlopen`、`payload.get`、`item.get`、`quote`、`base64.b64decode`、`response.read`

### 函数 `_limit_targets_to_units`

#### `_limit_targets_to_units(targets: object, limit_units: int) -> object`
- 可见性：内部函数
- 源码位置：`scripts/test_pipeline_first_diff_live.py:245`
- 作用：将处理目标截断到指定数量（优先英雄）。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 调用 `tuple` 并写入 `champion_ids`。
  3. 调用 `tuple` 并写入 `map_ids`。
  4. 根据条件分支选择不同处理路径。
  5. 返回 `type(targets)(champion_ids=tuple(), map_ids=selected_maps)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `targets` | `object` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `limit_units` | `int` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`object`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`tuple`、`type`、`int`、`getattr`

### 函数 `_build_latest_versions_override`

#### `_build_latest_versions_override(version: str) -> LatestVersions`
- 可见性：内部函数
- 源码位置：`scripts/test_pipeline_first_diff_live.py:262`
- 作用：构建测试用“最新版本”覆盖对象。
- 实现方式：
  1. 调用 `version.strip` 并写入 `normalized_version`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `get_latest_versions` 并写入 `latest`。
  4. 调用 `_fetch_manifest_url_from_repo` 并写入 `manifest_url`。
  5. 返回 `LatestVersions(game_version=normalized_version, game_manifest_url=manifest_url, lcu_version=latest.lcu_version, lcu_manifest_url=latest.lcu_manifest_url)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`LatestVersions`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`version.strip`、`get_latest_versions`、`_fetch_manifest_url_from_repo`、`LatestVersions`、`ValueError`

### 函数 `_is_champion_manifest_wad_path`

#### `_is_champion_manifest_wad_path(path: str) -> bool`
- 可见性：内部函数
- 源码位置：`scripts/test_pipeline_first_diff_live.py:278`
- 作用：判断 manifest WAD 路径是否为英雄资源。
- 实现方式：
  1. 返回 `'/champions/' in path.strip().replace('\\', '/').casefold()` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`bool`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`casefold`、`replace`、`path.strip`

### 函数 `_build_single_champion_smoke_filter`

#### `_build_single_champion_smoke_filter(original_filter: Callable[..., ManifestVoiceFilterResult]) -> Callable[..., ManifestVoiceFilterResult]`
- 可见性：内部函数
- 源码位置：`scripts/test_pipeline_first_diff_live.py:284`
- 作用：构建 diff 联调快捷筛选函数。
- 实现方式：
  1. 返回 `_patched_filter` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `original_filter` | `Callable[..., ManifestVoiceFilterResult]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`Callable[..., ManifestVoiceFilterResult]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`kwargs.get`、`tuple`、`set`、`enumerate`、`ManifestVoiceFilterResult`、`isinstance`、`len`、`original_filter`、`dict`、`all_decisions.extend`、`all_skipped.update`、`any`、`logger.info`、`replace`、`_is_champion_manifest_wad_path`、`sorted`、`path.strip`

### 函数 `_patch_pipeline_for_local_live_test`

#### `_patch_pipeline_for_local_live_test(state_file: Path, limit_units: int, latest_versions_override: LatestVersions | None, diff_smoke_single_champion: bool) -> Iterator[None]`
- 可见性：内部函数
- 源码位置：`scripts/test_pipeline_first_diff_live.py:345`
- 作用：临时 patch Pipeline 状态路径与目标解析函数。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 使用异常处理分支兜底失败路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `state_file` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `limit_units` | `int` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `latest_versions_override` | `LatestVersions | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `diff_smoke_single_champion` | `bool` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`Iterator[None]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`original_resolve_processing_targets`、`_limit_targets_to_units`、`original_resolve_all_processing_targets`、`load_local_state`、`evaluate_update_need_with_latest`、`_build_single_champion_smoke_filter`、`original_evaluate_update_need`

### 函数 `_prepare_first_run_state`

#### `_prepare_first_run_state(state_file: Path) -> None`
- 可见性：内部函数
- 源码位置：`scripts/test_pipeline_first_diff_live.py:409`
- 作用：准备首次运行状态（删除本地历史状态）。
- 实现方式：
  1. 执行 `state_file.parent.mkdir` 触发副作用逻辑。
  2. 执行 `state_file.unlink` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `state_file` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`state_file.parent.mkdir`、`state_file.unlink`

### 函数 `_prepare_diff_run_state`

#### `_prepare_diff_run_state(state_file: Path, previous_version: str) -> LocalRunState`
- 可见性：内部函数
- 源码位置：`scripts/test_pipeline_first_diff_live.py:416`
- 作用：准备非首次 diff 状态（写入旧版本历史状态）。
- 实现方式：
  1. 调用 `get_latest_versions` 并写入 `latest`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `_fetch_manifest_url_from_repo` 并写入 `previous_manifest_url`。
  4. 调用 `replace` 并写入 `checked_at`。
  5. 调用 `LocalRunState` 并写入 `state`。
  6. 执行 `save_local_state` 触发副作用逻辑。
  7. 返回 `state` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `state_file` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `previous_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`LocalRunState`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`get_latest_versions`、`_fetch_manifest_url_from_repo`、`replace`、`LocalRunState`、`save_local_state`、`previous_version.strip`、`latest.game_version.strip`、`ValueError`、`isoformat`、`datetime.now`

### 函数 `_build_pipeline_config`

#### `_build_pipeline_config(region: str, output_path: Path, game_path: Path | None, temp_game_dir: Path, audio_type: str, download_concurrency: int, diff_bin_filter_workers: int, diff_bin_extract_concurrency: int, diff_bin_filter_threshold: int, unpack_workers: int, low_disk_mode: bool, remote_dir: str, app_key: str, secret_key: str, refresh_token: str, pack_password: str | None, pack_encrypt_filenames: bool) -> PipelineConfig`
- 可见性：内部函数
- 源码位置：`scripts/test_pipeline_first_diff_live.py:439`
- 作用：构建脚本专用 Pipeline 配置。
- 实现方式：
  1. 返回 `PipelineConfig(output_path=output_path, game_region=region, game_path=game_path, audio_types=(audio_type,), temp_dir=temp_game_dir, baidu_pan_remote_dir=remote_dir, baidu_pan_app_key=app_key, baidu_pan_secret_key=secret_key, baidu_pan_refresh_token=refresh_token, download_concurrency=max(1, download_concurrency), diff_bin_filter_workers=max(1, diff_bin_filter_workers), diff_bin_extract_concurrency=max(1, diff_bin_extract_concurrency), diff_bin_filter_threshold=diff_bin_filter_threshold, unpack_workers=max(1, unpack_workers), low_disk_mode=low_disk_mode, enable_pack=True, enable_upload=True, pack_password=pack_password, pack_encrypt_filenames=pack_encrypt_filenames)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `region` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `output_path` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `game_path` | `Path | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `temp_game_dir` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `audio_type` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `download_concurrency` | `int` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `diff_bin_filter_workers` | `int` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `diff_bin_extract_concurrency` | `int` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `diff_bin_filter_threshold` | `int` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `unpack_workers` | `int` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `low_disk_mode` | `bool` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_dir` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `app_key` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `secret_key` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `refresh_token` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `pack_password` | `str | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `pack_encrypt_filenames` | `bool` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`PipelineConfig`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`PipelineConfig`、`max`

### 函数 `_collect_upload_archives`

#### `_collect_upload_archives(output_path: Path, game_version: str | None, limit_units: int) -> tuple[str, tuple[Path, ...]]`
- 可见性：内部函数
- 源码位置：`scripts/test_pipeline_first_diff_live.py:483`
- 作用：收集 upload 模式所需压缩包。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `tuple` 并写入 `archives`。
  4. 根据条件分支选择不同处理路径。
  5. 根据条件分支选择不同处理路径。
  6. 返回 `(resolved_version, archives)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `output_path` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `game_version` | `str | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `limit_units` | `int` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[str, tuple[Path, ...]]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`tuple`、`sorted`、`game_version.strip`、`package_dir.is_dir`、`FileNotFoundError`、`packages_root.is_dir`、`packages_root.iterdir`、`item.is_dir`、`item.name.casefold`、`package_dir.rglob`、`item.is_file`、`casefold`、`item.as_posix`

### 函数 `main`

#### `main() -> int`
- 可见性：公开函数
- 源码位置：`scripts/test_pipeline_first_diff_live.py:520`
- 作用：脚本主入口。
- 实现方式：
  1. 调用 `parse_args` 并写入 `args`。
  2. 执行 `_configure_log_level` 触发副作用逻辑。
  3. 调用 `resolve` 并写入 `work_dir`。
  4. 根据条件分支选择不同处理路径。
  5. 执行 `work_dir.mkdir` 触发副作用逻辑。
  6. 调用 `load_baidu_app_credentials` 并写入 `app_credentials`。
  7. 调用 `resolve_token_store` 并写入 `token_store`。
  8. 调用 `token_store.load_token` 并写入 `token`。
- 参数：
参数：无。
- 返回类型：`int`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`parse_args`、`_configure_log_level`、`resolve`、`work_dir.mkdir`、`load_baidu_app_credentials`、`resolve_token_store`、`token_store.load_token`、`str`、`_build_pipeline_config`、`print`、`work_dir.exists`、`shutil.rmtree`、`_build_latest_versions_override`、`_collect_upload_archives`、`pipeline_upload._upload_archives_and_manifest`、`_patch_pipeline_for_local_live_test`、`_build_parser`、`expanduser`、`upper`、`int`

## 模块 `scripts/test_single_unit_download_unpack_live.py`
- 模块说明：单单位下载与解包链路实测脚本。
- 类数量：0
- 函数/方法数量：3
- 函数索引：`_build_parser`、`_read_data_msgpack`、`main`

### 函数 `_build_parser`

#### `_build_parser() -> ArgumentParser`
- 可见性：内部函数
- 源码位置：`scripts/test_single_unit_download_unpack_live.py:21`
- 作用：（Docstring 未提供）
- 实现方式：
  1. 调用 `ArgumentParser` 并写入 `parser`。
  2. 执行 `parser.add_argument` 触发副作用逻辑。
  3. 执行 `parser.add_argument` 触发副作用逻辑。
  4. 执行 `parser.add_argument` 触发副作用逻辑。
  5. 执行 `parser.add_argument` 触发副作用逻辑。
  6. 执行 `parser.add_argument` 触发副作用逻辑。
  7. 返回 `parser` 作为结果。
- 参数：
参数：无。
- 返回类型：`ArgumentParser`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`ArgumentParser`、`parser.add_argument`

### 函数 `_read_data_msgpack`

#### `_read_data_msgpack(data_file_base: Path) -> dict`
- 可见性：内部函数
- 源码位置：`scripts/test_single_unit_download_unpack_live.py:35`
- 作用：（Docstring 未提供）
- 实现方式：
  1. 调用 `data_file_base.with_suffix` 并写入 `file`。
  2. 根据条件分支选择不同处理路径。
  3. 在上下文管理器中执行资源操作。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `data_file_base` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`data_file_base.with_suffix`、`file.exists`、`FileNotFoundError`、`file.open`、`msgpack.unpackb`、`stream.read`

### 函数 `main`

#### `main() -> int`
- 可见性：公开函数
- 源码位置：`scripts/test_single_unit_download_unpack_live.py:43`
- 作用：（Docstring 未提供）
- 实现方式：
  1. 调用 `parse_args` 并写入 `args`。
  2. 调用 `resolve` 并写入 `work_dir`。
  3. 根据条件分支选择不同处理路径。
  4. 执行 `build_simulated_dir` 触发副作用逻辑。
  5. 调用 `get_latest_versions` 并写入 `latest`。
  6. 调用 `download_game_content_metadata` 并写入 `metadata_file`。
  7. 调用 `download_lcu_data_wads` 并写入 `lcu_wads`。
  8. 调用 `run_data_updater` 并写入 `data_file_base`。
- 参数：
参数：无。
- 返回类型：`int`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`parse_args`、`resolve`、`build_simulated_dir`、`get_latest_versions`、`download_game_content_metadata`、`download_lcu_data_wads`、`run_data_updater`、`_read_data_msgpack`、`data.get`、`champions.get`、`champion.get`、`str`、`download_game_wads_by_runtime_paths`、`run_bin_updater`、`run_unpack_by_entity`、`print`、`work_dir.exists`、`shutil.rmtree`、`isinstance`、`ValueError`

## 模块 `src/rift_audio_pipeline/__init__.py`
- 模块说明：RiftAudioPipeline 包入口。
- 类数量：0
- 函数/方法数量：0

## 模块 `src/rift_audio_pipeline/__main__.py`
- 模块说明：模块执行入口。
- 类数量：0
- 函数/方法数量：0

## 模块 `src/rift_audio_pipeline/asset_downloader.py`
- 模块说明：基于 RiotManifest 的最小游戏环境下载组件。
- 类数量：0
- 函数/方法数量：9
- 函数索引：`download_game_content_metadata`、`download_lcu_data_wads`、`download_game_wads_by_runtime_paths`、`_resolve_manifest_files_by_patterns`、`_resolve_manifest_files_by_exact_paths`、`_download_manifest_files`、`_dedupe_manifest_files`、`_to_game_manifest_path`、`_to_runtime_relative_path`

### 函数 `download_game_content_metadata`

#### `download_game_content_metadata(game_manifest_url: str, download_dir: Path, game_path: Path, concurrency_limit: int = DEFAULT_DOWNLOAD_CONCURRENCY) -> Path`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/asset_downloader.py:22`
- 作用：下载并落地 `content-metadata.json`。
- 实现方式：
  1. 执行 `logger.debug` 触发副作用逻辑。
  2. 调用 `PatcherManifest` 并写入 `manifest`。
  3. 调用 `_resolve_manifest_files_by_exact_paths` 并写入 `selected_files`。
  4. 调用 `_download_manifest_files` 并写入 `downloaded`。
  5. 调用 `stage_runtime_file` 并写入 `staged`。
  6. 执行 `logger.debug` 触发副作用逻辑。
  7. 返回 `staged` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `game_manifest_url` | `str` | `-` | `positional_or_keyword` | GAME manifest URL。 |
| `download_dir` | `Path` | `-` | `positional_or_keyword` | 下载缓存目录。 |
| `game_path` | `Path` | `-` | `positional_or_keyword` | 运行时最小游戏目录。 |
| `concurrency_limit` | `int` | `DEFAULT_DOWNLOAD_CONCURRENCY` | `positional_or_keyword` | 并发下载数。 |
- 返回类型：`Path`
- 返回说明：落地后的目标文件路径。
- 可能抛出：未显式声明。
- 关键调用：`logger.debug`、`PatcherManifest`、`_resolve_manifest_files_by_exact_paths`、`_download_manifest_files`、`stage_runtime_file`、`str`

### 函数 `download_lcu_data_wads`

#### `download_lcu_data_wads(lcu_manifest_url: str, download_dir: Path, game_path: Path, region: str, concurrency_limit: int = DEFAULT_DOWNLOAD_CONCURRENCY) -> tuple[Path, ...]`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/asset_downloader.py:66`
- 作用：下载 DataUpdater 所需 LCU WAD 并落地到最小游戏目录。
- 实现方式：
  1. 执行 `logger.debug` 触发副作用逻辑。
  2. 调用 `PatcherManifest` 并写入 `manifest`。
  3. 调用 `_resolve_manifest_files_by_patterns` 并写入 `selected_files`。
  4. 调用 `_download_manifest_files` 并写入 `downloaded`。
  5. 遍历集合并执行批量处理。
  6. 执行 `logger.debug` 触发副作用逻辑。
  7. 返回 `tuple(staged)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `lcu_manifest_url` | `str` | `-` | `positional_or_keyword` | LCU manifest URL。 |
| `download_dir` | `Path` | `-` | `positional_or_keyword` | 下载缓存目录。 |
| `game_path` | `Path` | `-` | `positional_or_keyword` | 运行时最小游戏目录。 |
| `region` | `str` | `-` | `positional_or_keyword` | 语言区域，例如 `zh_CN`。 |
| `concurrency_limit` | `int` | `DEFAULT_DOWNLOAD_CONCURRENCY` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[Path, ...]`
- 返回说明：落地后的 WAD 路径集合。
- 可能抛出：未显式声明。
- 关键调用：`logger.debug`、`PatcherManifest`、`_resolve_manifest_files_by_patterns`、`_download_manifest_files`、`tuple`、`as_posix`、`_to_runtime_relative_path`、`staged.append`、`len`、`re.escape`、`str`、`stage_runtime_file`、`source.relative_to`

### 函数 `download_game_wads_by_runtime_paths`

#### `download_game_wads_by_runtime_paths(game_manifest_url: str, download_dir: Path, game_path: Path, runtime_wad_paths: Sequence[str], concurrency_limit: int = DEFAULT_DOWNLOAD_CONCURRENCY) -> tuple[Path, ...]`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/asset_downloader.py:120`
- 作用：按运行时路径下载 GAME WAD 并落地到最小游戏目录。
- 实现方式：
  1. 执行 `logger.debug` 触发副作用逻辑。
  2. 调用 `tuple` 并写入 `manifest_paths`。
  3. 调用 `PatcherManifest` 并写入 `manifest`。
  4. 调用 `_resolve_manifest_files_by_exact_paths` 并写入 `selected_files`。
  5. 调用 `_download_manifest_files` 并写入 `downloaded`。
  6. 遍历集合并执行批量处理。
  7. 执行 `logger.debug` 触发副作用逻辑。
  8. 返回 `tuple(staged)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `game_manifest_url` | `str` | `-` | `positional_or_keyword` | GAME manifest URL。 |
| `download_dir` | `Path` | `-` | `positional_or_keyword` | 下载缓存目录。 |
| `game_path` | `Path` | `-` | `positional_or_keyword` | 运行时最小游戏目录。 |
| `runtime_wad_paths` | `Sequence[str]` | `-` | `positional_or_keyword` | 运行时 WAD 路径集合。 |
| `concurrency_limit` | `int` | `DEFAULT_DOWNLOAD_CONCURRENCY` | `positional_or_keyword` | 并发下载数。 |
- 返回类型：`tuple[Path, ...]`
- 返回说明：落地后的 WAD 路径集合。
- 可能抛出：未显式声明。
- 关键调用：`logger.debug`、`tuple`、`PatcherManifest`、`_resolve_manifest_files_by_exact_paths`、`_download_manifest_files`、`len`、`as_posix`、`staged.append`、`_to_game_manifest_path`、`str`、`stage_runtime_file`、`source.relative_to`

### 函数 `_resolve_manifest_files_by_patterns`

#### `_resolve_manifest_files_by_patterns(manifest: PatcherManifest, patterns: Sequence[str]) -> tuple[Any, ...]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/asset_downloader.py:176`
- 作用：按正则模式筛选 manifest 文件。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 返回 `_dedupe_manifest_files(files)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `manifest` | `PatcherManifest` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `patterns` | `Sequence[str]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[Any, ...]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_dedupe_manifest_files`、`files.extend`、`manifest.filter_files`

### 函数 `_resolve_manifest_files_by_exact_paths`

#### `_resolve_manifest_files_by_exact_paths(manifest: PatcherManifest, exact_paths: Sequence[str]) -> tuple[Any, ...]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/asset_downloader.py:188`
- 作用：按精确路径筛选 manifest 文件。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 根据条件分支选择不同处理路径。
  3. 返回 `_dedupe_manifest_files(selected)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `manifest` | `PatcherManifest` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `exact_paths` | `Sequence[str]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[Any, ...]`
- 返回说明：（Docstring 未提供）
- 可能抛出：
  - `FileNotFoundError`
- 关键调用：`_dedupe_manifest_files`、`casefold`、`replace`、`index.get`、`selected.append`、`FileNotFoundError`、`manifest.files.values`、`normalized.casefold`、`missing.append`、`raw_path.strip`、`str`

### 函数 `_download_manifest_files`

#### `_download_manifest_files(manifest: PatcherManifest, files: Sequence[Any], download_dir: Path, concurrency_limit: int) -> tuple[Path, ...]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/asset_downloader.py:220`
- 作用：下载选定文件并返回本地路径。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 执行 `download_dir.mkdir` 触发副作用逻辑。
  3. 调用 `time.perf_counter` 并写入 `started_at`。
  4. 执行 `logger.debug` 触发副作用逻辑。
  5. 调用 `asyncio.run` 并写入 `results`。
  6. 执行 `logger.debug` 触发副作用逻辑。
  7. 根据条件分支选择不同处理路径。
  8. 返回 `tuple(sorted((download_dir / str(file_obj.name).replace('\\', '/') for file_obj in files), key=lambda path: path.as_posix().casefold()))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `manifest` | `PatcherManifest` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `files` | `Sequence[Any]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `download_dir` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `concurrency_limit` | `int` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[Path, ...]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`download_dir.mkdir`、`time.perf_counter`、`logger.debug`、`asyncio.run`、`tuple`、`len`、`manifest.download_files_concurrently`、`str`、`RuntimeError`、`sorted`、`zip`、`list`、`replace`、`casefold`、`path.as_posix`

### 函数 `_dedupe_manifest_files`

#### `_dedupe_manifest_files(files: Iterable[Any]) -> tuple[Any, ...]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/asset_downloader.py:265`
- 作用：按文件名去重并保持稳定顺序。
- 实现方式：
  1. 调用 `set` 并写入 `seen`。
  2. 遍历集合并执行批量处理。
  3. 返回 `tuple(deduped)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `files` | `Iterable[Any]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[Any, ...]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`set`、`tuple`、`replace`、`name.casefold`、`seen.add`、`deduped.append`、`str`、`getattr`

### 函数 `_to_game_manifest_path`

#### `_to_game_manifest_path(runtime_path: str) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/asset_downloader.py:282`
- 作用：将运行时路径转换为 GAME manifest 路径。
- 实现方式：
  1. 调用 `replace` 并写入 `normalized`。
  2. 根据条件分支选择不同处理路径。
  3. 根据条件分支选择不同处理路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `runtime_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`replace`、`normalized.startswith`、`ValueError`、`normalized.removeprefix`、`runtime_path.strip`

### 函数 `_to_runtime_relative_path`

#### `_to_runtime_relative_path(manifest_path: str) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/asset_downloader.py:293`
- 作用：将 manifest 路径映射为最小游戏目录相对路径。
- 实现方式：
  1. 调用 `replace` 并写入 `normalized`。
  2. 根据条件分支选择不同处理路径。
  3. 根据条件分支选择不同处理路径。
  4. 根据条件分支选择不同处理路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `manifest_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`replace`、`normalized.startswith`、`ValueError`、`manifest_path.strip`

## 模块 `src/rift_audio_pipeline/audio_processor.py`
- 模块说明：语音解包编排模块。
- 类数量：1
- 函数/方法数量：11
- 类索引：`AudioProcessingTargets`
- 函数索引：`run_data_updater`、`resolve_processing_targets`、`resolve_all_processing_targets`、`resolve_runtime_wad_paths`、`run_bin_updater`、`run_unpack`、`run_unpack_by_entity`、`_initialize_unpack_config`、`_extract_runtime_wad_paths_from_payload`、`_normalize_runtime_wad_path`、`_reset_singleton_instance`

### 类 `AudioProcessingTargets`
- 可见性：公开类
- 源码位置：`src/rift_audio_pipeline/audio_processor.py:16`
- 作用：需要处理的目标实体集合。
- 装饰器：`dataclass(frozen=True, slots=True)`
- 字段：
| 字段 | 类型 | 默认值 |
| --- | --- | --- |
| `champion_ids` | `tuple[int, ...]` | `-` |
| `map_ids` | `tuple[int, ...]` | `-` |
- 方法数量：0

### 函数 `run_data_updater`

#### `run_data_updater(game_path: Path, output_path: Path, region: str, force_update: bool = False) -> Path`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/audio_processor.py:23`
- 作用：执行 DataUpdater，生成/更新 `data` 文件。
- 实现方式：
  1. 执行 `_initialize_unpack_config` 触发副作用逻辑。
  2. 调用 `DataUpdater` 并写入 `updater`。
  3. 调用 `updater.check_and_update` 并写入 `data_file_base`。
  4. 根据条件分支选择不同处理路径。
  5. 执行 `logger.info` 触发副作用逻辑。
  6. 返回 `data_file_base` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `game_path` | `Path` | `-` | `positional_or_keyword` | 游戏目录。 |
| `output_path` | `Path` | `-` | `positional_or_keyword` | 输出目录。 |
| `region` | `str` | `-` | `positional_or_keyword` | 语言区域。 |
| `force_update` | `bool` | `False` | `positional_or_keyword` | 是否忽略版本检查强制更新。 |
- 返回类型：`Path`
- 返回说明：`data` 文件基础路径（不带后缀）。
- 可能抛出：未显式声明。
- 关键调用：`_initialize_unpack_config`、`DataUpdater`、`updater.check_and_update`、`logger.info`、`isinstance`、`RuntimeError`

### 函数 `resolve_processing_targets`

#### `resolve_processing_targets(data_file_base: Path, champion_aliases: Sequence[str], map_ids: Sequence[str]) -> AudioProcessingTargets`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/audio_processor.py:52`
- 作用：将 manifest 维度目标转换为 `BinUpdater/解包` 所需 ID。
- 实现方式：
  1. 调用 `read_data` 并写入 `payload`。
  2. 调用 `payload.get` 并写入 `champions_raw`。
  3. 调用 `set` 并写入 `champion_ids`。
  4. 遍历集合并执行批量处理。
  5. 调用 `set` 并写入 `normalized_map_ids`。
  6. 遍历集合并执行批量处理。
  7. 返回 `AudioProcessingTargets(champion_ids=tuple(sorted(champion_ids)), map_ids=tuple(sorted(normalized_map_ids)))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `data_file_base` | `Path` | `-` | `positional_or_keyword` | `data` 文件基础路径（不带后缀）。 |
| `champion_aliases` | `Sequence[str]` | `-` | `positional_or_keyword` | 英雄别名集合。 |
| `map_ids` | `Sequence[str]` | `-` | `positional_or_keyword` | 地图 ID 集合（字符串）。 |
- 返回类型：`AudioProcessingTargets`
- 返回说明：规范化后的目标 ID 集合；当为空时表示执行全量处理。
- 可能抛出：未显式声明。
- 关键调用：`read_data`、`payload.get`、`set`、`champions_raw.items`、`AudioProcessingTargets`、`item.casefold`、`casefold`、`isinstance`、`normalized_map_ids.add`、`tuple`、`str`、`champion_ids.add`、`int`、`logger.warning`、`sorted`、`champion_data.get`

### 函数 `resolve_all_processing_targets`

#### `resolve_all_processing_targets(data_file_base: Path) -> AudioProcessingTargets`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/audio_processor.py:98`
- 作用：从 `data` 文件提取全量英雄/地图 ID。
- 实现方式：
  1. 调用 `read_data` 并写入 `payload`。
  2. 调用 `payload.get` 并写入 `champions_raw`。
  3. 调用 `payload.get` 并写入 `maps_raw`。
  4. 调用 `sorted` 并写入 `champion_ids`。
  5. 调用 `sorted` 并写入 `map_ids`。
  6. 返回 `AudioProcessingTargets(champion_ids=tuple(champion_ids), map_ids=tuple(map_ids))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `data_file_base` | `Path` | `-` | `positional_or_keyword` | `data` 文件基础路径（不带后缀）。 |
- 返回类型：`AudioProcessingTargets`
- 返回说明：全量目标 ID 集合。
- 可能抛出：未显式声明。
- 关键调用：`read_data`、`payload.get`、`sorted`、`AudioProcessingTargets`、`int`、`tuple`、`isdigit`、`str`

### 函数 `resolve_runtime_wad_paths`

#### `resolve_runtime_wad_paths(data_file_base: Path, region: str, champion_ids: Sequence[int], map_ids: Sequence[int], include_root_wad: bool = True) -> tuple[str, ...]`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/audio_processor.py:124`
- 作用：从 `data` 文件解析目标实体对应的运行时 WAD 路径。
- 实现方式：
  1. 调用 `read_data` 并写入 `payload`。
  2. 调用 `payload.get` 并写入 `champions_raw`。
  3. 调用 `payload.get` 并写入 `maps_raw`。
  4. 根据条件分支选择不同处理路径。
  5. 根据条件分支选择不同处理路径。
  6. 返回 `tuple(sorted(runtime_paths.values(), key=str.casefold))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `data_file_base` | `Path` | `-` | `positional_or_keyword` | `data` 文件基础路径（不带后缀）。 |
| `region` | `str` | `-` | `positional_or_keyword` | 语言区域（例如 `zh_CN`）。 |
| `champion_ids` | `Sequence[int]` | `-` | `positional_or_keyword` | 英雄 ID 集合。 |
| `map_ids` | `Sequence[int]` | `-` | `positional_or_keyword` | 地图 ID 集合。 |
| `include_root_wad` | `bool` | `True` | `positional_or_keyword` | 是否包含 `wad.root` 路径。 |
- 返回类型：`tuple[str, ...]`
- 返回说明：去重并排序后的运行时 WAD 路径集合。
- 可能抛出：未显式声明。
- 关键调用：`read_data`、`payload.get`、`isinstance`、`tuple`、`str`、`champions_raw.items`、`maps_raw.items`、`sorted`、`_extract_runtime_wad_paths_from_payload`、`runtime_paths.values`、`runtime_paths.setdefault`、`path.casefold`

### 函数 `run_bin_updater`

#### `run_bin_updater(champion_ids: tuple[int, ...], map_ids: tuple[int, ...], force_update: bool = False, process_events: bool = False) -> None`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/audio_processor.py:187`
- 作用：执行 BinUpdater。
- 实现方式：
  1. 调用 `BinUpdater` 并写入 `updater`。
  2. 根据条件分支选择不同处理路径。
  3. 执行 `updater.update` 触发副作用逻辑。
  4. 执行 `logger.info` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `champion_ids` | `tuple[int, ...]` | `-` | `positional_or_keyword` | 英雄 ID 列表；为空时表示全量。 |
| `map_ids` | `tuple[int, ...]` | `-` | `positional_or_keyword` | 地图 ID 列表；为空时表示全量。 |
| `force_update` | `bool` | `False` | `positional_or_keyword` | 是否忽略版本检查强制更新。 |
| `process_events` | `bool` | `False` | `positional_or_keyword` | 是否处理 events 数据。语音资源场景默认关闭以降低耗时。 |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`BinUpdater`、`updater.update`、`logger.info`、`list`、`str`

### 函数 `run_unpack`

#### `run_unpack(champion_ids: tuple[int, ...], map_ids: tuple[int, ...], max_workers: int = DEFAULT_UNPACK_MAX_WORKERS) -> None`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/audio_processor.py:222`
- 作用：执行语音解包。
- 实现方式：
  1. 执行 `_reset_singleton_instance` 触发副作用逻辑。
  2. 调用 `DataReader` 并写入 `reader`。
  3. 根据条件分支选择不同处理路径。
  4. 执行 `reader.write_unknown_categories_to_file` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `champion_ids` | `tuple[int, ...]` | `-` | `positional_or_keyword` | 英雄 ID 列表；为空时表示全量。 |
| `map_ids` | `tuple[int, ...]` | `-` | `positional_or_keyword` | 地图 ID 列表；为空时表示全量。 |
| `max_workers` | `int` | `DEFAULT_UNPACK_MAX_WORKERS` | `positional_or_keyword` | 并发线程数。 |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_reset_singleton_instance`、`DataReader`、`reader.write_unknown_categories_to_file`、`logger.info`、`unpack_audio_all`、`unpack_champions`、`unpack_maps`、`list`

### 函数 `run_unpack_by_entity`

#### `run_unpack_by_entity(champion_ids: tuple[int, ...], map_ids: tuple[int, ...], max_workers: int = DEFAULT_UNPACK_MAX_WORKERS) -> None`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/audio_processor.py:266`
- 作用：按实体顺序执行解包，降低峰值磁盘占用。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 遍历集合并执行批量处理。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `champion_ids` | `tuple[int, ...]` | `-` | `positional_or_keyword` | 英雄 ID 列表。 |
| `map_ids` | `tuple[int, ...]` | `-` | `positional_or_keyword` | 地图 ID 列表。 |
| `max_workers` | `int` | `DEFAULT_UNPACK_MAX_WORKERS` | `positional_or_keyword` | 每次实体解包的并发线程数。 |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`run_unpack`、`tuple`

### 函数 `_initialize_unpack_config`

#### `_initialize_unpack_config(game_path: Path, output_path: Path, region: str) -> None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/audio_processor.py:293`
- 作用：初始化 `lol_audio_unpack` 配置。
- 实现方式：
  1. 执行 `unpack_config.initialize` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `game_path` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `output_path` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `region` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`unpack_config.initialize`

### 函数 `_extract_runtime_wad_paths_from_payload`

#### `_extract_runtime_wad_paths_from_payload(payload_item: object, region: str, include_root_wad: bool) -> tuple[str, ...]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/audio_processor.py:309`
- 作用：从 `data` 条目提取根 WAD 与区域 WAD 运行时路径。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 调用 `payload_item.get` 并写入 `wad_raw`。
  3. 根据条件分支选择不同处理路径。
  4. 根据条件分支选择不同处理路径。
  5. 遍历集合并执行批量处理。
  6. 返回 `tuple(sorted(normalized.values(), key=str.casefold))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `payload_item` | `object` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `region` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `include_root_wad` | `bool` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[str, ...]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`payload_item.get`、`tuple`、`isinstance`、`wad_raw.get`、`candidates.insert`、`_normalize_runtime_wad_path`、`normalized.setdefault`、`sorted`、`path.casefold`、`normalized.values`

### 函数 `_normalize_runtime_wad_path`

#### `_normalize_runtime_wad_path(path: str) -> str | None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/audio_processor.py:336`
- 作用：标准化运行时 WAD 路径。
- 实现方式：
  1. 调用 `replace` 并写入 `normalized`。
  2. 根据条件分支选择不同处理路径。
  3. 根据条件分支选择不同处理路径。
  4. 根据条件分支选择不同处理路径。
  5. 返回 `None` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str | None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`replace`、`normalized.startswith`、`path.strip`

### 函数 `_reset_singleton_instance`

#### `_reset_singleton_instance(target_cls: type[object]) -> None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/audio_processor.py:349`
- 作用：重置下游库单例对象，避免同进程多次运行时复用旧状态。
- 实现方式：
  1. 执行 `Singleton._instances.pop` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `target_cls` | `type[object]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`Singleton._instances.pop`

## 模块 `src/rift_audio_pipeline/baidu/__init__.py`
- 模块说明：百度网盘内部封装包。
- 类数量：0
- 函数/方法数量：0

## 模块 `src/rift_audio_pipeline/baidu/cli.py`
- 模块说明：百度 OAuth 本地调试命令行。
- 类数量：0
- 函数/方法数量：7
- 函数索引：`build_parser`、`main`、`_add_common_credential_args`、`_handle_auth_url`、`_handle_exchange_code`、`_handle_refresh_token`、`_handle_show_token`

### 函数 `build_parser`

#### `build_parser() -> argparse.ArgumentParser`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/baidu/cli.py:18`
- 作用：构建 OAuth 调试 CLI。
- 实现方式：
  1. 调用 `argparse.ArgumentParser` 并写入 `parser`。
  2. 调用 `parser.add_subparsers` 并写入 `subparsers`。
  3. 调用 `subparsers.add_parser` 并写入 `auth_url_parser`。
  4. 执行 `_add_common_credential_args` 触发副作用逻辑。
  5. 执行 `auth_url_parser.add_argument` 触发副作用逻辑。
  6. 执行 `auth_url_parser.add_argument` 触发副作用逻辑。
  7. 执行 `auth_url_parser.add_argument` 触发副作用逻辑。
  8. 执行 `auth_url_parser.set_defaults` 触发副作用逻辑。
- 参数：
参数：无。
- 返回类型：`argparse.ArgumentParser`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`argparse.ArgumentParser`、`parser.add_subparsers`、`subparsers.add_parser`、`_add_common_credential_args`、`auth_url_parser.add_argument`、`auth_url_parser.set_defaults`、`exchange_parser.add_argument`、`exchange_parser.set_defaults`、`refresh_parser.add_argument`、`refresh_parser.set_defaults`、`show_token_parser.add_argument`、`show_token_parser.set_defaults`、`str`

### 函数 `main`

#### `main() -> int`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/baidu/cli.py:79`
- 作用：CLI 主函数。
- 实现方式：
  1. 调用 `build_parser` 并写入 `parser`。
  2. 调用 `parser.parse_args` 并写入 `args`。
  3. 返回 `int(handler(args))` 作为结果。
- 参数：
参数：无。
- 返回类型：`int`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`build_parser`、`parser.parse_args`、`int`、`handler`

### 函数 `_add_common_credential_args`

#### `_add_common_credential_args(parser: argparse.ArgumentParser) -> None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/baidu/cli.py:88`
- 作用：为命令添加凭据参数。
- 实现方式：
  1. 执行 `parser.add_argument` 触发副作用逻辑。
  2. 执行 `parser.add_argument` 触发副作用逻辑。
  3. 执行 `parser.add_argument` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `parser` | `argparse.ArgumentParser` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`parser.add_argument`、`str`

### 函数 `_handle_auth_url`

#### `_handle_auth_url(args: argparse.Namespace) -> int`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/baidu/cli.py:100`
- 作用：处理 auth-url 命令。
- 实现方式：
  1. 调用 `load_baidu_app_credentials` 并写入 `credentials`。
  2. 在上下文管理器中执行资源操作。
  3. 执行 `print` 触发副作用逻辑。
  4. 执行 `print` 触发副作用逻辑。
  5. 返回 `0` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `args` | `argparse.Namespace` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`int`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`load_baidu_app_credentials`、`print`、`BaiduOAuthClient`、`client.build_authorization_url`、`Path`

### 函数 `_handle_exchange_code`

#### `_handle_exchange_code(args: argparse.Namespace) -> int`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/baidu/cli.py:120`
- 作用：处理 exchange-code 命令。
- 实现方式：
  1. 调用 `load_baidu_app_credentials` 并写入 `credentials`。
  2. 调用 `resolve_token_store` 并写入 `token_store`。
  3. 在上下文管理器中执行资源操作。
  4. 执行 `token_store.save_token` 触发副作用逻辑。
  5. 执行 `print` 触发副作用逻辑。
  6. 执行 `print` 触发副作用逻辑。
  7. 执行 `print` 触发副作用逻辑。
  8. 执行 `print` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `args` | `argparse.Namespace` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`int`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`load_baidu_app_credentials`、`resolve_token_store`、`token_store.save_token`、`print`、`BaiduOAuthClient`、`client.exchange_code_for_token`、`Path`、`mask_secret`

### 函数 `_handle_refresh_token`

#### `_handle_refresh_token(args: argparse.Namespace) -> int`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/baidu/cli.py:143`
- 作用：处理 refresh-token 命令。
- 实现方式：
  1. 调用 `load_baidu_app_credentials` 并写入 `credentials`。
  2. 调用 `resolve_token_store` 并写入 `token_store`。
  3. 根据条件分支选择不同处理路径。
  4. 在上下文管理器中执行资源操作。
  5. 执行 `token_store.save_token` 触发副作用逻辑。
  6. 执行 `print` 触发副作用逻辑。
  7. 执行 `print` 触发副作用逻辑。
  8. 执行 `print` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `args` | `argparse.Namespace` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`int`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`load_baidu_app_credentials`、`resolve_token_store`、`token_store.save_token`、`print`、`BaiduOAuthClient`、`client.refresh_access_token`、`Path`、`token_store.load_token`、`mask_secret`

### 函数 `_handle_show_token`

#### `_handle_show_token(args: argparse.Namespace) -> int`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/baidu/cli.py:169`
- 作用：处理 show-token 命令。
- 实现方式：
  1. 调用 `resolve_token_store` 并写入 `token_store`。
  2. 调用 `token_store.load_token` 并写入 `token`。
  3. 执行 `print` 触发副作用逻辑。
  4. 执行 `print` 触发副作用逻辑。
  5. 执行 `print` 触发副作用逻辑。
  6. 执行 `print` 触发副作用逻辑。
  7. 执行 `print` 触发副作用逻辑。
  8. 执行 `print` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `args` | `argparse.Namespace` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`int`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`resolve_token_store`、`token_store.load_token`、`print`、`Path`、`mask_secret`

## 模块 `src/rift_audio_pipeline/baidu/oauth.py`
- 模块说明：百度 OAuth 授权与本地 token 管理。
- 类数量：5
- 函数/方法数量：27
- 类索引：`BaiduOAuthError`、`BaiduAppCredentials`、`BaiduOAuthToken`、`LocalBaiduTokenStore`、`BaiduOAuthClient`
- 函数索引：`load_baidu_app_credentials`、`resolve_token_store`、`mask_secret`、`_load_kv_file`、`_payload_to_dict`、`_extract_api_exception_message`、`_as_non_empty_str`、`_normalize_config_value`、`_to_utc_iso`、`_parse_utc_iso`

### 类 `BaiduOAuthError`
- 可见性：公开类
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:28`
- 作用：百度 OAuth 请求异常。
- 方法数量：1

### 函数 `__init__`

#### `__init__(self, message: str, error_code: str | None = None) -> None`
- 可见性：内部方法
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:31`
- 作用：初始化异常对象。
- 实现方式：
  1. 执行 `__init__` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `message` | `str` | `-` | `positional_or_keyword` | 异常描述信息。 |
| `error_code` | `str | None` | `None` | `positional_or_keyword` | 百度接口返回的错误码。 |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`__init__`、`super`

### 类 `BaiduAppCredentials`
- 可见性：公开类
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:44`
- 作用：百度开放平台应用凭据。
- 装饰器：`dataclass(frozen=True, slots=True)`
- 字段：
| 字段 | 类型 | 默认值 |
| --- | --- | --- |
| `app_key` | `str` | `-` |
| `secret_key` | `str` | `-` |
- 方法数量：0

### 类 `BaiduOAuthToken`
- 可见性：公开类
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:52`
- 作用：百度 OAuth token 数据。
- 装饰器：`dataclass(frozen=True, slots=True)`
- 字段：
| 字段 | 类型 | 默认值 |
| --- | --- | --- |
| `access_token` | `str` | `-` |
| `refresh_token` | `str` | `-` |
| `expires_in` | `int` | `-` |
| `scope` | `str` | `-` |
| `session_key` | `str | None` | `-` |
| `session_secret` | `str | None` | `-` |
| `obtained_at` | `str` | `-` |
- 方法数量：4

### 函数 `expires_at`

#### `expires_at(self) -> str`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:64`
- 作用：返回过期时间（UTC ISO8601）。
- 实现方式：
  1. 调用 `_parse_utc_iso` 并写入 `obtained_at`。
  2. 返回 `_to_utc_iso(obtained_at + timedelta(seconds=self.expires_in))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_parse_utc_iso`、`_to_utc_iso`、`timedelta`

### 函数 `from_payload`

#### `from_payload(cls, payload: Mapping[str, Any], fallback_refresh_token: str | None = None) -> BaiduOAuthToken`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:71`
- 作用：从百度接口响应构建 token。
- 实现方式：
  1. 调用 `_as_non_empty_str` 并写入 `access_token`。
  2. 调用 `payload.get` 并写入 `expires_in_value`。
  3. 调用 `_as_non_empty_str` 并写入 `session_key`。
  4. 调用 `_as_non_empty_str` 并写入 `session_secret`。
  5. 根据条件分支选择不同处理路径。
  6. 根据条件分支选择不同处理路径。
  7. 根据条件分支选择不同处理路径。
  8. 返回 `cls(access_token=access_token, refresh_token=refresh_token, expires_in=expires_in_value, scope=scope, session_key=session_key, session_secret=session_secret, obtained_at=_to_utc_iso(datetime.now(tz=timezone.utc)))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `cls` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `payload` | `Mapping[str, Any]` | `-` | `positional_or_keyword` | 接口响应字典。 |
| `fallback_refresh_token` | `str | None` | `None` | `positional_or_keyword` | 刷新接口未返回新 refresh_token 时的回退值。 |
- 返回类型：`BaiduOAuthToken`
- 返回说明：标准化后的 token 对象。
- 可能抛出：
  - `BaiduOAuthError`
- 关键调用：`_as_non_empty_str`、`payload.get`、`cls`、`BaiduOAuthError`、`isinstance`、`_to_utc_iso`、`datetime.now`

### 函数 `from_dict`

#### `from_dict(cls, data: Mapping[str, Any]) -> BaiduOAuthToken`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:116`
- 作用：从本地 JSON 反序列化 token。
- 实现方式：
  1. 返回 `cls(access_token=str(data['access_token']), refresh_token=str(data['refresh_token']), expires_in=int(data['expires_in']), scope=str(data.get('scope', '')), session_key=_as_non_empty_str(data.get('session_key')), session_secret=_as_non_empty_str(data.get('session_secret')), obtained_at=str(data['obtained_at']))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `cls` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `data` | `Mapping[str, Any]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`BaiduOAuthToken`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`cls`、`str`、`int`、`_as_non_empty_str`、`data.get`

### 函数 `to_dict`

#### `to_dict(self) -> dict[str, Any]`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:129`
- 作用：序列化 token 到 JSON 字典。
- 实现方式：
  1. 返回 `dict(asdict(self))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`dict`、`asdict`

### 类 `LocalBaiduTokenStore`
- 可见性：公开类
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:135`
- 作用：本地 token 文件存储。
- 方法数量：4

### 函数 `__init__`

#### `__init__(self, token_file: Path) -> None`
- 可见性：内部方法
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:138`
- 作用：初始化 token 存储。
- 实现方式：
  1. 执行函数体中的顺序逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `token_file` | `Path` | `-` | `positional_or_keyword` | token 文件完整路径。 |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：未识别到显式函数调用。

### 函数 `token_file`

#### `token_file(self) -> Path`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:148`
- 作用：返回 token 文件路径。
- 实现方式：
  1. 返回 `self._token_file` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`Path`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：未识别到显式函数调用。

### 函数 `load_token`

#### `load_token(self) -> BaiduOAuthToken`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:153`
- 作用：读取本地 token。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 调用 `self._token_file.read_text` 并写入 `raw_text`。
  3. 调用 `json.loads` 并写入 `data`。
  4. 根据条件分支选择不同处理路径。
  5. 返回 `BaiduOAuthToken.from_dict(data=data)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`BaiduOAuthToken`
- 返回说明：解析后的 token 对象。
- 可能抛出：
  - `FileNotFoundError`
  - `ValueError`
- 关键调用：`self._token_file.read_text`、`json.loads`、`BaiduOAuthToken.from_dict`、`self._token_file.exists`、`FileNotFoundError`、`isinstance`、`ValueError`

### 函数 `save_token`

#### `save_token(self, token: BaiduOAuthToken) -> None`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:172`
- 作用：写入本地 token。
- 实现方式：
  1. 执行 `self._token_file.parent.mkdir` 触发副作用逻辑。
  2. 调用 `json.dumps` 并写入 `serialized`。
  3. 执行 `self._token_file.write_text` 触发副作用逻辑。
  4. 根据条件分支选择不同处理路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `token` | `BaiduOAuthToken` | `-` | `positional_or_keyword` | 需持久化的 token 对象。 |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self._token_file.parent.mkdir`、`json.dumps`、`self._token_file.write_text`、`token.to_dict`、`os.chmod`

### 类 `BaiduOAuthClient`
- 可见性：公开类
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:186`
- 作用：百度 OAuth 客户端（官方 SDK AuthApi 适配）。
- 方法数量：8

### 函数 `__init__`

#### `__init__(self, timeout: float = 30.0) -> None`
- 可见性：内部方法
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:189`
- 作用：初始化客户端。
- 实现方式：
  1. 执行 `ensure_official_sdk_path` 触发副作用逻辑。
  2. 调用 `load_openapi_client_module` 并写入 `_openapi_client`。
  3. 调用 `self._openapi_client.ApiClient` 并写入 `_api_client`。
  4. 调用 `importlib.import_module` 并写入 `auth_api_module`。
  5. 调用 `importlib.import_module` 并写入 `exception_module`。
  6. 调用 `auth_api_module.AuthApi` 并写入 `_auth_api`。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `timeout` | `float` | `30.0` | `positional_or_keyword` | 接口请求超时（秒）。 |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`ensure_official_sdk_path`、`load_openapi_client_module`、`self._openapi_client.ApiClient`、`importlib.import_module`、`auth_api_module.AuthApi`

### 函数 `__enter__`

#### `__enter__(self) -> BaiduOAuthClient`
- 可见性：内部方法
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:206`
- 作用：（Docstring 未提供）
- 实现方式：
  1. 返回 `self` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`BaiduOAuthClient`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：未识别到显式函数调用。

### 函数 `__exit__`

#### `__exit__(self, exc_type: type[BaseException], exc: BaseException, tb: Any) -> None`
- 可见性：内部方法
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:209`
- 作用：（Docstring 未提供）
- 实现方式：
  1. 执行 `self.close` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `exc_type` | `type[BaseException]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `exc` | `BaseException` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `tb` | `Any` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self.close`

### 函数 `close`

#### `close(self) -> None`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:212`
- 作用：关闭连接池。
- 实现方式：
  1. 执行 `self._api_client.close` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self._api_client.close`

### 函数 `build_authorization_url`

#### `build_authorization_url(self, app_key: str, scope: str = DEFAULT_BAIDU_SCOPE, redirect_uri: str = DEFAULT_BAIDU_REDIRECT_URI, state: str | None = None) -> str`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:217`
- 作用：生成授权码模式 URL。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 返回 `f'{BAIDU_OAUTH_AUTHORIZE_URL}?{urlencode(params)}'` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `app_key` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `scope` | `str` | `DEFAULT_BAIDU_SCOPE` | `positional_or_keyword` | （Docstring 未提供） |
| `redirect_uri` | `str` | `DEFAULT_BAIDU_REDIRECT_URI` | `positional_or_keyword` | （Docstring 未提供） |
| `state` | `str | None` | `None` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`urlencode`

### 函数 `exchange_code_for_token`

#### `exchange_code_for_token(self, code: str, credentials: BaiduAppCredentials, redirect_uri: str = DEFAULT_BAIDU_REDIRECT_URI) -> BaiduOAuthToken`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:236`
- 作用：使用授权码换取 token。
- 实现方式：
  1. 调用 `self._invoke_auth_api` 并写入 `payload`。
  2. 返回 `BaiduOAuthToken.from_payload(payload=payload, fallback_refresh_token=None)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `code` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `credentials` | `BaiduAppCredentials` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `redirect_uri` | `str` | `DEFAULT_BAIDU_REDIRECT_URI` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`BaiduOAuthToken`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self._invoke_auth_api`、`BaiduOAuthToken.from_payload`、`self._auth_api.oauth_token_code2token`

### 函数 `refresh_access_token`

#### `refresh_access_token(self, refresh_token: str, credentials: BaiduAppCredentials) -> BaiduOAuthToken`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:256`
- 作用：使用 refresh_token 刷新 access_token。
- 实现方式：
  1. 调用 `self._invoke_auth_api` 并写入 `payload`。
  2. 返回 `BaiduOAuthToken.from_payload(payload=payload, fallback_refresh_token=refresh_token)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `refresh_token` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `credentials` | `BaiduAppCredentials` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`BaiduOAuthToken`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self._invoke_auth_api`、`BaiduOAuthToken.from_payload`、`self._auth_api.oauth_token_refresh_token`

### 函数 `_invoke_auth_api`

#### `_invoke_auth_api(self, action: Any, operation: str) -> dict[str, Any]`
- 可见性：内部方法
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:277`
- 作用：执行官方 AuthApi 调用并统一处理错误。
- 实现方式：
  1. 使用异常处理分支兜底失败路径。
  2. 调用 `_payload_to_dict` 并写入 `payload`。
  3. 调用 `_as_non_empty_str` 并写入 `error_code`。
  4. 根据条件分支选择不同处理路径。
  5. 返回 `payload` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `action` | `Any` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `operation` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_payload_to_dict`、`_as_non_empty_str`、`action`、`payload.get`、`BaiduOAuthError`、`_extract_api_exception_message`

### 函数 `load_baidu_app_credentials`

#### `load_baidu_app_credentials(app_key: str | None, secret_key: str | None, dev_config_file: Path = DEFAULT_BAIDU_DEV_CONFIG_FILE) -> BaiduAppCredentials`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:298`
- 作用：加载应用凭据，优先级为参数 > 环境变量 > `.dev.baidu`。
- 实现方式：
  1. 调用 `_load_kv_file` 并写入 `file_values`。
  2. 根据条件分支选择不同处理路径。
  3. 根据条件分支选择不同处理路径。
  4. 根据条件分支选择不同处理路径。
  5. 根据条件分支选择不同处理路径。
  6. 返回 `BaiduAppCredentials(app_key=resolved_app_key, secret_key=resolved_secret_key)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `app_key` | `str | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `secret_key` | `str | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `dev_config_file` | `Path` | `DEFAULT_BAIDU_DEV_CONFIG_FILE` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`BaiduAppCredentials`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_load_kv_file`、`BaiduAppCredentials`、`_as_non_empty_str`、`ValueError`、`os.getenv`、`file_values.get`

### 函数 `resolve_token_store`

#### `resolve_token_store(token_file: Path = DEFAULT_BAIDU_TOKEN_FILE) -> LocalBaiduTokenStore`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:322`
- 作用：创建 token 存储对象。
- 实现方式：
  1. 返回 `LocalBaiduTokenStore(token_file=token_file.expanduser().resolve())` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `token_file` | `Path` | `DEFAULT_BAIDU_TOKEN_FILE` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`LocalBaiduTokenStore`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`LocalBaiduTokenStore`、`resolve`、`token_file.expanduser`

### 函数 `mask_secret`

#### `mask_secret(value: str) -> str`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:328`
- 作用：对敏感字段做脱敏显示。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 返回 `f'{value[:6]}...{value[-4:]}'` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `value` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`len`

### 函数 `_load_kv_file`

#### `_load_kv_file(path: Path) -> dict[str, str]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:336`
- 作用：读取简单 `key=value` 配置文件。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 遍历集合并执行批量处理。
  3. 返回 `result` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `path` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, str]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`splitlines`、`path.exists`、`line.strip`、`stripped.split`、`_normalize_config_value`、`path.read_text`、`stripped.startswith`、`key.strip`、`raw_value.strip`

### 函数 `_payload_to_dict`

#### `_payload_to_dict(payload: Any) -> dict[str, Any]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:351`
- 作用：将 SDK 响应统一转换为字典。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 调用 `getattr` 并写入 `to_dict`。
  3. 根据条件分支选择不同处理路径。
  4. 调用 `getattr` 并写入 `attribute_map`。
  5. 根据条件分支选择不同处理路径。
  6. 根据条件分支选择不同处理路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `payload` | `Any` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`isinstance`、`getattr`、`callable`、`BaiduOAuthError`、`to_dict`、`dict`、`type`

### 函数 `_extract_api_exception_message`

#### `_extract_api_exception_message(error: Exception) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:374`
- 作用：提取官方 SDK 异常可读信息。
- 实现方式：
  1. 调用 `getattr` 并写入 `reason`。
  2. 调用 `getattr` 并写入 `body`。
  3. 调用 `getattr` 并写入 `status`。
  4. 返回 `f'status={status}, reason={reason}, body={body}'` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `error` | `Exception` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`getattr`

### 函数 `_as_non_empty_str`

#### `_as_non_empty_str(value: object) -> str | None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:383`
- 作用：将对象安全转换为非空字符串。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 返回 `None` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `value` | `object` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str | None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`isinstance`、`value.strip`

### 函数 `_normalize_config_value`

#### `_normalize_config_value(value: str) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:392`
- 作用：标准化配置值，去除包裹引号。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 返回 `value` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `value` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`strip`、`len`

### 函数 `_to_utc_iso`

#### `_to_utc_iso(value: datetime) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:400`
- 作用：将时间转换为 UTC ISO8601 字符串。
- 实现方式：
  1. 返回 `value.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `value` | `datetime` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`replace`、`isoformat`、`value.astimezone`

### 函数 `_parse_utc_iso`

#### `_parse_utc_iso(value: str) -> datetime`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/baidu/oauth.py:406`
- 作用：解析 UTC ISO8601 字符串。
- 实现方式：
  1. 返回 `datetime.fromisoformat(value.replace('Z', '+00:00'))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `value` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`datetime`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`datetime.fromisoformat`、`value.replace`

## 模块 `src/rift_audio_pipeline/baidu/pan.py`
- 模块说明：基于官方 openapi_client 的百度网盘 API 封装。
- 类数量：4
- 函数/方法数量：32
- 类索引：`BaiduCredentials`、`BaiduPanApiError`、`BaiduPanScopeWarning`、`BaiduPanClient`
- 函数索引：`_payload_to_dict`、`_extract_api_exception_message`、`_normalize_remote_path`、`_calculate_block_md5s`、`_token_not_expired`、`_as_int`、`_as_non_empty_str`

### 类 `BaiduCredentials`
- 可见性：公开类
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:34`
- 作用：百度开放平台凭据。
- 装饰器：`dataclass(frozen=True, slots=True)`
- 字段：
| 字段 | 类型 | 默认值 |
| --- | --- | --- |
| `app_key` | `str` | `-` |
| `secret_key` | `str` | `-` |
| `refresh_token` | `str` | `-` |
- 方法数量：0

### 类 `BaiduPanApiError`
- 可见性：公开类
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:42`
- 作用：百度网盘 API 请求异常。
- 方法数量：1

### 函数 `__init__`

#### `__init__(self, message: str, errno: int | None = None, payload: Mapping[str, Any] | None = None) -> None`
- 可见性：内部方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:45`
- 作用：初始化异常对象。
- 实现方式：
  1. 执行 `__init__` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `message` | `str` | `-` | `positional_or_keyword` | 异常信息。 |
| `errno` | `int | None` | `None` | `positional_or_keyword` | 接口返回错误码。 |
| `payload` | `Mapping[str, Any] | None` | `None` | `positional_or_keyword` | 原始响应数据。 |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`__init__`、`super`

### 类 `BaiduPanScopeWarning`
- 可见性：公开类
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:64`
- 作用：百度网盘工作目录边界告警。
- 方法数量：0

### 类 `BaiduPanClient`
- 可见性：公开类
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:68`
- 作用：百度网盘客户端（官方 SDK 适配层）。
- 方法数量：24

### 函数 `__init__`

#### `__init__(self, credentials: BaiduCredentials, remote_dir: str, token_store: LocalBaiduTokenStore | None = None) -> None`
- 可见性：内部方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:71`
- 作用：初始化客户端。
- 实现方式：
  1. 调用 `_normalize_remote_path` 并写入 `_remote_dir`。
  2. 调用 `credentials.refresh_token.strip` 并写入 `_refresh_token`。
  3. 根据条件分支选择不同处理路径。
  4. 根据条件分支选择不同处理路径。
  5. 执行 `ensure_official_sdk_path` 触发副作用逻辑。
  6. 调用 `load_openapi_client_module` 并写入 `_openapi_client`。
  7. 调用 `self._openapi_client.ApiClient` 并写入 `_api_client`。
  8. 调用 `importlib.import_module` 并写入 `fileinfo_api_module`。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `credentials` | `BaiduCredentials` | `-` | `positional_or_keyword` | 百度开放平台凭据。 |
| `remote_dir` | `str` | `-` | `positional_or_keyword` | 网盘工作目录。 |
| `token_store` | `LocalBaiduTokenStore | None` | `None` | `positional_or_keyword` | 本地 token 存储（可选）。 |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：
  - `ValueError`
- 关键调用：`_normalize_remote_path`、`credentials.refresh_token.strip`、`ensure_official_sdk_path`、`load_openapi_client_module`、`self._openapi_client.ApiClient`、`importlib.import_module`、`fileinfo_api_module.FileinfoApi`、`filemanager_api_module.FilemanagerApi`、`fileupload_api_module.FileuploadApi`、`multimedia_api_module.MultimediafileApi`、`userinfo_api_module.UserinfoApi`、`ValueError`、`token_store.load_token`

### 函数 `remote_dir`

#### `remote_dir(self) -> str`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:125`
- 作用：返回默认网盘工作目录。
- 实现方式：
  1. 返回 `self._remote_dir` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：未识别到显式函数调用。

### 函数 `current_refresh_token`

#### `current_refresh_token(self) -> str`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:131`
- 作用：返回当前 refresh token。
- 实现方式：
  1. 返回 `self._refresh_token` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：未识别到显式函数调用。

### 函数 `close`

#### `close(self) -> None`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:136`
- 作用：关闭内部连接池。
- 实现方式：
  1. 执行 `self._api_client.close` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self._api_client.close`

### 函数 `refresh_access_token`

#### `refresh_access_token(self) -> str`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:141`
- 作用：刷新 access token 并返回最新值。
- 实现方式：
  1. 调用 `BaiduAppCredentials` 并写入 `app_credentials`。
  2. 在上下文管理器中执行资源操作。
  3. 根据条件分支选择不同处理路径。
  4. 返回 `token.access_token` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`BaiduAppCredentials`、`BaiduOAuthClient`、`oauth_client.refresh_access_token`、`self._token_store.save_token`

### 函数 `get_quota`

#### `get_quota(self) -> dict[str, Any]`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:160`
- 作用：获取网盘容量信息。
- 实现方式：
  1. 调用 `self._ensure_access_token` 并写入 `access_token`。
  2. 调用 `self._invoke_sdk` 并写入 `payload`。
  3. 执行 `payload.setdefault` 触发副作用逻辑。
  4. 返回 `payload` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self._ensure_access_token`、`self._invoke_sdk`、`payload.setdefault`、`_as_int`、`max`、`self._userinfo_api.apiquota`、`payload.get`

### 函数 `list_files`

#### `list_files(self, dir_path: str, limit: int = 1000, start: int = 0) -> dict[str, Any]`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:173`
- 作用：列出目录文件。
- 实现方式：
  1. 调用 `self._ensure_access_token` 并写入 `access_token`。
  2. 调用 `self._resolve_workdir_path` 并写入 `normalized_dir`。
  3. 返回 `self._invoke_sdk(lambda: self._fileinfo_api.xpanfilelist(access_token, dir=normalized_dir, folder='0', start=str(start), limit=limit, order='name', desc=0, web='1', showempty=1), operation='xpanfilelist')` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `dir_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `limit` | `int` | `1000` | `positional_or_keyword` | （Docstring 未提供） |
| `start` | `int` | `0` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self._ensure_access_token`、`self._resolve_workdir_path`、`self._invoke_sdk`、`self._fileinfo_api.xpanfilelist`、`str`

### 函数 `create_directory`

#### `create_directory(self, dir_path: str) -> dict[str, Any]`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:197`
- 作用：创建目录。
- 实现方式：
  1. 调用 `self._ensure_access_token` 并写入 `access_token`。
  2. 调用 `self._resolve_workdir_path` 并写入 `normalized_dir`。
  3. 返回 `self._invoke_sdk(lambda: self._fileupload_api.xpanfilecreate(access_token, normalized_dir, 1, 0, '', '[]', rtype=3), operation='xpanfilecreate(isdir=1)')` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `dir_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self._ensure_access_token`、`self._resolve_workdir_path`、`self._invoke_sdk`、`self._fileupload_api.xpanfilecreate`

### 函数 `rename_path`

#### `rename_path(self, source_path: str, new_name: str, ondup: str = 'newcopy') -> dict[str, Any]`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:219`
- 作用：重命名文件或目录。
- 实现方式：
  1. 返回 `self._filemanager_operation(opera='rename', filelist=payload, ondup=ondup)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `source_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `new_name` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `ondup` | `str` | `'newcopy'` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self._filemanager_operation`、`self._resolve_workdir_path`

### 函数 `copy_path`

#### `copy_path(self, source_path: str, destination_dir: str, new_name: str | None = None, ondup: str = 'newcopy') -> dict[str, Any]`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:236`
- 作用：复制文件或目录。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 返回 `self._filemanager_operation(opera='copy', filelist=[file_payload], ondup=ondup)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `source_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `destination_dir` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `new_name` | `str | None` | `None` | `positional_or_keyword` | （Docstring 未提供） |
| `ondup` | `str` | `'newcopy'` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self._filemanager_operation`、`self._resolve_workdir_path`

### 函数 `move_path`

#### `move_path(self, source_path: str, destination_dir: str, new_name: str | None = None, ondup: str = 'newcopy') -> dict[str, Any]`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:261`
- 作用：移动文件或目录。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 返回 `self._filemanager_operation(opera='move', filelist=[file_payload], ondup=ondup)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `source_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `destination_dir` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `new_name` | `str | None` | `None` | `positional_or_keyword` | （Docstring 未提供） |
| `ondup` | `str` | `'newcopy'` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self._filemanager_operation`、`self._resolve_workdir_path`

### 函数 `delete_path`

#### `delete_path(self, target_path: str) -> dict[str, Any]`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:287`
- 作用：删除单个路径。
- 实现方式：
  1. 返回 `self.delete_paths(paths=[target_path])` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `target_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self.delete_paths`

### 函数 `delete_paths`

#### `delete_paths(self, paths: Iterable[str]) -> dict[str, Any]`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:292`
- 作用：批量删除路径。
- 实现方式：
  1. 返回 `self._filemanager_operation(opera='delete', filelist=filelist, ondup=None)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `paths` | `Iterable[str]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self._filemanager_operation`、`self._resolve_workdir_path`

### 函数 `upload_file`

#### `upload_file(self, local_path: Path, remote_path: str, rtype: int = 3) -> dict[str, Any]`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:307`
- 作用：上传单个文件（precreate -> superfile2 -> create）。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `self._ensure_access_token` 并写入 `access_token`。
  4. 调用 `self._resolve_workdir_path` 并写入 `normalized_remote_path`。
  5. 调用 `_calculate_block_md5s` 并写入 `block_md5s`。
  6. 调用 `json.dumps` 并写入 `block_list_json`。
  7. 调用 `self._invoke_sdk` 并写入 `precreate_payload`。
  8. 调用 `_as_non_empty_str` 并写入 `upload_id`。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `local_path` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `rtype` | `int` | `3` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self._ensure_access_token`、`self._resolve_workdir_path`、`_calculate_block_md5s`、`json.dumps`、`self._invoke_sdk`、`_as_non_empty_str`、`local_path.exists`、`FileNotFoundError`、`local_path.is_file`、`ValueError`、`local_path.stat`、`precreate_payload.get`、`BaiduPanApiError`、`local_path.open`、`enumerate`、`self._fileupload_api.xpanfileprecreate`、`file_obj.read`、`io.BytesIO`、`self._fileupload_api.xpanfilecreate`、`part_payload.get`

### 函数 `get_file_version_info`

#### `get_file_version_info(self, remote_path: str) -> dict[str, Any]`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:389`
- 作用：获取文件版本信息（含 dlink、md5、mtime 等）。
- 实现方式：
  1. 调用 `self.get_path_entry` 并写入 `entry`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `_as_int` 并写入 `fs_id`。
  4. 根据条件分支选择不同处理路径。
  5. 调用 `self._ensure_access_token` 并写入 `access_token`。
  6. 调用 `self._invoke_sdk` 并写入 `metas_payload`。
  7. 调用 `metas_payload.get` 并写入 `meta_list`。
  8. 根据条件分支选择不同处理路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self.get_path_entry`、`_as_int`、`self._ensure_access_token`、`self._invoke_sdk`、`metas_payload.get`、`merged.update`、`isinstance`、`IsADirectoryError`、`entry.get`、`BaiduPanApiError`、`self._multimedia_api.xpanmultimediafilemetas`、`json.dumps`

### 函数 `download_file`

#### `download_file(self, remote_path: str, local_path: Path) -> dict[str, Any]`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:427`
- 作用：下载单个文件到本地。
- 实现方式：
  1. 调用 `self._resolve_workdir_path` 并写入 `normalized_path`。
  2. 调用 `self.get_file_version_info` 并写入 `version_info`。
  3. 调用 `self._ensure_access_token` 并写入 `access_token`。
  4. 执行 `local_path.parent.mkdir` 触发副作用逻辑。
  5. 调用 `local_path.with_suffix` 并写入 `temp_path`。
  6. 遍历集合并执行批量处理。
  7. 返回 `version_info` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `local_path` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self._resolve_workdir_path`、`self.get_file_version_info`、`self._ensure_access_token`、`local_path.parent.mkdir`、`local_path.with_suffix`、`range`、`self._invoke_sdk_call_api`、`temp_path.replace`、`temp_path.open`、`temp_path.exists`、`raw_response.release_conn`、`raw_response.read`、`file_obj.write`、`temp_path.unlink`、`BaiduPanApiError`

### 函数 `get_path_entry`

#### `get_path_entry(self, remote_path: str) -> dict[str, Any]`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:471`
- 作用：查询单一路径条目。
- 实现方式：
  1. 调用 `self._resolve_workdir_path` 并写入 `normalized_path`。
  2. 根据条件分支选择不同处理路径。
  3. 根据条件分支选择不同处理路径。
  4. 调用 `PurePosixPath` 并写入 `path_obj`。
  5. 使用异常处理分支兜底失败路径。
  6. 遍历集合并执行批量处理。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self._resolve_workdir_path`、`PurePosixPath`、`listing.get`、`FileNotFoundError`、`str`、`self.list_files`、`isinstance`、`entry.get`

### 函数 `_filemanager_operation`

#### `_filemanager_operation(self, opera: str, filelist: list[dict[str, Any]], ondup: str | None) -> dict[str, Any]`
- 可见性：内部方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:497`
- 作用：执行 filemanager 操作。
- 实现方式：
  1. 调用 `self._ensure_access_token` 并写入 `access_token`。
  2. 调用 `json.dumps` 并写入 `filelist_json`。
  3. 根据条件分支选择不同处理路径。
  4. 根据条件分支选择不同处理路径。
  5. 根据条件分支选择不同处理路径。
  6. 根据条件分支选择不同处理路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `opera` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `filelist` | `list[dict[str, Any]]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `ondup` | `str | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self._ensure_access_token`、`json.dumps`、`ValueError`、`self._invoke_sdk`、`self._filemanager_api.filemanagercopy`、`self._filemanager_api.filemanagermove`、`self._filemanager_api.filemanagerrename`、`self._filemanager_api.filemanagerdelete`

### 函数 `_invoke_sdk`

#### `_invoke_sdk(self, action: Callable[[], Any], operation: str) -> dict[str, Any]`
- 可见性：内部方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:549`
- 作用：执行官方 SDK 调用并统一转换响应。
- 实现方式：
  1. 使用异常处理分支兜底失败路径。
  2. 调用 `_payload_to_dict` 并写入 `payload`。
  3. 调用 `_as_int` 并写入 `errno`。
  4. 根据条件分支选择不同处理路径。
  5. 返回 `payload` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `action` | `Callable[[], Any]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `operation` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_payload_to_dict`、`_as_int`、`action`、`payload.get`、`BaiduPanApiError`、`_extract_api_exception_message`

### 函数 `_invoke_sdk_call_api`

#### `_invoke_sdk_call_api(self, access_token: str, remote_path: str) -> Any`
- 可见性：内部方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:568`
- 作用：通过官方 ApiClient.call_api 下载文件流。
- 实现方式：
  1. 使用异常处理分支兜底失败路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `access_token` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`Any`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self._api_client.call_api`、`BaiduPanApiError`、`_extract_api_exception_message`

### 函数 `_ensure_access_token`

#### `_ensure_access_token(self) -> str`
- 可见性：内部方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:591`
- 作用：确保存在可用 access token。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 返回 `self.refresh_access_token()` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`self.refresh_access_token`、`_token_not_expired`

### 函数 `_resolve_workdir_path`

#### `_resolve_workdir_path(self, raw_path: str, operation: str, path_role: str, allow_outside: bool = False) -> str`
- 可见性：内部方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:598`
- 作用：解析并校验网盘路径是否在工作目录范围内。
- 实现方式：
  1. 调用 `self._resolve_remote_path` 并写入 `normalized_path`。
  2. 根据条件分支选择不同处理路径。
  3. 根据条件分支选择不同处理路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `raw_path` | `str` | `-` | `positional_or_keyword` | 用户输入的路径。 |
| `operation` | `str` | `-` | `positional_or_keyword` | 当前操作名。 |
| `path_role` | `str` | `-` | `positional_or_keyword` | 路径语义（如 source_path、destination_dir）。 |
| `allow_outside` | `bool` | `False` | `positional_or_keyword` | 是否允许越界路径（允许时仅告警）。 |
- 返回类型：`str`
- 返回说明：标准化后的绝对网盘路径。
- 可能抛出：
  - `ValueError`
- 关键调用：`self._resolve_remote_path`、`self._is_under_remote_dir`、`ValueError`、`warnings.warn`

### 函数 `_resolve_remote_path`

#### `_resolve_remote_path(self, raw_path: str) -> str`
- 可见性：内部方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:635`
- 作用：将原始路径解析为绝对网盘路径。
- 实现方式：
  1. 调用 `raw_path.strip` 并写入 `stripped`。
  2. 根据条件分支选择不同处理路径。
  3. 根据条件分支选择不同处理路径。
  4. 根据条件分支选择不同处理路径。
  5. 返回 `_normalize_remote_path(f'{self._remote_dir}/{stripped}')` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `raw_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`raw_path.strip`、`stripped.startswith`、`_normalize_remote_path`

### 函数 `_is_under_remote_dir`

#### `_is_under_remote_dir(self, path: str) -> bool`
- 可见性：内部方法
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:647`
- 作用：判断路径是否落在工作目录内。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 调用 `PurePosixPath` 并写入 `work_dir_obj`。
  3. 调用 `PurePosixPath` 并写入 `path_obj`。
  4. 返回 `path_obj == work_dir_obj or work_dir_obj in path_obj.parents` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`bool`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`PurePosixPath`

### 函数 `_payload_to_dict`

#### `_payload_to_dict(payload: Any) -> dict[str, Any]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:657`
- 作用：将 SDK 响应统一转换为字典。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 调用 `getattr` 并写入 `to_dict`。
  3. 根据条件分支选择不同处理路径。
  4. 调用 `getattr` 并写入 `attribute_map`。
  5. 根据条件分支选择不同处理路径。
  6. 根据条件分支选择不同处理路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `payload` | `Any` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`isinstance`、`getattr`、`callable`、`BaiduPanApiError`、`to_dict`、`dict`、`type`

### 函数 `_extract_api_exception_message`

#### `_extract_api_exception_message(error: Exception) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:680`
- 作用：提取官方 SDK 异常可读信息。
- 实现方式：
  1. 调用 `getattr` 并写入 `reason`。
  2. 调用 `getattr` 并写入 `body`。
  3. 调用 `getattr` 并写入 `status`。
  4. 返回 `f'status={status}, reason={reason}, body={body}'` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `error` | `Exception` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`getattr`

### 函数 `_normalize_remote_path`

#### `_normalize_remote_path(path: str) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:689`
- 作用：规范化网盘路径。
- 实现方式：
  1. 调用 `path.strip` 并写入 `stripped`。
  2. 根据条件分支选择不同处理路径。
  3. 根据条件分支选择不同处理路径。
  4. 调用 `posixpath.normpath` 并写入 `normalized`。
  5. 根据条件分支选择不同处理路径。
  6. 根据条件分支选择不同处理路径。
  7. 返回 `normalized` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`path.strip`、`posixpath.normpath`、`stripped.startswith`、`normalized.startswith`

### 函数 `_calculate_block_md5s`

#### `_calculate_block_md5s(local_path: Path) -> list[str]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:705`
- 作用：计算文件分片 MD5 列表。
- 实现方式：
  1. 在上下文管理器中执行资源操作。
  2. 根据条件分支选择不同处理路径。
  3. 返回 `block_md5s` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `local_path` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`list[str]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`local_path.open`、`block_md5s.append`、`file_obj.read`、`hexdigest`、`hashlib.md5`

### 函数 `_token_not_expired`

#### `_token_not_expired(token: BaiduOAuthToken) -> bool`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:720`
- 作用：判断 token 在安全窗口内是否仍有效。
- 实现方式：
  1. 调用 `datetime.fromisoformat` 并写入 `expires_at`。
  2. 调用 `datetime.now` 并写入 `now`。
  3. 返回 `expires_at.timestamp() - now.timestamp() > TOKEN_EXPIRY_SAFETY_SECONDS` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `token` | `BaiduOAuthToken` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`bool`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`datetime.fromisoformat`、`datetime.now`、`token.expires_at.replace`、`expires_at.timestamp`、`now.timestamp`

### 函数 `_as_int`

#### `_as_int(value: object) -> int | None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:728`
- 作用：将对象安全转换为整数。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 根据条件分支选择不同处理路径。
  3. 根据条件分支选择不同处理路径。
  4. 返回 `None` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `value` | `object` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`int | None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`isinstance`、`int`、`value.strip`

### 函数 `_as_non_empty_str`

#### `_as_non_empty_str(value: object) -> str | None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/baidu/pan.py:746`
- 作用：将对象安全转换为非空字符串。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 返回 `None` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `value` | `object` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str | None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`isinstance`、`value.strip`

## 模块 `src/rift_audio_pipeline/baidu/sdk.py`
- 模块说明：百度官方 SDK 加载工具。
- 类数量：0
- 函数/方法数量：2
- 函数索引：`ensure_official_sdk_path`、`load_openapi_client_module`

### 函数 `ensure_official_sdk_path`

#### `ensure_official_sdk_path() -> Path`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/baidu/sdk.py:14`
- 作用：确保官方 SDK 目录在 `sys.path` 中。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 调用 `str` 并写入 `sdk_path_text`。
  3. 根据条件分支选择不同处理路径。
  4. 返回 `OFFICIAL_BAIDU_SDK_DIR` 作为结果。
- 参数：
参数：无。
- 返回类型：`Path`
- 返回说明：官方 SDK 根目录路径。
- 可能抛出：
  - `FileNotFoundError`
- 关键调用：`str`、`OFFICIAL_BAIDU_SDK_DIR.exists`、`FileNotFoundError`、`sys.path.insert`

### 函数 `load_openapi_client_module`

#### `load_openapi_client_module() -> ModuleType`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/baidu/sdk.py:32`
- 作用：动态加载官方 `openapi_client` 模块。
- 实现方式：
  1. 执行 `ensure_official_sdk_path` 触发副作用逻辑。
  2. 返回 `importlib.import_module('openapi_client')` 作为结果。
- 参数：
参数：无。
- 返回类型：`ModuleType`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`ensure_official_sdk_path`、`importlib.import_module`

## 模块 `src/rift_audio_pipeline/bin_extractor.py`
- 模块说明：bin 提取与本地标志管理。
- 类数量：0
- 函数/方法数量：7
- 函数索引：`write_to_bin_input`、`create_local_bin_flag`、`write_many_to_bin_input`、`seed_bin_input_from_directory`、`_normalize_relative_bin_path`、`extract_champion_bins`、`extract_map_bins`

### 函数 `write_to_bin_input`

#### `write_to_bin_input(version_dir: Path, relative_path: str, content: bytes) -> Path`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/bin_extractor.py:11`
- 作用：将 bin 原始数据写入 `bin_input` 目录。
- 实现方式：
  1. 调用 `_normalize_relative_bin_path` 并写入 `normalized_path`。
  2. 执行 `target_file.parent.mkdir` 触发副作用逻辑。
  3. 执行 `target_file.write_bytes` 触发副作用逻辑。
  4. 返回 `target_file` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `version_dir` | `Path` | `-` | `positional_or_keyword` | 版本目录路径。 |
| `relative_path` | `str` | `-` | `positional_or_keyword` | bin 文件相对路径。 |
| `content` | `bytes` | `-` | `positional_or_keyword` | 二进制内容。 |
- 返回类型：`Path`
- 返回说明：写入后的文件路径。
- 可能抛出：
  - `ValueError`
- 关键调用：`_normalize_relative_bin_path`、`target_file.parent.mkdir`、`target_file.write_bytes`

### 函数 `create_local_bin_flag`

#### `create_local_bin_flag(version_dir: Path) -> Path`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/bin_extractor.py:33`
- 作用：创建 local_bin 标志文件。
- 实现方式：
  1. 执行 `flag_file.touch` 触发副作用逻辑。
  2. 返回 `flag_file` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `version_dir` | `Path` | `-` | `positional_or_keyword` | 版本目录路径。 |
- 返回类型：`Path`
- 返回说明：标志文件路径。
- 可能抛出：未显式声明。
- 关键调用：`flag_file.touch`

### 函数 `write_many_to_bin_input`

#### `write_many_to_bin_input(version_dir: Path, bin_payloads: Mapping[str, bytes], enable_local_bin: bool = True) -> tuple[Path, ...]`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/bin_extractor.py:48`
- 作用：批量写入 bin 数据到 `bin_input` 目录。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 返回 `tuple(written_files)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `version_dir` | `Path` | `-` | `positional_or_keyword` | 版本目录路径。 |
| `bin_payloads` | `Mapping[str, bytes]` | `-` | `positional_or_keyword` | 以相对路径为 key、二进制内容为 value 的映射。 |
| `enable_local_bin` | `bool` | `True` | `positional_or_keyword` | 是否在写入后创建 `.use_local_bin` 标志。 |
- 返回类型：`tuple[Path, ...]`
- 返回说明：已写入文件路径集合（按路径排序）。
- 可能抛出：未显式声明。
- 关键调用：`tuple`、`write_to_bin_input`、`create_local_bin_flag`、`sorted`、`bin_payloads.items`、`casefold`

### 函数 `seed_bin_input_from_directory`

#### `seed_bin_input_from_directory(version_dir: Path, source_dir: Path, enable_local_bin: bool = True) -> tuple[Path, ...]`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/bin_extractor.py:73`
- 作用：从本地目录导入 bin 文件到 `bin_input`。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 遍历集合并执行批量处理。
  3. 返回 `write_many_to_bin_input(version_dir=version_dir, bin_payloads=payloads, enable_local_bin=enable_local_bin)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `version_dir` | `Path` | `-` | `positional_or_keyword` | 版本目录路径。 |
| `source_dir` | `Path` | `-` | `positional_or_keyword` | 本地 bin 根目录。 |
| `enable_local_bin` | `bool` | `True` | `positional_or_keyword` | 是否在导入后创建 `.use_local_bin` 标志。 |
- 返回类型：`tuple[Path, ...]`
- 返回说明：已写入文件路径集合（按路径排序）。
- 可能抛出：
  - `FileNotFoundError`
- 关键调用：`sorted`、`write_many_to_bin_input`、`source_dir.is_dir`、`FileNotFoundError`、`source_dir.rglob`、`as_posix`、`item.read_bytes`、`item.is_file`、`item.suffix.casefold`、`casefold`、`item.relative_to`、`path.as_posix`

### 函数 `_normalize_relative_bin_path`

#### `_normalize_relative_bin_path(relative_path: str) -> Path`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/bin_extractor.py:114`
- 作用：规范化相对路径并阻止越界。
- 实现方式：
  1. 调用 `replace` 并写入 `raw`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `Path` 并写入 `path`。
  4. 根据条件分支选择不同处理路径。
  5. 调用 `Path` 并写入 `normalized`。
  6. 根据条件分支选择不同处理路径。
  7. 根据条件分支选择不同处理路径。
  8. 返回 `normalized` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `relative_path` | `str` | `-` | `positional_or_keyword` | 输入相对路径。 |
- 返回类型：`Path`
- 返回说明：规范化后的相对路径对象。
- 可能抛出：
  - `ValueError`
- 关键调用：`replace`、`Path`、`path.is_absolute`、`any`、`ValueError`、`relative_path.strip`

### 函数 `extract_champion_bins`

#### `extract_champion_bins(alias: str, manifest_url: str) -> None`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/bin_extractor.py:143`
- 作用：预留：按英雄 alias 在线提取 bin。
- 实现方式：
  1. 执行函数体中的顺序逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `alias` | `str` | `-` | `positional_or_keyword` | 英雄别名。 |
| `manifest_url` | `str` | `-` | `positional_or_keyword` | 当前版本 manifest URL。 |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：
  - `NotImplementedError`
- 关键调用：`NotImplementedError`

### 函数 `extract_map_bins`

#### `extract_map_bins(map_id: str, manifest_url: str) -> None`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/bin_extractor.py:157`
- 作用：预留：按地图 ID 在线提取 bin。
- 实现方式：
  1. 执行函数体中的顺序逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `map_id` | `str` | `-` | `positional_or_keyword` | 地图 ID。 |
| `manifest_url` | `str` | `-` | `positional_or_keyword` | 当前版本 manifest URL。 |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：
  - `NotImplementedError`
- 关键调用：`NotImplementedError`

## 模块 `src/rift_audio_pipeline/cli.py`
- 模块说明：命令行入口。
- 类数量：0
- 函数/方法数量：2
- 函数索引：`build_parser`、`main`

### 函数 `build_parser`

#### `build_parser() -> argparse.ArgumentParser`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/cli.py:12`
- 作用：构建命令行解析器。
- 实现方式：
  1. 调用 `argparse.ArgumentParser` 并写入 `parser`。
  2. 执行 `parser.add_argument` 触发副作用逻辑。
  3. 执行 `parser.add_argument` 触发副作用逻辑。
  4. 执行 `parser.add_argument` 触发副作用逻辑。
  5. 执行 `parser.add_argument` 触发副作用逻辑。
  6. 执行 `parser.add_argument` 触发副作用逻辑。
  7. 执行 `parser.add_argument` 触发副作用逻辑。
  8. 执行 `parser.add_argument` 触发副作用逻辑。
- 参数：
参数：无。
- 返回类型：`argparse.ArgumentParser`
- 返回说明：配置完成的参数解析器。
- 可能抛出：未显式声明。
- 关键调用：`argparse.ArgumentParser`、`parser.add_argument`

### 函数 `main`

#### `main() -> int`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/cli.py:122`
- 作用：命令行主函数。
- 实现方式：
  1. 调用 `build_parser` 并写入 `parser`。
  2. 调用 `parser.parse_args` 并写入 `args`。
  3. 调用 `PipelineConfig.from_namespace` 并写入 `config`。
  4. 返回 `run_pipeline(config=config)` 作为结果。
- 参数：
参数：无。
- 返回类型：`int`
- 返回说明：退出状态码，`0` 表示执行成功。
- 可能抛出：未显式声明。
- 关键调用：`build_parser`、`parser.parse_args`、`PipelineConfig.from_namespace`、`run_pipeline`

## 模块 `src/rift_audio_pipeline/config.py`
- 模块说明：项目配置管理。
- 类数量：1
- 函数/方法数量：1
- 类索引：`PipelineConfig`

### 类 `PipelineConfig`
- 可见性：公开类
- 源码位置：`src/rift_audio_pipeline/config.py:20`
- 作用：流水线运行配置。
- 装饰器：`dataclass(frozen=True, slots=True)`
- 字段：
| 字段 | 类型 | 默认值 |
| --- | --- | --- |
| `output_path` | `Path` | `-` |
| `game_region` | `str` | `DEFAULT_GAME_REGION` |
| `game_path` | `Path | None` | `None` |
| `lcu_download_mode` | `str` | `DEFAULT_LCU_DOWNLOAD_MODE` |
| `audio_types` | `tuple[str, ...]` | `DEFAULT_AUDIO_TYPES` |
| `temp_dir` | `Path | None` | `None` |
| `baidu_pan_remote_dir` | `str` | `DEFAULT_BAIDU_PAN_REMOTE_DIR` |
| `baidu_pan_app_key` | `str | None` | `None` |
| `baidu_pan_secret_key` | `str | None` | `None` |
| `baidu_pan_refresh_token` | `str | None` | `None` |
| `local_bin_dir` | `Path | None` | `None` |
| `download_concurrency` | `int` | `4` |
| `diff_bin_filter_workers` | `int` | `DEFAULT_DIFF_BIN_FILTER_WORKERS` |
| `diff_bin_extract_concurrency` | `int` | `DEFAULT_DIFF_BIN_EXTRACT_CONCURRENCY` |
| `diff_bin_filter_threshold` | `int` | `DEFAULT_DIFF_BIN_FILTER_THRESHOLD` |
| `unpack_workers` | `int` | `2` |
| `low_disk_mode` | `bool` | `True` |
| `enable_pack` | `bool` | `False` |
| `pack_output_dir` | `Path | None` | `None` |
| `pack_password` | `str | None` | `None` |
| `pack_encrypt_filenames` | `bool` | `True` |
| `pack_extra_dir` | `Path | None` | `None` |
| `enable_upload` | `bool` | `False` |
| `dry_run` | `bool` | `False` |
- 方法数量：1

### 函数 `from_namespace`

#### `from_namespace(cls, args: Namespace) -> PipelineConfig`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/config.py:79`
- 作用：从 CLI 参数和环境变量构建配置。
- 实现方式：
  1. 调用 `os.getenv` 并写入 `env_app_key`。
  2. 调用 `os.getenv` 并写入 `env_secret_key`。
  3. 调用 `os.getenv` 并写入 `env_refresh_token`。
  4. 调用 `resolve` 并写入 `output_path`。
  5. 调用 `max` 并写入 `unpack_workers`。
  6. 调用 `max` 并写入 `download_concurrency`。
  7. 调用 `max` 并写入 `diff_bin_filter_workers`。
  8. 调用 `max` 并写入 `diff_bin_extract_concurrency`。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `cls` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `args` | `Namespace` | `-` | `positional_or_keyword` | `argparse` 解析得到的参数对象。 |
- 返回类型：`PipelineConfig`
- 返回说明：完整的流水线配置对象。
- 可能抛出：未显式声明。
- 关键调用：`os.getenv`、`resolve`、`max`、`int`、`cls`、`expanduser`、`tuple`、`bool`、`Path`

## 模块 `src/rift_audio_pipeline/game_dir_builder.py`
- 模块说明：游戏目录检测与模拟目录构建。
- 类数量：0
- 函数/方法数量：9
- 函数索引：`check_local_game_path`、`build_simulated_dir`、`write_content_metadata`、`stage_wad_file`、`stage_runtime_file`、`cleanup_updater_inputs`、`cleanup_lcu_data_wads`、`_normalize_relative_game_path`、`check_disk_space`

### 函数 `check_local_game_path`

#### `check_local_game_path(game_path: Path) -> bool`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/game_dir_builder.py:11`
- 作用：检查本地游戏目录是否满足最低资源条件。
- 实现方式：
  1. 返回 `all((path.exists() for path in required_dirs))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `game_path` | `Path` | `-` | `positional_or_keyword` | 游戏根目录路径，通常包含 `Game` 与 `LeagueClient` 子目录。 |
- 返回类型：`bool`
- 返回说明：若关键目录存在返回 `True`，否则返回 `False`。
- 可能抛出：未显式声明。
- 关键调用：`all`、`path.exists`

### 函数 `build_simulated_dir`

#### `build_simulated_dir(base_dir: Path) -> Path`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/game_dir_builder.py:28`
- 作用：构建在线模式所需的最小游戏目录结构。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 返回 `base_dir` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `base_dir` | `Path` | `-` | `positional_or_keyword` | 模拟目录根路径。 |
- 返回类型：`Path`
- 返回说明：已创建完成的模拟目录路径。
- 可能抛出：未显式声明。
- 关键调用：`directory.mkdir`

### 函数 `write_content_metadata`

#### `write_content_metadata(game_path: Path, version: str) -> Path`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/game_dir_builder.py:46`
- 作用：写入最小游戏环境所需的 `content-metadata.json`。
- 实现方式：
  1. 执行 `metadata_file.parent.mkdir` 触发副作用逻辑。
  2. 执行 `metadata_file.write_text` 触发副作用逻辑。
  3. 返回 `metadata_file` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `game_path` | `Path` | `-` | `positional_or_keyword` | 游戏根目录路径。 |
| `version` | `str` | `-` | `positional_or_keyword` | 游戏完整版本号（例如 `16.4.7480682`）。 |
- 返回类型：`Path`
- 返回说明：已写入的 metadata 文件路径。
- 可能抛出：未显式声明。
- 关键调用：`metadata_file.parent.mkdir`、`metadata_file.write_text`、`json.dumps`

### 函数 `stage_wad_file`

#### `stage_wad_file(game_path: Path, relative_wad_path: str, source_wad_file: Path, strategy: Literal['hardlink', 'copy'] = 'hardlink') -> Path`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/game_dir_builder.py:69`
- 作用：将 WAD 文件按相对路径落地到最小游戏目录。
- 实现方式：
  1. 返回 `stage_runtime_file(game_path=game_path, relative_path=relative_wad_path, source_file=source_wad_file, strategy=strategy)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `game_path` | `Path` | `-` | `positional_or_keyword` | 游戏根目录路径。 |
| `relative_wad_path` | `str` | `-` | `positional_or_keyword` | 相对于游戏根目录的 WAD 路径。 |
| `source_wad_file` | `Path` | `-` | `positional_or_keyword` | 本地源 WAD 文件路径。 |
| `strategy` | `Literal['hardlink', 'copy']` | `'hardlink'` | `positional_or_keyword` | 写入策略。`hardlink` 失败时会自动回退到复制。 |
- 返回类型：`Path`
- 返回说明：落地后的目标文件路径。
- 可能抛出：
  - `FileNotFoundError`
  - `ValueError`
- 关键调用：`stage_runtime_file`

### 函数 `stage_runtime_file`

#### `stage_runtime_file(game_path: Path, relative_path: str, source_file: Path, strategy: Literal['hardlink', 'copy'] = 'hardlink') -> Path`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/game_dir_builder.py:99`
- 作用：将任意运行时文件按相对路径落地到游戏目录。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 调用 `_normalize_relative_game_path` 并写入 `normalized_path`。
  3. 执行 `target_file.parent.mkdir` 触发副作用逻辑。
  4. 根据条件分支选择不同处理路径。
  5. 根据条件分支选择不同处理路径。
  6. 根据条件分支选择不同处理路径。
  7. 执行 `shutil.copy2` 触发副作用逻辑。
  8. 返回 `target_file` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `game_path` | `Path` | `-` | `positional_or_keyword` | 游戏根目录路径。 |
| `relative_path` | `str` | `-` | `positional_or_keyword` | 相对于游戏根目录的目标路径。 |
| `source_file` | `Path` | `-` | `positional_or_keyword` | 本地源文件路径。 |
| `strategy` | `Literal['hardlink', 'copy']` | `'hardlink'` | `positional_or_keyword` | 写入策略。`hardlink` 失败时自动回退复制。 |
- 返回类型：`Path`
- 返回说明：落地后的目标文件路径。
- 可能抛出：
  - `FileNotFoundError`
  - `ValueError`
- 关键调用：`_normalize_relative_game_path`、`target_file.parent.mkdir`、`target_file.exists`、`shutil.copy2`、`source_file.is_file`、`FileNotFoundError`、`source_file.resolve`、`target_file.resolve`、`target_file.unlink`、`target_file.hardlink_to`

### 函数 `cleanup_updater_inputs`

#### `cleanup_updater_inputs(game_path: Path, version_dir: Path) -> tuple[int, int]`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/game_dir_builder.py:144`
- 作用：清理 Updater 阶段使用的临时输入数据。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 根据条件分支选择不同处理路径。
  3. 根据条件分支选择不同处理路径。
  4. 返回 `(removed_lcu_wad_count, removed_bin_file_count)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `game_path` | `Path` | `-` | `positional_or_keyword` | 运行时游戏目录。 |
| `version_dir` | `Path` | `-` | `positional_or_keyword` | 当前版本目录（通常为 `output/manifest/<version>`）。 |
- 返回类型：`tuple[int, int]`
- 返回说明：二元组 `(removed_lcu_wad_count, removed_bin_file_count)`。
- 可能抛出：未显式声明。
- 关键调用：`lcu_dir.is_dir`、`bin_input_dir.exists`、`local_bin_flag.exists`、`lcu_dir.glob`、`bin_input_dir.rglob`、`shutil.rmtree`、`local_bin_flag.unlink`、`wad_file.is_file`、`file_path.is_file`、`wad_file.unlink`

### 函数 `cleanup_lcu_data_wads`

#### `cleanup_lcu_data_wads(game_path: Path, region: str) -> int`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/game_dir_builder.py:183`
- 作用：清理 DataUpdater 所需的 LCU WAD 输入文件。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 遍历集合并执行批量处理。
  3. 遍历集合并执行批量处理。
  4. 返回 `removed_count` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `game_path` | `Path` | `-` | `positional_or_keyword` | 运行时游戏目录。 |
| `region` | `str` | `-` | `positional_or_keyword` | 语言区域（例如 `zh_CN`）。 |
- 返回类型：`int`
- 返回说明：已删除文件数。
- 可能抛出：未显式声明。
- 关键调用：`sorted`、`lcu_dir.is_dir`、`lcu_dir.glob`、`targets.values`、`file_path.unlink`、`file_path.is_file`、`casefold`、`file_path.as_posix`、`item.as_posix`

### 函数 `_normalize_relative_game_path`

#### `_normalize_relative_game_path(relative_path: str) -> Path`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/game_dir_builder.py:217`
- 作用：规范化并校验游戏目录内相对路径。
- 实现方式：
  1. 调用 `replace` 并写入 `raw`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `Path` 并写入 `path`。
  4. 根据条件分支选择不同处理路径。
  5. 调用 `Path` 并写入 `normalized`。
  6. 根据条件分支选择不同处理路径。
  7. 根据条件分支选择不同处理路径。
  8. 返回 `normalized` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `relative_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`Path`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`replace`、`Path`、`path.is_absolute`、`any`、`ValueError`、`relative_path.strip`

### 函数 `check_disk_space`

#### `check_disk_space(path: Path, required_bytes: int) -> bool`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/game_dir_builder.py:237`
- 作用：检测磁盘可用空间是否足够。
- 实现方式：
  1. 调用 `shutil.disk_usage` 并写入 `usage`。
  2. 返回 `usage.free >= required_bytes` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `path` | `Path` | `-` | `positional_or_keyword` | 目标目录路径。 |
| `required_bytes` | `int` | `-` | `positional_or_keyword` | 预估所需空间（字节）。 |
- 返回类型：`bool`
- 返回说明：可用空间充足返回 `True`，否则返回 `False`。
- 可能抛出：未显式声明。
- 关键调用：`shutil.disk_usage`

## 模块 `src/rift_audio_pipeline/manifest_ops.py`
- 模块说明：Manifest 获取、版本状态判断与差异分析。
- 类数量：8
- 函数/方法数量：41
- 类索引：`LatestVersions`、`LocalRunState`、`ChangedEntities`、`ManifestWadChanges`、`UpdateDecision`、`VoicePathStatus`、`WadVoiceFilterDecision`、`ManifestVoiceFilterResult`
- 函数索引：`get_latest_versions`、`compare_major_minor`、`get_manifest_wad_changes`、`get_changed_entities`、`extract_changed_entities_from_wad_paths`、`filter_wad_changes_by_bin_voice_paths`、`_prepare_voice_filter_bin_output_dir`、`_write_voice_filter_bin_output_file`、`_normalize_relative_bin_output_path`、`_build_wad_voice_filter_decision`、`_collect_voice_path_statuses`、`_load_wad_header`、`_build_manifest_file_index`、`_extract_existing_bin_raws`、`_collect_voice_paths_from_bin_raws`、`_classify_voice_bank_paths`、`_build_wad_focus_status_index`、`_resolve_inner_path_status`、`_resolve_wad_path_hash`、`_build_candidate_bin_paths`、`_resolve_root_wad_path`、`_normalize_update_paths`、`_group_update_paths_by_root_wad`、`_build_wad_voice_filter_decisions_for_group`、`_normalize_manifest_path`、`_extract_diff_entry_path`、`load_local_state`、`save_local_state`、`build_local_state`、`evaluate_update_need`、`evaluate_update_need_with_latest`、`_extract_changed_entities_from_paths`

### 类 `LatestVersions`
- 可见性：公开类
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:73`
- 作用：最新版本信息。
- 装饰器：`dataclass(frozen=True, slots=True)`
- 字段：
| 字段 | 类型 | 默认值 |
| --- | --- | --- |
| `game_version` | `str` | `-` |
| `game_manifest_url` | `str` | `-` |
| `lcu_version` | `str` | `-` |
| `lcu_manifest_url` | `str` | `-` |
- 方法数量：0

### 类 `LocalRunState`
- 可见性：公开类
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:83`
- 作用：本地历史状态。
- 装饰器：`dataclass(frozen=True, slots=True)`
- 字段：
| 字段 | 类型 | 默认值 |
| --- | --- | --- |
| `schema_version` | `int` | `-` |
| `game_version` | `str` | `-` |
| `game_manifest_url` | `str` | `-` |
| `lcu_version` | `str` | `-` |
| `lcu_manifest_url` | `str` | `-` |
| `checked_at` | `str` | `-` |
- 方法数量：2

### 函数 `from_dict`

#### `from_dict(cls, data: dict[str, Any]) -> LocalRunState`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:94`
- 作用：从字典反序列化状态对象。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 返回 `cls(schema_version=int(data['schema_version']), game_version=str(data['game_version']), game_manifest_url=str(data['game_manifest_url']), lcu_version=str(data['lcu_version']), lcu_manifest_url=str(data['lcu_manifest_url']), checked_at=str(data['checked_at']))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `cls` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `data` | `dict[str, Any]` | `-` | `positional_or_keyword` | JSON 字典。 |
- 返回类型：`LocalRunState`
- 返回说明：状态对象。
- 可能抛出：
  - `ValueError`
- 关键调用：`cls`、`ValueError`、`int`、`str`

### 函数 `to_dict`

#### `to_dict(self) -> dict[str, Any]`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:127`
- 作用：序列化状态对象。
- 实现方式：
  1. 返回 `dict(asdict(self))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`dict`、`asdict`

### 类 `ChangedEntities`
- 可见性：公开类
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:134`
- 作用：变更实体集合。
- 装饰器：`dataclass(frozen=True, slots=True)`
- 字段：
| 字段 | 类型 | 默认值 |
| --- | --- | --- |
| `champion_aliases` | `tuple[str, ...]` | `-` |
| `map_ids` | `tuple[str, ...]` | `-` |
- 方法数量：0

### 类 `ManifestWadChanges`
- 可见性：公开类
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:142`
- 作用：Manifest WAD 路径差异结果。
- 装饰器：`dataclass(frozen=True, slots=True)`
- 字段：
| 字段 | 类型 | 默认值 |
| --- | --- | --- |
| `added_paths` | `tuple[str, ...]` | `-` |
| `changed_paths` | `tuple[str, ...]` | `-` |
| `removed_paths` | `tuple[str, ...]` | `-` |
- 方法数量：1

### 函数 `update_paths`

#### `update_paths(self) -> tuple[str, ...]`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:150`
- 作用：返回需要更新下载的路径集合（added + changed）。
- 实现方式：
  1. 返回 `tuple(sorted(set(self.added_paths + self.changed_paths)))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[str, ...]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`tuple`、`sorted`、`set`

### 类 `UpdateDecision`
- 可见性：公开类
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:157`
- 作用：更新判定结果。
- 装饰器：`dataclass(frozen=True, slots=True)`
- 字段：
| 字段 | 类型 | 默认值 |
| --- | --- | --- |
| `should_update` | `bool` | `-` |
| `reason` | `str` | `-` |
| `latest_versions` | `LatestVersions` | `-` |
| `previous_state` | `LocalRunState | None` | `-` |
| `changed_entities` | `ChangedEntities` | `-` |
| `wad_changes` | `ManifestWadChanges` | `-` |
- 方法数量：0

### 类 `VoicePathStatus`
- 可见性：公开类
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:169`
- 作用：单个语音资源路径的旧新版本差异状态。
- 装饰器：`dataclass(frozen=True, slots=True)`
- 字段：
| 字段 | 类型 | 默认值 |
| --- | --- | --- |
| `path` | `str` | `-` |
| `status` | `VoicePathDiffStatus` | `-` |
| `path_type` | `str` | `-` |
- 方法数量：2

### 函数 `from_dict`

#### `from_dict(cls, data: Mapping[str, Any]) -> VoicePathStatus`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:177`
- 作用：从字典反序列化路径状态。
- 实现方式：
  1. 返回 `cls(path=str(data.get('path', '')), status=str(data.get('status', 'missing')), path_type=str(data.get('path_type', '')))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `cls` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `data` | `Mapping[str, Any]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`VoicePathStatus`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`cls`、`str`、`data.get`

### 函数 `to_dict`

#### `to_dict(self) -> dict[str, Any]`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:186`
- 作用：序列化为字典。
- 实现方式：
  1. 返回 `dict(asdict(self))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`dict`、`asdict`

### 类 `WadVoiceFilterDecision`
- 可见性：公开类
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:193`
- 作用：单个 WAD 的二次筛选判定结果。
- 装饰器：`dataclass(frozen=True, slots=True)`
- 字段：
| 字段 | 类型 | 默认值 |
| --- | --- | --- |
| `region_wad_path` | `str` | `-` |
| `root_wad_path` | `str | None` | `-` |
| `entity_type` | `str` | `-` |
| `matched_bin_paths` | `tuple[str, ...]` | `-` |
| `audio_paths` | `tuple[str, ...]` | `-` |
| `event_paths` | `tuple[str, ...]` | `-` |
| `path_statuses` | `tuple[VoicePathStatus, ...]` | `-` |
| `changed_audio_paths` | `tuple[str, ...]` | `-` |
| `changed_event_paths` | `tuple[str, ...]` | `-` |
| `should_unpack` | `bool` | `-` |
| `skip_reason` | `str | None` | `-` |
- 方法数量：2

### 函数 `from_dict`

#### `from_dict(cls, data: Mapping[str, Any]) -> WadVoiceFilterDecision`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:209`
- 作用：从字典反序列化单个 WAD 判定结果。
- 实现方式：
  1. 调用 `data.get` 并写入 `path_statuses_raw`。
  2. 调用 `tuple` 并写入 `path_statuses`。
  3. 返回 `cls(region_wad_path=str(data.get('region_wad_path', '')), root_wad_path=str(data.get('root_wad_path')) if data.get('root_wad_path') is not None else None, entity_type=str(data.get('entity_type', '')), matched_bin_paths=tuple((str(item) for item in data.get('matched_bin_paths', tuple()))), audio_paths=tuple((str(item) for item in data.get('audio_paths', tuple()))), event_paths=tuple((str(item) for item in data.get('event_paths', tuple()))), path_statuses=path_statuses, changed_audio_paths=tuple((str(item) for item in data.get('changed_audio_paths', tuple()))), changed_event_paths=tuple((str(item) for item in data.get('changed_event_paths', tuple()))), should_unpack=bool(data.get('should_unpack', False)), skip_reason=str(data.get('skip_reason')) if data.get('skip_reason') is not None else None)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `cls` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `data` | `Mapping[str, Any]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`WadVoiceFilterDecision`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`data.get`、`tuple`、`cls`、`VoicePathStatus.from_dict`、`str`、`bool`、`isinstance`

### 函数 `to_dict`

#### `to_dict(self) -> dict[str, Any]`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:240`
- 作用：序列化为字典。
- 实现方式：
  1. 返回 `{'region_wad_path': self.region_wad_path, 'root_wad_path': self.root_wad_path, 'entity_type': self.entity_type, 'matched_bin_paths': list(self.matched_bin_paths), 'audio_paths': list(self.audio_paths), 'event_paths': list(self.event_paths), 'path_statuses': [item.to_dict() for item in self.path_statuses], 'changed_audio_paths': list(self.changed_audio_paths), 'changed_event_paths': list(self.changed_event_paths), 'should_unpack': self.should_unpack, 'skip_reason': self.skip_reason}` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`list`、`item.to_dict`

### 类 `ManifestVoiceFilterResult`
- 可见性：公开类
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:259`
- 作用：WAD 二次筛选汇总结果。
- 装饰器：`dataclass(frozen=True, slots=True)`
- 字段：
| 字段 | 类型 | 默认值 |
| --- | --- | --- |
| `unpack_paths` | `tuple[str, ...]` | `-` |
| `skipped_paths` | `tuple[str, ...]` | `-` |
| `decisions` | `tuple[WadVoiceFilterDecision, ...]` | `-` |
- 方法数量：2

### 函数 `from_dict`

#### `from_dict(cls, data: Mapping[str, Any]) -> ManifestVoiceFilterResult`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:267`
- 作用：从字典反序列化二次筛选汇总结果。
- 实现方式：
  1. 调用 `data.get` 并写入 `decisions_raw`。
  2. 调用 `tuple` 并写入 `decisions`。
  3. 返回 `cls(unpack_paths=tuple((str(item) for item in data.get('unpack_paths', tuple()))), skipped_paths=tuple((str(item) for item in data.get('skipped_paths', tuple()))), decisions=decisions)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `cls` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `data` | `Mapping[str, Any]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`ManifestVoiceFilterResult`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`data.get`、`tuple`、`cls`、`WadVoiceFilterDecision.from_dict`、`isinstance`、`str`

### 函数 `to_dict`

#### `to_dict(self) -> dict[str, Any]`
- 可见性：公开方法
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:282`
- 作用：序列化为字典。
- 实现方式：
  1. 返回 `{'unpack_paths': list(self.unpack_paths), 'skipped_paths': list(self.skipped_paths), 'decisions': [item.to_dict() for item in self.decisions]}` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `self` | `未标注` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`list`、`item.to_dict`

### 函数 `get_latest_versions`

#### `get_latest_versions(game_release_region: str = DEFAULT_GAME_RELEASE_REGION, lcu_release_region: str = DEFAULT_LCU_RELEASE_REGION) -> LatestVersions`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:292`
- 作用：获取 GAME 和 LCU 最新版本信息。
- 实现方式：
  1. 调用 `RiotGameData` 并写入 `game_data`。
  2. 执行 `game_data.load_lcu_data` 触发副作用逻辑。
  3. 执行 `game_data.load_game_data` 触发副作用逻辑。
  4. 调用 `game_data.latest_game` 并写入 `latest_game`。
  5. 调用 `game_data.latest_lcu` 并写入 `latest_lcu`。
  6. 根据条件分支选择不同处理路径。
  7. 根据条件分支选择不同处理路径。
  8. 返回 `LatestVersions(game_version=latest_game['version'], game_manifest_url=latest_game['url'], lcu_version=latest_lcu['version'], lcu_manifest_url=latest_lcu['url'])` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `game_release_region` | `str` | `DEFAULT_GAME_RELEASE_REGION` | `positional_or_keyword` | GAME 版本来源区域。 |
| `lcu_release_region` | `str` | `DEFAULT_LCU_RELEASE_REGION` | `positional_or_keyword` | LCU 版本来源区域。 |
- 返回类型：`LatestVersions`
- 返回说明：最新版本信息对象。
- 可能抛出：
  - `RuntimeError`
- 关键调用：`RiotGameData`、`game_data.load_lcu_data`、`game_data.load_game_data`、`game_data.latest_game`、`game_data.latest_lcu`、`LatestVersions`、`RuntimeError`

### 函数 `compare_major_minor`

#### `compare_major_minor(left_version: str, right_version: str) -> bool`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:328`
- 作用：比较两个版本号的 `major.minor` 是否一致。
- 实现方式：
  1. 调用 `left_version.split` 并写入 `left_parts`。
  2. 调用 `right_version.split` 并写入 `right_parts`。
  3. 返回 `left_parts[:2] == right_parts[:2]` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `left_version` | `str` | `-` | `positional_or_keyword` | 左侧版本号，如 `16.4.7480682`。 |
| `right_version` | `str` | `-` | `positional_or_keyword` | 右侧版本号，如 `16.4.7489999`。 |
- 返回类型：`bool`
- 返回说明：若 `major.minor` 相同返回 `True`，否则返回 `False`。
- 可能抛出：未显式声明。
- 关键调用：`left_version.split`、`right_version.split`

### 函数 `get_manifest_wad_changes`

#### `get_manifest_wad_changes(old_manifest_url: str, new_manifest_url: str, region: str) -> ManifestWadChanges`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:344`
- 作用：获取指定区域 WAD 的路径差异。
- 实现方式：
  1. 调用 `diff_manifests` 并写入 `report`。
  2. 返回 `ManifestWadChanges(added_paths=tuple(sorted(added_paths, key=str.casefold)), changed_paths=tuple(sorted(changed_paths, key=str.casefold)), removed_paths=tuple(sorted(removed_paths, key=str.casefold)))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `old_manifest_url` | `str` | `-` | `positional_or_keyword` | 旧版本 manifest URL。 |
| `new_manifest_url` | `str` | `-` | `positional_or_keyword` | 新版本 manifest URL。 |
| `region` | `str` | `-` | `positional_or_keyword` | 语言区域，如 `zh_CN`。 |
- 返回类型：`ManifestWadChanges`
- 返回说明：路径差异结果（added/changed/removed）。
- 可能抛出：未显式声明。
- 关键调用：`diff_manifests`、`ManifestWadChanges`、`str`、`_extract_diff_entry_path`、`getattr`、`tuple`、`sorted`

### 函数 `get_changed_entities`

#### `get_changed_entities(old_manifest_url: str, new_manifest_url: str, region: str) -> ChangedEntities`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:383`
- 作用：获取 Manifest 差异中的变更实体。
- 实现方式：
  1. 调用 `get_manifest_wad_changes` 并写入 `wad_changes`。
  2. 返回 `_extract_changed_entities_from_paths(paths=set(wad_changes.added_paths + wad_changes.changed_paths + wad_changes.removed_paths))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `old_manifest_url` | `str` | `-` | `positional_or_keyword` | 旧版本 manifest URL。 |
| `new_manifest_url` | `str` | `-` | `positional_or_keyword` | 新版本 manifest URL。 |
| `region` | `str` | `-` | `positional_or_keyword` | 语言区域，如 `zh_CN`。 |
- 返回类型：`ChangedEntities`
- 返回说明：变更实体集合。
- 可能抛出：未显式声明。
- 关键调用：`get_manifest_wad_changes`、`_extract_changed_entities_from_paths`、`set`

### 函数 `extract_changed_entities_from_wad_paths`

#### `extract_changed_entities_from_wad_paths(paths: Sequence[str]) -> ChangedEntities`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:407`
- 作用：从区域 WAD 路径集合提取英雄 alias 与地图 ID。
- 实现方式：
  1. 返回 `_extract_changed_entities_from_paths(paths=normalized_paths)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `paths` | `Sequence[str]` | `-` | `positional_or_keyword` | 区域 WAD 路径集合。 |
- 返回类型：`ChangedEntities`
- 返回说明：变更实体集合。
- 可能抛出：未显式声明。
- 关键调用：`_extract_changed_entities_from_paths`、`_normalize_manifest_path`、`isinstance`、`path.strip`

### 函数 `filter_wad_changes_by_bin_voice_paths`

#### `filter_wad_changes_by_bin_voice_paths(old_manifest_url: str, new_manifest_url: str, region: str, update_paths: Sequence[str], max_champion_skin_bin_index: int = DEFAULT_MAX_CHAMPION_SKIN_BIN_INDEX, unit_max_workers: int = DEFAULT_VOICE_FILTER_UNIT_MAX_WORKERS, extractor_prefetch_chunk_concurrency: int = DEFAULT_VOICE_FILTER_EXTRACTOR_PREFETCH_CONCURRENCY, bin_output_dir: Path | None = None) -> ManifestVoiceFilterResult`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:423`
- 作用：基于根 WAD 的 BIN 解析结果筛选真正需要解包的区域 WAD。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 根据条件分支选择不同处理路径。
  3. 根据条件分支选择不同处理路径。
  4. 调用 `_normalize_update_paths` 并写入 `normalized_paths`。
  5. 根据条件分支选择不同处理路径。
  6. 调用 `PatcherManifest` 并写入 `old_manifest`。
  7. 调用 `PatcherManifest` 并写入 `new_manifest`。
  8. 调用 `_build_manifest_file_index` 并写入 `old_file_index`。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `old_manifest_url` | `str` | `-` | `positional_or_keyword` | 旧版本 manifest URL。 |
| `new_manifest_url` | `str` | `-` | `positional_or_keyword` | 新版本 manifest URL。 |
| `region` | `str` | `-` | `positional_or_keyword` | 语言区域（例如 `zh_CN`）。 |
| `update_paths` | `Sequence[str]` | `-` | `positional_or_keyword` | 来自 manifest diff 的区域 WAD 变化路径（通常为 `added + changed`）。 |
| `max_champion_skin_bin_index` | `int` | `DEFAULT_MAX_CHAMPION_SKIN_BIN_INDEX` | `positional_or_keyword` | 英雄 BIN 探测上限（包含该值）。 |
| `unit_max_workers` | `int` | `DEFAULT_VOICE_FILTER_UNIT_MAX_WORKERS` | `positional_or_keyword` | 以英雄/地图为单位并发筛选时的最大并发数。 |
| `extractor_prefetch_chunk_concurrency` | `int` | `DEFAULT_VOICE_FILTER_EXTRACTOR_PREFETCH_CONCURRENCY` | `positional_or_keyword` | WADExtractor 内部预取下载并发 （映射 `prefetch_chunk_concurrency`）。 |
| `bin_output_dir` | `Path | None` | `None` | `positional_or_keyword` | 可选 BIN 落地目录；传入后会在筛选阶段直接写入 BIN 文件。 |
- 返回类型：`ManifestVoiceFilterResult`
- 返回说明：二次筛选结果，包含“需解包路径”、“可跳过路径”与每个 WAD 的明细判定。
- 可能抛出：
  - `ValueError`
  - `RuntimeError`
- 关键调用：`_normalize_update_paths`、`PatcherManifest`、`_build_manifest_file_index`、`_group_update_paths_by_root_wad`、`min`、`tuple`、`ManifestVoiceFilterResult`、`ValueError`、`_prepare_voice_filter_bin_output_dir`、`set`、`len`、`sorted`、`_build_wad_voice_filter_decisions_for_group`、`decisions.extend`、`collected_bin_payloads.extend`、`ThreadPoolExecutor`、`as_completed`、`on_bin_payloads`、`bin_payloads.items`、`_normalize_manifest_path`

### 函数 `_prepare_voice_filter_bin_output_dir`

#### `_prepare_voice_filter_bin_output_dir(bin_output_dir: Path) -> None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:588`
- 作用：准备 BIN 输出目录。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 执行 `bin_output_dir.mkdir` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `bin_output_dir` | `Path` | `-` | `positional_or_keyword` | BIN 输出目录。 |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`bin_output_dir.exists`、`bin_output_dir.mkdir`、`shutil.rmtree`

### 函数 `_write_voice_filter_bin_output_file`

#### `_write_voice_filter_bin_output_file(bin_output_dir: Path, relative_path: str, content: bytes) -> Path`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:600`
- 作用：写入单个 BIN 原始数据到输出目录。
- 实现方式：
  1. 调用 `_normalize_relative_bin_output_path` 并写入 `normalized_path`。
  2. 执行 `target_file.parent.mkdir` 触发副作用逻辑。
  3. 执行 `target_file.write_bytes` 触发副作用逻辑。
  4. 返回 `target_file` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `bin_output_dir` | `Path` | `-` | `positional_or_keyword` | BIN 输出目录。 |
| `relative_path` | `str` | `-` | `positional_or_keyword` | BIN 相对路径。 |
| `content` | `bytes` | `-` | `positional_or_keyword` | BIN 原始字节。 |
- 返回类型：`Path`
- 返回说明：已写入的目标文件路径。
- 可能抛出：未显式声明。
- 关键调用：`_normalize_relative_bin_output_path`、`target_file.parent.mkdir`、`target_file.write_bytes`

### 函数 `_normalize_relative_bin_output_path`

#### `_normalize_relative_bin_output_path(relative_path: str) -> Path`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:623`
- 作用：规范化 BIN 输出相对路径并阻止越界。
- 实现方式：
  1. 调用 `_normalize_manifest_path` 并写入 `raw`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `Path` 并写入 `path`。
  4. 根据条件分支选择不同处理路径。
  5. 调用 `Path` 并写入 `normalized`。
  6. 根据条件分支选择不同处理路径。
  7. 根据条件分支选择不同处理路径。
  8. 返回 `normalized` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `relative_path` | `str` | `-` | `positional_or_keyword` | 原始相对路径。 |
- 返回类型：`Path`
- 返回说明：规范化后的相对路径对象。
- 可能抛出：
  - `ValueError`
- 关键调用：`_normalize_manifest_path`、`Path`、`path.is_absolute`、`any`、`ValueError`

### 函数 `_build_wad_voice_filter_decision`

#### `_build_wad_voice_filter_decision(old_extractor: WADExtractor, new_extractor: WADExtractor, old_file_index: Mapping[str, Any], new_file_index: Mapping[str, Any], region: str, wad_path: str, max_champion_skin_bin_index: int, on_bin_payloads: Callable[[WadVoiceFilterDecision, Mapping[str, bytes]], None] | None = None) -> WadVoiceFilterDecision`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:650`
- 作用：构建单个区域 WAD 的二次筛选判定。
- 实现方式：
  1. 调用 `_normalize_manifest_path` 并写入 `normalized_wad_path`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `_resolve_root_wad_path` 并写入 `root_wad_path`。
  4. 根据条件分支选择不同处理路径。
  5. 调用 `_build_candidate_bin_paths` 并写入 `entity_type, candidate_bin_paths`。
  6. 根据条件分支选择不同处理路径。
  7. 根据条件分支选择不同处理路径。
  8. 调用 `_extract_existing_bin_raws` 并写入 `bin_raws`。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `old_extractor` | `WADExtractor` | `-` | `positional_or_keyword` | 旧版本 WAD 提取器。 |
| `new_extractor` | `WADExtractor` | `-` | `positional_or_keyword` | 新版本 WAD 提取器。 |
| `old_file_index` | `Mapping[str, Any]` | `-` | `positional_or_keyword` | 旧版本 manifest 文件索引。 |
| `new_file_index` | `Mapping[str, Any]` | `-` | `positional_or_keyword` | 新版本 manifest 文件索引。 |
| `region` | `str` | `-` | `positional_or_keyword` | 语言区域。 |
| `wad_path` | `str` | `-` | `positional_or_keyword` | 目标区域 WAD 路径。 |
| `max_champion_skin_bin_index` | `int` | `-` | `positional_or_keyword` | 英雄 BIN 探测上限。 |
| `on_bin_payloads` | `Callable[[WadVoiceFilterDecision, Mapping[str, bytes]], None] | None` | `None` | `positional_or_keyword` | 可选回调；当判定需解包时回传该 WAD 命中的 BIN 原始数据。 |
- 返回类型：`WadVoiceFilterDecision`
- 返回说明：单个 WAD 的筛选判定结果。
- 可能抛出：未显式声明。
- 关键调用：`_normalize_manifest_path`、`_resolve_root_wad_path`、`_build_candidate_bin_paths`、`_extract_existing_bin_raws`、`_collect_voice_paths_from_bin_raws`、`_collect_voice_path_statuses`、`tuple`、`bool`、`WadVoiceFilterDecision`、`normalized_wad_path.casefold`、`root_wad_path.casefold`、`sorted`、`on_bin_payloads`、`bin_raws.keys`

### 函数 `_collect_voice_path_statuses`

#### `_collect_voice_path_statuses(old_extractor: WADExtractor, new_extractor: WADExtractor, old_file_index: Mapping[str, Any], new_file_index: Mapping[str, Any], region_wad_path: str, audio_paths: tuple[str, ...], event_paths: tuple[str, ...]) -> tuple[VoicePathStatus, ...]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:836`
- 作用：收集语音路径状态（added/removed/changed/unchanged/missing）。
- 实现方式：
  1. 调用 `tuple` 并写入 `focus_paths`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `diff_manifests` 并写入 `manifest_report`。
  4. 调用 `diff_wad_headers` 并写入 `wad_header_report`。
  5. 调用 `_build_wad_focus_status_index` 并写入 `section_status_by_hash, missing_paths`。
  6. 调用 `_load_wad_header` 并写入 `old_header`。
  7. 调用 `_load_wad_header` 并写入 `new_header`。
  8. 遍历集合并执行批量处理。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `old_extractor` | `WADExtractor` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `new_extractor` | `WADExtractor` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `old_file_index` | `Mapping[str, Any]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `new_file_index` | `Mapping[str, Any]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `region_wad_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `audio_paths` | `tuple[str, ...]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `event_paths` | `tuple[str, ...]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[VoicePathStatus, ...]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`tuple`、`diff_manifests`、`diff_wad_headers`、`_build_wad_focus_status_index`、`_load_wad_header`、`sorted`、`statuses.append`、`VoicePathStatus`、`_resolve_inner_path_status`、`isinstance`、`path.strip`、`item.path.casefold`

### 函数 `_load_wad_header`

#### `_load_wad_header(extractor: WADExtractor, file_index: Mapping[str, Any], wad_path: str) -> Any | None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:916`
- 作用：按路径加载 WAD 头；文件不存在时返回 `None`。
- 实现方式：
  1. 调用 `file_index.get` 并写入 `file_obj`。
  2. 根据条件分支选择不同处理路径。
  3. 返回 `extractor.get_wad_header(file_obj)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `extractor` | `WADExtractor` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `file_index` | `Mapping[str, Any]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `wad_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`Any | None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`file_index.get`、`extractor.get_wad_header`、`wad_path.casefold`

### 函数 `_build_manifest_file_index`

#### `_build_manifest_file_index(manifest: PatcherManifest) -> dict[str, Any]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:929`
- 作用：构建 manifest 文件索引（key 为小写路径）。
- 实现方式：
  1. 返回 `{str(file.name).casefold(): file for file in manifest.files.values()}` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `manifest` | `PatcherManifest` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, Any]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`casefold`、`manifest.files.values`、`str`

### 函数 `_extract_existing_bin_raws`

#### `_extract_existing_bin_raws(extractor: WADExtractor, root_wad_path: str, candidate_bin_paths: Sequence[str]) -> dict[str, bytes]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:935`
- 作用：从根 WAD 中提取存在的 BIN 原始数据。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 返回 `existing` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `extractor` | `WADExtractor` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `root_wad_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `candidate_bin_paths` | `Sequence[str]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, bytes]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`range`、`len`、`list`、`extractor.extract_files`、`result.get`、`wad_result.items`、`isinstance`、`bytes`、`str`

### 函数 `_collect_voice_paths_from_bin_raws`

#### `_collect_voice_paths_from_bin_raws(root_wad_path: str, bin_raws: Mapping[str, bytes]) -> tuple[tuple[str, ...], tuple[str, ...]]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:957`
- 作用：从 BIN 数据提取并分类语音资源路径。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 返回 `_classify_voice_bank_paths(bank_paths)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `root_wad_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `bin_raws` | `Mapping[str, bytes]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[tuple[str, ...], tuple[str, ...]]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`bin_raws.items`、`_classify_voice_bank_paths`、`getattr`、`BIN`、`tuple`、`RuntimeError`、`isinstance`、`value.strip`、`bank_paths.append`

### 函数 `_classify_voice_bank_paths`

#### `_classify_voice_bank_paths(paths: Sequence[str]) -> tuple[tuple[str, ...], tuple[str, ...]]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:982`
- 作用：按规则将路径分类为 audio 与 event。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 返回 `(tuple(sorted(audio.values(), key=str.casefold)), tuple(sorted(events.values(), key=str.casefold)))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `paths` | `Sequence[str]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[tuple[str, ...], tuple[str, ...]]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_normalize_manifest_path`、`normalized.casefold`、`lowered.endswith`、`tuple`、`audio.setdefault`、`events.setdefault`、`sorted`、`audio.values`、`events.values`

### 函数 `_build_wad_focus_status_index`

#### `_build_wad_focus_status_index(region_wad_path: str, wad_header_report: Any) -> tuple[dict[int, VoicePathDiffStatus], set[str]]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:1003`
- 作用：从 `diff_wad_headers` 结果提取 path_hash 状态索引。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 返回 `({}, set())` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `region_wad_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `wad_header_report` | `Any` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[dict[int, VoicePathDiffStatus], set[str]]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`getattr`、`tuple`、`set`、`isinstance`、`file_path.casefold`、`region_wad_path.casefold`、`casefold`、`strip`、`path.strip`、`str`

### 函数 `_resolve_inner_path_status`

#### `_resolve_inner_path_status(path: str, old_header: Any | None, new_header: Any | None, section_status_by_hash: Mapping[int, VoicePathDiffStatus], missing_paths: set[str]) -> VoicePathDiffStatus`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:1033`
- 作用：按 `diff_wad_headers` 的 path_hash 差异结果解析单一路径状态。
- 实现方式：
  1. 调用 `_normalize_manifest_path` 并写入 `normalized_path`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `set` 并写入 `candidate_hashes`。
  4. 根据条件分支选择不同处理路径。
  5. 根据条件分支选择不同处理路径。
  6. 根据条件分支选择不同处理路径。
  7. 根据条件分支选择不同处理路径。
  8. 根据条件分支选择不同处理路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `old_header` | `Any | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `new_header` | `Any | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `section_status_by_hash` | `Mapping[int, VoicePathDiffStatus]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `missing_paths` | `set[str]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`VoicePathDiffStatus`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_normalize_manifest_path`、`set`、`normalized_path.casefold`、`candidate_hashes.add`、`_resolve_wad_path_hash`

### 函数 `_resolve_wad_path_hash`

#### `_resolve_wad_path_hash(header: Any, path: str) -> int`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:1072`
- 作用：按 WAD 版本算法计算路径哈希。
- 实现方式：
  1. 调用 `getattr` 并写入 `hash_func`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `getattr` 并写入 `fallback`。
  4. 根据条件分支选择不同处理路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `header` | `Any` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`int`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`getattr`、`callable`、`ValueError`、`int`、`type`、`hash_func`、`fallback`

### 函数 `_build_candidate_bin_paths`

#### `_build_candidate_bin_paths(root_wad_path: str, max_champion_skin_bin_index: int) -> tuple[str, tuple[str, ...]]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:1084`
- 作用：按根 WAD 类型构造 BIN 探测路径。
- 实现方式：
  1. 调用 `CHAMPION_ROOT_WAD_PATH_PATTERN.match` 并写入 `champion_match`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `MAP_ROOT_WAD_PATH_PATTERN.match` 并写入 `map_match`。
  4. 根据条件分支选择不同处理路径。
  5. 根据条件分支选择不同处理路径。
  6. 返回 `('unknown', tuple())` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `root_wad_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `max_champion_skin_bin_index` | `int` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[str, tuple[str, ...]]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`CHAMPION_ROOT_WAD_PATH_PATTERN.match`、`MAP_ROOT_WAD_PATH_PATTERN.match`、`casefold`、`tuple`、`MAP_COMMON_ROOT_WAD_PATH_PATTERN.match`、`map_match.group`、`champion_match.group`、`range`

### 函数 `_resolve_root_wad_path`

#### `_resolve_root_wad_path(region_wad_path: str, region: str) -> str | None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:1112`
- 作用：将 `xx.<region>.wad.client` 映射到根 WAD 路径 `xx.wad.client`。
- 实现方式：
  1. 调用 `_normalize_manifest_path` 并写入 `normalized`。
  2. 调用 `normalized.casefold` 并写入 `lowered`。
  3. 根据条件分支选择不同处理路径。
  4. 返回 `f'{normalized[:len(normalized) - len(region_suffix)]}.wad.client'` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `region_wad_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `region` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str | None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_normalize_manifest_path`、`normalized.casefold`、`lowered.endswith`、`region_suffix.casefold`、`len`

### 函数 `_normalize_update_paths`

#### `_normalize_update_paths(update_paths: Sequence[str]) -> tuple[str, ...]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:1123`
- 作用：标准化并去重 WAD 路径列表。
- 实现方式：
  1. 返回 `tuple(sorted({_normalize_manifest_path(path) for path in update_paths if isinstance(path, str) and path.strip()}, key=str.casefold))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `update_paths` | `Sequence[str]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[str, ...]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`tuple`、`sorted`、`_normalize_manifest_path`、`isinstance`、`path.strip`

### 函数 `_group_update_paths_by_root_wad`

#### `_group_update_paths_by_root_wad(update_paths: Sequence[str], region: str) -> tuple[tuple[str, ...], ...]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:1138`
- 作用：按根 WAD（英雄/地图单位）对区域 WAD 路径分组。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 返回 `tuple((tuple(sorted(set(paths), key=str.casefold)) for _, paths in sorted(grouped.items(), key=lambda item: item[0].casefold())))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `update_paths` | `Sequence[str]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `region` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[tuple[str, ...], ...]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`tuple`、`_normalize_manifest_path`、`_resolve_root_wad_path`、`append`、`grouped.setdefault`、`sorted`、`normalized_path.casefold`、`casefold`、`set`、`grouped.items`

### 函数 `_build_wad_voice_filter_decisions_for_group`

#### `_build_wad_voice_filter_decisions_for_group(old_manifest: PatcherManifest, new_manifest: PatcherManifest, old_file_index: Mapping[str, Any], new_file_index: Mapping[str, Any], region: str, wad_paths: Sequence[str], max_champion_skin_bin_index: int, extractor_prefetch_chunk_concurrency: int, collect_bin_payloads: bool) -> tuple[tuple[WadVoiceFilterDecision, ...], tuple[tuple[WadVoiceFilterDecision, dict[str, bytes]], ...]]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:1159`
- 作用：按单个单位分组执行 WAD 二次筛选。
- 实现方式：
  1. 在上下文管理器中执行资源操作。
  2. 返回 `(tuple(decisions), tuple(captured_payloads))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `old_manifest` | `PatcherManifest` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `new_manifest` | `PatcherManifest` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `old_file_index` | `Mapping[str, Any]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `new_file_index` | `Mapping[str, Any]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `region` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `wad_paths` | `Sequence[str]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `max_champion_skin_bin_index` | `int` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `extractor_prefetch_chunk_concurrency` | `int` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `collect_bin_payloads` | `bool` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[tuple[WadVoiceFilterDecision, ...], tuple[tuple[WadVoiceFilterDecision, dict[str, bytes]], ...]]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`WADExtractor`、`tuple`、`str`、`bytes`、`captured_payloads.append`、`_build_wad_voice_filter_decision`、`decisions.append`、`bin_payloads.items`、`isinstance`

### 函数 `_normalize_manifest_path`

#### `_normalize_manifest_path(path: str) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:1212`
- 作用：统一清洗 manifest 路径分隔符与首尾空白。
- 实现方式：
  1. 返回 `path.strip().replace('\\', '/')` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`replace`、`path.strip`

### 函数 `_extract_diff_entry_path`

#### `_extract_diff_entry_path(entry: Any) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:1217`
- 作用：提取 diff 条目中的路径字段。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 根据条件分支选择不同处理路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `entry` | `Any` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`isinstance`、`ValueError`、`entry.get`、`getattr`、`value.strip`

### 函数 `load_local_state`

#### `load_local_state(state_file: Path = DEFAULT_LOCAL_STATE_FILE) -> LocalRunState | None`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:1229`
- 作用：读取本地历史状态。
- 实现方式：
  1. 调用 `resolve` 并写入 `resolved_file`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `json.loads` 并写入 `payload`。
  4. 根据条件分支选择不同处理路径。
  5. 返回 `LocalRunState.from_dict(payload)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `state_file` | `Path` | `DEFAULT_LOCAL_STATE_FILE` | `positional_or_keyword` | 本地状态文件路径。 |
- 返回类型：`LocalRunState | None`
- 返回说明：读取到的状态对象；文件不存在时返回 `None`。
- 可能抛出：
  - `ValueError`
- 关键调用：`resolve`、`json.loads`、`LocalRunState.from_dict`、`resolved_file.exists`、`resolved_file.read_text`、`isinstance`、`ValueError`、`state_file.expanduser`

### 函数 `save_local_state`

#### `save_local_state(state: LocalRunState, state_file: Path = DEFAULT_LOCAL_STATE_FILE) -> Path`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:1252`
- 作用：写入本地历史状态。
- 实现方式：
  1. 调用 `resolve` 并写入 `resolved_file`。
  2. 执行 `resolved_file.parent.mkdir` 触发副作用逻辑。
  3. 执行 `resolved_file.write_text` 触发副作用逻辑。
  4. 返回 `resolved_file` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `state` | `LocalRunState` | `-` | `positional_or_keyword` | 状态对象。 |
| `state_file` | `Path` | `DEFAULT_LOCAL_STATE_FILE` | `positional_or_keyword` | 写入目标路径。 |
- 返回类型：`Path`
- 返回说明：已写入文件路径。
- 可能抛出：未显式声明。
- 关键调用：`resolve`、`resolved_file.parent.mkdir`、`resolved_file.write_text`、`json.dumps`、`state_file.expanduser`、`state.to_dict`

### 函数 `build_local_state`

#### `build_local_state(latest_versions: LatestVersions) -> LocalRunState`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:1275`
- 作用：根据最新版本构造状态对象。
- 实现方式：
  1. 调用 `replace` 并写入 `checked_at`。
  2. 返回 `LocalRunState(schema_version=LOCAL_STATE_SCHEMA_VERSION, game_version=latest_versions.game_version, game_manifest_url=latest_versions.game_manifest_url, lcu_version=latest_versions.lcu_version, lcu_manifest_url=latest_versions.lcu_manifest_url, checked_at=checked_at)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `latest_versions` | `LatestVersions` | `-` | `positional_or_keyword` | 最新版本信息。 |
- 返回类型：`LocalRunState`
- 返回说明：本地状态对象。
- 可能抛出：未显式声明。
- 关键调用：`replace`、`LocalRunState`、`isoformat`、`datetime.now`

### 函数 `evaluate_update_need`

#### `evaluate_update_need(region: str, state_file: Path = DEFAULT_LOCAL_STATE_FILE, game_release_region: str = DEFAULT_GAME_RELEASE_REGION, lcu_release_region: str = DEFAULT_LCU_RELEASE_REGION) -> UpdateDecision`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:1296`
- 作用：评估是否需要进入后续更新流程。
- 实现方式：
  1. 调用 `get_latest_versions` 并写入 `latest_versions`。
  2. 使用异常处理分支兜底失败路径。
  3. 返回 `evaluate_update_need_with_latest(region=region, latest_versions=latest_versions, previous_state=previous_state)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `region` | `str` | `-` | `positional_or_keyword` | 语言区域标识（例如 `zh_CN`）。 |
| `state_file` | `Path` | `DEFAULT_LOCAL_STATE_FILE` | `positional_or_keyword` | 本地状态文件路径。 |
| `game_release_region` | `str` | `DEFAULT_GAME_RELEASE_REGION` | `positional_or_keyword` | GAME 版本来源区域。 |
| `lcu_release_region` | `str` | `DEFAULT_LCU_RELEASE_REGION` | `positional_or_keyword` | LCU 版本来源区域。 |
- 返回类型：`UpdateDecision`
- 返回说明：更新判定结果。
- 可能抛出：未显式声明。
- 关键调用：`get_latest_versions`、`evaluate_update_need_with_latest`、`load_local_state`

### 函数 `evaluate_update_need_with_latest`

#### `evaluate_update_need_with_latest(region: str, latest_versions: LatestVersions, previous_state: LocalRunState | None) -> UpdateDecision`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:1329`
- 作用：基于给定最新版本与历史状态评估更新需求。
- 实现方式：
  1. 调用 `ChangedEntities` 并写入 `empty_changes`。
  2. 调用 `ManifestWadChanges` 并写入 `empty_wad_changes`。
  3. 根据条件分支选择不同处理路径。
  4. 根据条件分支选择不同处理路径。
  5. 调用 `get_manifest_wad_changes` 并写入 `wad_changes`。
  6. 调用 `_extract_changed_entities_from_paths` 并写入 `changed_entities`。
  7. 调用 `bool` 并写入 `has_region_changes`。
  8. 返回 `UpdateDecision(should_update=has_region_changes, reason=DECISION_REASON_REGION_MANIFEST_CHANGED if has_region_changes else DECISION_REASON_NO_REGION_MANIFEST_CHANGES, latest_versions=latest_versions, previous_state=previous_state, changed_entities=changed_entities, wad_changes=wad_changes)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `region` | `str` | `-` | `positional_or_keyword` | 语言区域标识（例如 `zh_CN`）。 |
| `latest_versions` | `LatestVersions` | `-` | `positional_or_keyword` | 最新版本信息。 |
| `previous_state` | `LocalRunState | None` | `-` | `positional_or_keyword` | 历史状态，首次执行可为 `None`。 |
- 返回类型：`UpdateDecision`
- 返回说明：更新判定结果。
- 可能抛出：未显式声明。
- 关键调用：`ChangedEntities`、`ManifestWadChanges`、`get_manifest_wad_changes`、`_extract_changed_entities_from_paths`、`bool`、`UpdateDecision`、`tuple`、`set`

### 函数 `_extract_changed_entities_from_paths`

#### `_extract_changed_entities_from_paths(paths: set[str]) -> ChangedEntities`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/manifest_ops.py:1397`
- 作用：从路径集合中提取英雄 alias 与地图 ID。
- 实现方式：
  1. 调用 `set` 并写入 `champion_aliases`。
  2. 调用 `set` 并写入 `map_ids`。
  3. 遍历集合并执行批量处理。
  4. 返回 `ChangedEntities(champion_aliases=tuple(sorted(champion_aliases, key=str.casefold)), map_ids=tuple(sorted(map_ids, key=lambda item: int(item))))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `paths` | `set[str]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`ChangedEntities`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`set`、`ChangedEntities`、`path.replace`、`CHAMPION_WAD_PATH_PATTERN.match`、`MAP_WAD_PATH_PATTERN.match`、`champion_aliases.add`、`tuple`、`champion_match.group`、`map_match.group`、`map_ids.add`、`sorted`、`int`

## 模块 `src/rift_audio_pipeline/packer.py`
- 模块说明：打包模块。
- 类数量：0
- 函数/方法数量：14
- 函数索引：`pack_champion`、`pack_all`、`_resolve_7zip_executable`、`_validate_compression_level`、`_normalize_extra_files`、`_normalize_report_file`、`_normalize_archive_name`、`_build_archive_name`、`_resolve_report_file`、`_stage_directory`、`_stage_report_file`、`_stage_extra_files`、`_build_7z_command`、`_execute_7z_command`

### 函数 `pack_champion`

#### `pack_champion(champion_dir: Path, output_path: Path, *, archive_name: str | None = None, report_file: Path | None = None, password: str | None = None, encrypt_filenames: bool = True, extra_files: Sequence[Path] = tuple(), compression_level: int = DEFAULT_COMPRESSION_LEVEL, seven_zip_executable: str | None = None) -> Path`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/packer.py:17`
- 作用：打包单个英雄语音目录。
- 实现方式：
  1. 调用 `resolve` 并写入 `source_dir`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `resolve` 并写入 `output_dir`。
  4. 执行 `output_dir.mkdir` 触发副作用逻辑。
  5. 调用 `_normalize_archive_name` 并写入 `archive_file_name`。
  6. 调用 `_resolve_7zip_executable` 并写入 `executable`。
  7. 调用 `_validate_compression_level` 并写入 `level`。
  8. 调用 `_normalize_extra_files` 并写入 `staged_extra_files`。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `champion_dir` | `Path` | `-` | `positional_or_keyword` | 英雄语音目录。 |
| `output_path` | `Path` | `-` | `positional_or_keyword` | 打包产物目录。 |
| `archive_name` | `str | None` | `None` | `keyword_only` | 压缩包文件名；为空时使用目录名。 |
| `report_file` | `Path | None` | `None` | `keyword_only` | 可选的 `_id_metadata.yaml` 报告文件。 |
| `password` | `str | None` | `None` | `keyword_only` | 压缩包密码；为空时不启用密码。 |
| `encrypt_filenames` | `bool` | `True` | `keyword_only` | 启用密码时是否开启文件名加密（`-mhe=on`）。 |
| `extra_files` | `Sequence[Path]` | `tuple()` | `keyword_only` | 需要附加到压缩包根目录的额外文件集合。 |
| `compression_level` | `int` | `DEFAULT_COMPRESSION_LEVEL` | `keyword_only` | 压缩级别（`0-9`）。 |
| `seven_zip_executable` | `str | None` | `None` | `keyword_only` | 指定 7z 可执行文件；为空时自动查找。 |
- 返回类型：`Path`
- 返回说明：产物路径。
- 可能抛出：
  - `FileNotFoundError`
  - `ValueError`
  - `RuntimeError`
- 关键调用：`tuple`、`resolve`、`output_dir.mkdir`、`_normalize_archive_name`、`_resolve_7zip_executable`、`_validate_compression_level`、`_normalize_extra_files`、`_normalize_report_file`、`source_dir.is_dir`、`FileNotFoundError`、`tempfile.TemporaryDirectory`、`Path`、`_stage_directory`、`_stage_report_file`、`_stage_extra_files`、`_build_7z_command`、`_execute_7z_command`、`champion_dir.expanduser`、`output_path.expanduser`

### 函数 `pack_all`

#### `pack_all(audio_dir: Path, output_dir: Path, *, version: str | None = None, audio_type: str | None = None, report_dir: Path | None = None, password: str | None = None, encrypt_filenames: bool = True, extra_files: Sequence[Path] = tuple(), compression_level: int = DEFAULT_COMPRESSION_LEVEL, seven_zip_executable: str | None = None) -> tuple[Path, ...]`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/packer.py:83`
- 作用：批量打包语音目录。
- 实现方式：
  1. 调用 `resolve` 并写入 `source_root`。
  2. 根据条件分支选择不同处理路径。
  3. 遍历集合并执行批量处理。
  4. 返回 `tuple(archives)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `audio_dir` | `Path` | `-` | `positional_or_keyword` | 音频目录。 |
| `output_dir` | `Path` | `-` | `positional_or_keyword` | 产物目录。 |
| `version` | `str | None` | `None` | `keyword_only` | 压缩包版本后缀（例如 `16.4`）。 |
| `audio_type` | `str | None` | `None` | `keyword_only` | 压缩包类型后缀（例如 `VO`）。 |
| `report_dir` | `Path | None` | `None` | `keyword_only` | 报告目录，命名规则为 `_<实体ID>_metadata.yaml`。 |
| `password` | `str | None` | `None` | `keyword_only` | 压缩包密码；为空时不启用密码。 |
| `encrypt_filenames` | `bool` | `True` | `keyword_only` | 启用密码时是否开启文件名加密（`-mhe=on`）。 |
| `extra_files` | `Sequence[Path]` | `tuple()` | `keyword_only` | 需要附加到压缩包根目录的额外文件集合。 |
| `compression_level` | `int` | `DEFAULT_COMPRESSION_LEVEL` | `keyword_only` | 压缩级别（`0-9`）。 |
| `seven_zip_executable` | `str | None` | `None` | `keyword_only` | 指定 7z 可执行文件；为空时自动查找。 |
- 返回类型：`tuple[Path, ...]`
- 返回说明：打包产物路径集合。
- 可能抛出：
  - `FileNotFoundError`
  - `ValueError`
  - `RuntimeError`
- 关键调用：`tuple`、`resolve`、`sorted`、`source_root.is_dir`、`FileNotFoundError`、`source_root.iterdir`、`archives.append`、`audio_dir.expanduser`、`item.is_dir`、`pack_champion`、`path.name.casefold`、`_build_archive_name`、`_resolve_report_file`

### 函数 `_resolve_7zip_executable`

#### `_resolve_7zip_executable(seven_zip_executable: str | None) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/packer.py:147`
- 作用：解析 7z 可执行文件路径。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 遍历集合并执行批量处理。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `seven_zip_executable` | `str | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`FileNotFoundError`、`shutil.which`

### 函数 `_validate_compression_level`

#### `_validate_compression_level(compression_level: int) -> int`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/packer.py:159`
- 作用：校验压缩级别。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 返回 `compression_level` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `compression_level` | `int` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`int`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`ValueError`

### 函数 `_normalize_extra_files`

#### `_normalize_extra_files(extra_files: Sequence[Path]) -> tuple[Path, ...]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/packer.py:169`
- 作用：标准化并校验附加文件列表。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 返回 `tuple(resolved)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `extra_files` | `Sequence[Path]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[Path, ...]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`tuple`、`resolve`、`resolved.append`、`resolved_path.is_file`、`FileNotFoundError`、`file_path.expanduser`

### 函数 `_normalize_report_file`

#### `_normalize_report_file(report_file: Path | None) -> Path | None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/packer.py:181`
- 作用：标准化并校验报告文件。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 调用 `resolve` 并写入 `resolved`。
  3. 根据条件分支选择不同处理路径。
  4. 返回 `resolved` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `report_file` | `Path | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`Path | None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`resolve`、`resolved.is_file`、`FileNotFoundError`、`report_file.expanduser`

### 函数 `_normalize_archive_name`

#### `_normalize_archive_name(archive_name: str | None, fallback: str) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/packer.py:192`
- 作用：规范化压缩包文件名。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 根据条件分支选择不同处理路径。
  3. 返回 `raw_name` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `archive_name` | `str | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `fallback` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`isinstance`、`archive_name.strip`、`raw_name.endswith`

### 函数 `_build_archive_name`

#### `_build_archive_name(directory_name: str, version: str | None, audio_type: str | None) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/packer.py:203`
- 作用：构建压缩包文件名。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 根据条件分支选择不同处理路径。
  3. 返回 `f"{'-'.join(parts)}{ARCHIVE_SUFFIX}"` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `directory_name` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `version` | `str | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `audio_type` | `str | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`version.strip`、`parts.append`、`audio_type.strip`、`join`

### 函数 `_resolve_report_file`

#### `_resolve_report_file(folder_name: str, report_dir: Path | None) -> Path | None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/packer.py:218`
- 作用：根据目录名解析对应报告文件。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 调用 `resolve` 并写入 `resolved_report_dir`。
  3. 根据条件分支选择不同处理路径。
  4. 调用 `strip` 并写入 `entity_id`。
  5. 根据条件分支选择不同处理路径。
  6. 根据条件分支选择不同处理路径。
  7. 返回 `None` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `folder_name` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `report_dir` | `Path | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`Path | None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`resolve`、`strip`、`candidate.is_file`、`resolved_report_dir.is_dir`、`report_dir.expanduser`、`folder_name.split`

### 函数 `_stage_directory`

#### `_stage_directory(stage_root: Path, source_dir: Path) -> None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/packer.py:235`
- 作用：将目录以链接或复制方式放入临时打包目录。
- 实现方式：
  1. 使用异常处理分支兜底失败路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `stage_root` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `source_dir` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`target.symlink_to`、`shutil.copytree`

### 函数 `_stage_report_file`

#### `_stage_report_file(stage_root: Path, report_file: Path | None) -> None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/packer.py:245`
- 作用：将报告文件复制到压缩包根目录。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 执行 `shutil.copy2` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `stage_root` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `report_file` | `Path | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`shutil.copy2`

### 函数 `_stage_extra_files`

#### `_stage_extra_files(stage_root: Path, extra_files: Sequence[Path]) -> None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/packer.py:254`
- 作用：将附加文件复制到压缩包根目录。
- 实现方式：
  1. 调用 `set` 并写入 `used_names`。
  2. 遍历集合并执行批量处理。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `stage_root` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `extra_files` | `Sequence[Path]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`set`、`file_path.name.casefold`、`used_names.add`、`shutil.copy2`、`ValueError`

### 函数 `_build_7z_command`

#### `_build_7z_command(executable: str, archive_path: Path, compression_level: int, password: str | None, encrypt_filenames: bool) -> tuple[str, ...]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/packer.py:267`
- 作用：构建 7z 打包命令。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 执行 `command.extend` 触发副作用逻辑。
  3. 返回 `tuple(command)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `executable` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `archive_path` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `compression_level` | `int` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `password` | `str | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `encrypt_filenames` | `bool` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[str, ...]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`command.extend`、`tuple`、`command.append`、`str`

### 函数 `_execute_7z_command`

#### `_execute_7z_command(command: Sequence[str], cwd: Path) -> None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/packer.py:291`
- 作用：执行 7z 命令并在失败时抛出带上下文的异常。
- 实现方式：
  1. 使用异常处理分支兜底失败路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `command` | `Sequence[str]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `cwd` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`subprocess.run`、`list`、`strip`、`RuntimeError`

## 模块 `src/rift_audio_pipeline/pipeline/__init__.py`
- 模块说明：Pipeline 包入口。
- 类数量：0
- 函数/方法数量：0

## 模块 `src/rift_audio_pipeline/pipeline/orchestrator.py`
- 模块说明：主流程编排模块。
- 类数量：2
- 函数/方法数量：21
- 类索引：`_StreamingEntityTask`、`_PackedEntityArtifact`
- 函数索引：`run_pipeline`、`_should_enable_streaming_mode`、`_resolve_effective_unpack_workers`、`_run_streaming_unpack_pack_upload`、`_build_streaming_entity_tasks`、`_run_streaming_upload_worker`、`_enqueue_streaming_upload_job`、`_drain_streaming_upload_queue`、`_ensure_streaming_disk_space`、`_estimate_streaming_required_bytes`、`_resolve_runtime_wad_file`、`_pack_single_streaming_entity`、`_resolve_entity_audio_directory`、`_extract_entity_id_from_directory_name`、`_build_entity_archive_name`、`_cleanup_task_runtime_wads`、`_cleanup_entity_audio_output`、`_cleanup_uploaded_archive`、`_resolve_runtime_game_path`、`_build_runtime_download_dir`、`_resolve_runtime_download_dirs`

### 类 `_StreamingEntityTask`
- 可见性：内部类
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:78`
- 作用：低磁盘流式模式中的单实体任务。
- 装饰器：`dataclass(frozen=True, slots=True)`
- 字段：
| 字段 | 类型 | 默认值 |
| --- | --- | --- |
| `target` | `str` | `-` |
| `entity_id` | `int` | `-` |
| `champion_ids` | `tuple[int, ...]` | `-` |
| `map_ids` | `tuple[int, ...]` | `-` |
| `runtime_wad_paths` | `tuple[str, ...]` | `-` |
- 方法数量：0

### 类 `_PackedEntityArtifact`
- 可见性：内部类
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:89`
- 作用：单实体打包结果。
- 装饰器：`dataclass(frozen=True, slots=True)`
- 字段：
| 字段 | 类型 | 默认值 |
| --- | --- | --- |
| `task` | `_StreamingEntityTask` | `-` |
| `archive_path` | `Path` | `-` |
- 方法数量：0

### 函数 `run_pipeline`

#### `run_pipeline(config: PipelineConfig) -> int`
- 可见性：公开函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:96`
- 作用：执行流水线主入口。
- 实现方式：
  1. 执行 `config.output_path.mkdir` 触发副作用逻辑。
  2. 调用 `ensure_official_sdk_path` 并写入 `sdk_dir`。
  3. 执行 `logger.info` 触发副作用逻辑。
  4. 使用异常处理分支兜底失败路径。
  5. 执行 `logger.info` 触发副作用逻辑。
  6. 调用 `_normalize_pipeline_game_version` 并写入 `pipeline_game_version`。
  7. 根据条件分支选择不同处理路径。
  8. 根据条件分支选择不同处理路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `config` | `PipelineConfig` | `-` | `positional_or_keyword` | 流水线配置对象。 |
- 返回类型：`int`
- 返回说明：退出状态码，`0` 表示执行成功。
- 可能抛出：未显式声明。
- 关键调用：`config.output_path.mkdir`、`ensure_official_sdk_path`、`logger.info`、`_normalize_pipeline_game_version`、`_resolve_package_output_root`、`_resolve_runtime_game_path`、`_build_runtime_download_dir`、`_resolve_runtime_download_dirs`、`data_file_base.parent.name.strip`、`resolve_processing_targets`、`tuple`、`_should_enable_streaming_mode`、`_resolve_effective_unpack_workers`、`build_local_state`、`save_local_state`、`evaluate_update_need`、`logger.error`、`_preflight_remote_upload_index`、`_retry_pending_manifest_sync_queue`、`check_local_game_path`

### 函数 `_should_enable_streaming_mode`

#### `_should_enable_streaming_mode(config: PipelineConfig, runtime_is_simulated: bool, targets: object) -> bool`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:554`
- 作用：判定是否启用低磁盘流式模式。
- 实现方式：
  1. 调用 `bool` 并写入 `has_targets`。
  2. 根据条件分支选择不同处理路径。
  3. 根据条件分支选择不同处理路径。
  4. 执行 `logger.info` 触发副作用逻辑。
  5. 返回 `False` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `config` | `PipelineConfig` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `runtime_is_simulated` | `bool` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `targets` | `object` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`bool`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`bool`、`logger.info`、`getattr`、`tuple`

### 函数 `_resolve_effective_unpack_workers`

#### `_resolve_effective_unpack_workers(configured_workers: int, runtime_is_simulated: bool) -> int`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:572`
- 作用：解析本次运行实际生效的解包并发数。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 调用 `max` 并写入 `cpu_workers`。
  3. 调用 `max` 并写入 `effective_workers`。
  4. 根据条件分支选择不同处理路径。
  5. 返回 `effective_workers` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `configured_workers` | `int` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `runtime_is_simulated` | `bool` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`int`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`max`、`logger.info`、`os.cpu_count`

### 函数 `_run_streaming_unpack_pack_upload`

#### `_run_streaming_unpack_pack_upload(config: PipelineConfig, game_version: str, data_file_base: Path, targets: object, runtime_game_path: Path, runtime_wad_paths: tuple[str, ...], include_root_wad: bool, unpack_workers: int, allow_missing_remote_index: bool, run_record_collector: list[dict[str, object]], preloaded_remote_index: dict[str, dict[str, object]] | None = None, pending_manifest_sync_queue_file: Path | None = None) -> Path | None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:592`
- 作用：执行实体级流式流水线：解包 -> 打包 -> 上传 -> 清理。
- 实现方式：
  1. 调用 `_build_streaming_entity_tasks` 并写入 `tasks`。
  2. 根据条件分支选择不同处理路径。
  3. 执行 `logger.info` 触发副作用逻辑。
  4. 调用 `_resolve_pack_extra_files` 并写入 `extra_files`。
  5. 调用 `_resolve_pack_archive_type` 并写入 `archive_audio_type`。
  6. 根据条件分支选择不同处理路径。
  7. 根据条件分支选择不同处理路径。
  8. 调用 `Queue` 并写入 `upload_queue`。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `config` | `PipelineConfig` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `data_file_base` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `targets` | `object` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `runtime_game_path` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `runtime_wad_paths` | `tuple[str, ...]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `include_root_wad` | `bool` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `unpack_workers` | `int` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `allow_missing_remote_index` | `bool` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `run_record_collector` | `list[dict[str, object]]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `preloaded_remote_index` | `dict[str, dict[str, object]] | None` | `None` | `positional_or_keyword` | （Docstring 未提供） |
| `pending_manifest_sync_queue_file` | `Path | None` | `None` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`Path | None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_build_streaming_entity_tasks`、`logger.info`、`_resolve_pack_extra_files`、`_resolve_pack_archive_type`、`Queue`、`threading.Thread`、`upload_thread.start`、`logger.warning`、`len`、`_enqueue_streaming_upload_job`、`upload_thread.join`、`join`、`_ensure_streaming_disk_space`、`run_unpack`、`_pack_single_streaming_entity`、`_cleanup_task_runtime_wads`、`_cleanup_entity_audio_output`、`RuntimeError`、`upload_thread.is_alive`、`_drain_streaming_upload_queue`

### 函数 `_build_streaming_entity_tasks`

#### `_build_streaming_entity_tasks(data_file_base: Path, region: str, targets: object, runtime_wad_paths: tuple[str, ...], include_root_wad: bool) -> tuple[_StreamingEntityTask, ...]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:732`
- 作用：构建流式模式所需的实体任务集合。
- 实现方式：
  1. 调用 `tuple` 并写入 `champion_ids`。
  2. 调用 `tuple` 并写入 `map_ids`。
  3. 遍历集合并执行批量处理。
  4. 遍历集合并执行批量处理。
  5. 返回 `tuple(tasks)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `data_file_base` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `region` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `targets` | `object` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `runtime_wad_paths` | `tuple[str, ...]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `include_root_wad` | `bool` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[_StreamingEntityTask, ...]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`tuple`、`item.casefold`、`resolve_runtime_wad_paths`、`tasks.append`、`int`、`_StreamingEntityTask`、`getattr`、`runtime_wad_index.get`、`path.casefold`

### 函数 `_run_streaming_upload_worker`

#### `_run_streaming_upload_worker(config: PipelineConfig, game_version: str, upload_queue: Queue[_PackedEntityArtifact | None], upload_errors: list[Exception], upload_manifest_holder: list[Path | None], allow_missing_remote_index: bool, run_record_collector: list[dict[str, object]], preloaded_remote_index: dict[str, dict[str, object]] | None = None, pending_manifest_sync_queue_file: Path | None = None) -> None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:789`
- 作用：消费流式打包产物并执行上传与压缩包清理。
- 实现方式：
  1. 执行 `logger.debug` 触发副作用逻辑。
  2. 使用异常处理分支兜底失败路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `config` | `PipelineConfig` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `upload_queue` | `Queue[_PackedEntityArtifact | None]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `upload_errors` | `list[Exception]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `upload_manifest_holder` | `list[Path | None]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `allow_missing_remote_index` | `bool` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `run_record_collector` | `list[dict[str, object]]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `preloaded_remote_index` | `dict[str, dict[str, object]] | None` | `None` | `positional_or_keyword` | （Docstring 未提供） |
| `pending_manifest_sync_queue_file` | `Path | None` | `None` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`logger.debug`、`_resolve_package_output_root`、`BaiduCredentials`、`resolve_token_store`、`BaiduPanClient`、`_initialize_remote_upload_layout`、`_resolve_upload_remote_index`、`_current_utc_timestamp`、`_resolve_default_upload_resource_type`、`ValueError`、`upload_queue.get`、`logger.exception`、`upload_errors.append`、`client.close`、`_process_archives_upload`、`run_entries.extend`、`_cleanup_uploaded_archive`、`logger.info`、`upload_queue.task_done`、`_finalize_upload_manifest`

### 函数 `_enqueue_streaming_upload_job`

#### `_enqueue_streaming_upload_job(upload_queue: Queue[_PackedEntityArtifact | None], upload_errors: list[Exception], artifact: _PackedEntityArtifact | None) -> None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:891`
- 作用：将实体打包产物安全入队，避免上传线程异常导致阻塞。
- 实现方式：
  1. 在循环中持续处理直到满足退出条件。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `upload_queue` | `Queue[_PackedEntityArtifact | None]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `upload_errors` | `list[Exception]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `artifact` | `_PackedEntityArtifact | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`RuntimeError`、`upload_queue.put`

### 函数 `_drain_streaming_upload_queue`

#### `_drain_streaming_upload_queue(upload_queue: Queue[_PackedEntityArtifact | None]) -> None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:908`
- 作用：在异常场景下尝试终止上传线程并释放队列阻塞。
- 实现方式：
  1. 在循环中持续处理直到满足退出条件。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `upload_queue` | `Queue[_PackedEntityArtifact | None]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`upload_queue.put_nowait`、`upload_queue.get_nowait`、`upload_queue.task_done`

### 函数 `_ensure_streaming_disk_space`

#### `_ensure_streaming_disk_space(config: PipelineConfig, game_version: str, runtime_game_path: Path, task: _StreamingEntityTask) -> None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:923`
- 作用：在流式任务启动前执行磁盘空间检查。
- 实现方式：
  1. 调用 `_estimate_streaming_required_bytes` 并写入 `required_bytes`。
  2. 调用 `_resolve_package_output_root` 并写入 `package_root`。
  3. 调用 `tuple` 并写入 `probe_dirs`。
  4. 遍历集合并执行批量处理。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `config` | `PipelineConfig` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `runtime_game_path` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `task` | `_StreamingEntityTask` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_estimate_streaming_required_bytes`、`_resolve_package_output_root`、`tuple`、`probe.mkdir`、`check_disk_space`、`RuntimeError`、`resolve`、`runtime_game_path.expanduser`、`config.output_path.expanduser`、`package_root.expanduser`

### 函数 `_estimate_streaming_required_bytes`

#### `_estimate_streaming_required_bytes(runtime_game_path: Path, task: _StreamingEntityTask) -> int`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:953`
- 作用：估算当前实体任务执行所需的最小可用磁盘空间。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 返回 `max(STREAMING_MIN_REQUIRED_BYTES, estimated)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `runtime_game_path` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `task` | `_StreamingEntityTask` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`int`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`max`、`_resolve_runtime_wad_file`、`wad_file.stat`、`wad_file.is_file`

### 函数 `_resolve_runtime_wad_file`

#### `_resolve_runtime_wad_file(runtime_game_path: Path, runtime_wad_path: str) -> Path | None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:972`
- 作用：将运行时 WAD 路径转换为本地文件路径。
- 实现方式：
  1. 调用 `replace` 并写入 `normalized`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `normalized.removeprefix` 并写入 `relative_path`。
  4. 根据条件分支选择不同处理路径。
  5. 调用 `Path` 并写入 `relative`。
  6. 根据条件分支选择不同处理路径。
  7. 返回 `runtime_game_path / relative` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `runtime_game_path` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `runtime_wad_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`Path | None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`replace`、`normalized.removeprefix`、`relative_path.startswith`、`Path`、`any`、`runtime_wad_path.strip`

### 函数 `_pack_single_streaming_entity`

#### `_pack_single_streaming_entity(config: PipelineConfig, game_version: str, task: _StreamingEntityTask, extra_files: tuple[Path, ...], archive_audio_type: str | None) -> tuple[_PackedEntityArtifact, Path, Path | None]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:987`
- 作用：打包单实体输出并返回产物信息。
- 实现方式：
  1. 调用 `_resolve_entity_audio_directory` 并写入 `entity_audio_dir`。
  2. 调用 `_build_entity_archive_name` 并写入 `archive_name`。
  3. 调用 `pack_champion` 并写入 `archive_path`。
  4. 返回 `(_PackedEntityArtifact(task=task, archive_path=archive_path), entity_audio_dir, normalized_report_file)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `config` | `PipelineConfig` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `task` | `_StreamingEntityTask` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `extra_files` | `tuple[Path, ...]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `archive_audio_type` | `str | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[_PackedEntityArtifact, Path, Path | None]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_resolve_entity_audio_directory`、`_build_entity_archive_name`、`pack_champion`、`report_file.is_file`、`_PackedEntityArtifact`、`_resolve_package_output_root`

### 函数 `_resolve_entity_audio_directory`

#### `_resolve_entity_audio_directory(output_path: Path, game_version: str, task: _StreamingEntityTask) -> Path`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:1031`
- 作用：定位当前实体对应的解包输出目录。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 调用 `tuple` 并写入 `matched_dirs`。
  3. 根据条件分支选择不同处理路径。
  4. 根据条件分支选择不同处理路径。
  5. 返回 `matched_dirs[0]` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `output_path` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `task` | `_StreamingEntityTask` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`Path`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`tuple`、`target_root.is_dir`、`FileNotFoundError`、`len`、`RuntimeError`、`target_root.iterdir`、`item.is_dir`、`_extract_entity_id_from_directory_name`

### 函数 `_extract_entity_id_from_directory_name`

#### `_extract_entity_id_from_directory_name(directory_name: str) -> int | None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:1060`
- 作用：从目录名中解析实体 ID。
- 实现方式：
  1. 调用 `strip` 并写入 `prefix`。
  2. 根据条件分支选择不同处理路径。
  3. 返回 `None` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `directory_name` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`int | None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`strip`、`prefix.isdigit`、`int`、`directory_name.split`

### 函数 `_build_entity_archive_name`

#### `_build_entity_archive_name(directory_name: str, game_version: str, audio_type: str | None) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:1069`
- 作用：构建单实体压缩包名称，规则与批量打包保持一致。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 根据条件分支选择不同处理路径。
  3. 返回 `f"{'-'.join(parts)}.7z"` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `directory_name` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `audio_type` | `str | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`game_version.strip`、`parts.append`、`isinstance`、`audio_type.strip`、`join`

### 函数 `_cleanup_task_runtime_wads`

#### `_cleanup_task_runtime_wads(runtime_game_path: Path, runtime_wad_paths: tuple[str, ...]) -> int`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:1084`
- 作用：清理单实体关联的运行时 WAD 文件。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 返回 `removed_count` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `runtime_game_path` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `runtime_wad_paths` | `tuple[str, ...]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`int`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_resolve_runtime_wad_file`、`wad_file.unlink`、`wad_file.is_file`

### 函数 `_cleanup_entity_audio_output`

#### `_cleanup_entity_audio_output(entity_audio_dir: Path, report_file: Path | None) -> int`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:1103`
- 作用：清理单实体解包目录与对应报告文件。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 根据条件分支选择不同处理路径。
  3. 返回 `removed_files` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `entity_audio_dir` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `report_file` | `Path | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`int`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`entity_audio_dir.is_dir`、`entity_audio_dir.rglob`、`shutil.rmtree`、`report_file.is_file`、`report_file.unlink`、`item.is_file`

### 函数 `_cleanup_uploaded_archive`

#### `_cleanup_uploaded_archive(archive_path: Path) -> None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:1121`
- 作用：在上传成功后删除本地压缩包。
- 实现方式：
  1. 执行 `archive_path.unlink` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `archive_path` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`archive_path.unlink`

### 函数 `_resolve_runtime_game_path`

#### `_resolve_runtime_game_path(config: PipelineConfig, latest_game_version: str) -> tuple[Path, bool]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:1127`
- 作用：解析本次运行使用的游戏目录。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 调用 `expanduser` 并写入 `simulated_base`。
  3. 调用 `build_simulated_dir` 并写入 `simulated_dir`。
  4. 执行 `write_content_metadata` 触发副作用逻辑。
  5. 执行 `logger.info` 触发副作用逻辑。
  6. 返回 `(simulated_dir, True)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `config` | `PipelineConfig` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `latest_game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[Path, bool]`
- 返回说明：二元组 `(runtime_game_path, runtime_is_simulated)`。
- 可能抛出：未显式声明。
- 关键调用：`expanduser`、`build_simulated_dir`、`write_content_metadata`、`logger.info`、`simulated_base.resolve`、`resolve`、`Path`

### 函数 `_build_runtime_download_dir`

#### `_build_runtime_download_dir(runtime_game_path: Path, game_version: str, region: str, runtime_is_simulated: bool) -> Path`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:1150`
- 作用：构建运行时下载缓存目录。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 返回 `runtime_game_path.parent / 'downloads' / game_version / region` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `runtime_game_path` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `region` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `runtime_is_simulated` | `bool` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`Path`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：未识别到显式函数调用。

### 函数 `_resolve_runtime_download_dirs`

#### `_resolve_runtime_download_dirs(runtime_download_dir: Path, runtime_is_simulated: bool) -> tuple[Path, Path]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/orchestrator.py:1163`
- 作用：解析 GAME/LCU 下载目录。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 返回 `(runtime_download_dir / 'game', runtime_download_dir / 'lcu')` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `runtime_download_dir` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `runtime_is_simulated` | `bool` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[Path, Path]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：未识别到显式函数调用。

## 模块 `src/rift_audio_pipeline/pipeline/upload.py`
- 模块说明：Pipeline 上传、索引与日志模块。
- 类数量：2
- 函数/方法数量：32
- 类索引：`_ArchiveUploadLayout`、`_IndexedArchiveMetadata`
- 函数索引：`_pack_unpacked_outputs`、`_preflight_remote_upload_index`、`_upload_archives_and_manifest`、`_resolve_upload_remote_index`、`_clone_upload_manifest_index`、`_process_archives_upload`、`_finalize_upload_manifest`、`_merge_remote_index_for_finalize`、`_collect_remote_index_mutation_keys`、`_retry_pending_manifest_sync_queue`、`_enqueue_pending_manifest_sync`、`_load_pending_manifest_sync_entries`、`_save_pending_manifest_sync_entries`、`_resolve_package_output_root`、`_resolve_pack_extra_files`、`_resolve_pack_archive_type`、`_resolve_default_upload_resource_type`、`_build_archive_upload_layout`、`_resolve_archive_target_group`、`_parse_archive_file_name`、`_archive_remote_old_versions`、`_resolve_index_entry_metadata`、`_build_relative_remote_path`、`_ensure_remote_directory`、`_initialize_remote_upload_layout`、`_build_readable_upload_manifest_content`、`_build_upload_database_payload`、`_write_and_upload_update_log_files`、`_build_update_log_payload`、`_load_remote_upload_manifest_index`、`_build_upload_manifest_payload`、`_remote_file_exists`

### 类 `_ArchiveUploadLayout`
- 可见性：内部类
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:53`
- 作用：压缩包上传路由信息。
- 装饰器：`dataclass(frozen=True, slots=True)`
- 字段：
| 字段 | 类型 | 默认值 |
| --- | --- | --- |
| `remote_name` | `str` | `-` |
| `remote_relative_path` | `str` | `-` |
| `remote_path` | `str` | `-` |
| `target_group` | `str` | `-` |
| `resource_type` | `str` | `-` |
| `entity_key` | `str` | `-` |
- 方法数量：0

### 类 `_IndexedArchiveMetadata`
- 可见性：内部类
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:64`
- 作用：远端索引条目解析结果。
- 装饰器：`dataclass(frozen=True, slots=True)`
- 字段：
| 字段 | 类型 | 默认值 |
| --- | --- | --- |
| `remote_path` | `str` | `-` |
| `remote_name` | `str` | `-` |
| `game_version` | `str | None` | `-` |
| `target_group` | `str | None` | `-` |
| `resource_type` | `str | None` | `-` |
| `entity_key` | `str | None` | `-` |
| `is_old_bucket` | `bool` | `-` |
- 方法数量：0

### 函数 `_pack_unpacked_outputs`

#### `_pack_unpacked_outputs(config: PipelineConfig, game_version: str) -> tuple[Path, ...]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:75`
- 作用：将当前版本解包产物按目录批量打包。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `_resolve_pack_extra_files` 并写入 `extra_files`。
  4. 调用 `_resolve_pack_archive_type` 并写入 `archive_audio_type`。
  5. 根据条件分支选择不同处理路径。
  6. 根据条件分支选择不同处理路径。
  7. 遍历集合并执行批量处理。
  8. 返回 `tuple(sorted(archives, key=lambda path: path.as_posix().casefold()))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `config` | `PipelineConfig` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[Path, ...]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_resolve_pack_extra_files`、`_resolve_pack_archive_type`、`tuple`、`version_audio_dir.is_dir`、`logger.warning`、`_resolve_package_output_root`、`logger.info`、`pack_all`、`archives.extend`、`sorted`、`join`、`target_dir.is_dir`、`len`、`str`、`casefold`、`path.as_posix`

### 函数 `_preflight_remote_upload_index`

#### `_preflight_remote_upload_index(config: PipelineConfig, package_root: Path, allow_missing_remote_index: bool) -> dict[str, dict[str, object]]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:131`
- 作用：在主线更新确认阶段预检远端上传索引。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 调用 `BaiduCredentials` 并写入 `credentials`。
  3. 调用 `resolve_token_store` 并写入 `token_store`。
  4. 调用 `BaiduPanClient` 并写入 `client`。
  5. 使用异常处理分支兜底失败路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `config` | `PipelineConfig` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `package_root` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `allow_missing_remote_index` | `bool` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, dict[str, object]]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`BaiduCredentials`、`resolve_token_store`、`BaiduPanClient`、`ValueError`、`_initialize_remote_upload_layout`、`_load_remote_upload_manifest_index`、`_clone_upload_manifest_index`、`client.close`、`logger.info`、`len`

### 函数 `_upload_archives_and_manifest`

#### `_upload_archives_and_manifest(config: PipelineConfig, game_version: str, archives: tuple[Path, ...], allow_missing_remote_index: bool = True, run_record_collector: list[dict[str, object]] | None = None, preloaded_remote_index: dict[str, dict[str, object]] | None = None, pending_manifest_sync_queue_file: Path | None = None) -> Path | None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:171`
- 作用：将打包产物上传到百度网盘，并同步本次上传清单。
- 实现方式：
  1. 执行 `logger.debug` 触发副作用逻辑。
  2. 根据条件分支选择不同处理路径。
  3. 根据条件分支选择不同处理路径。
  4. 调用 `_resolve_package_output_root` 并写入 `package_root`。
  5. 调用 `BaiduCredentials` 并写入 `credentials`。
  6. 调用 `resolve_token_store` 并写入 `token_store`。
  7. 调用 `BaiduPanClient` 并写入 `client`。
  8. 使用异常处理分支兜底失败路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `config` | `PipelineConfig` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `archives` | `tuple[Path, ...]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `allow_missing_remote_index` | `bool` | `True` | `positional_or_keyword` | （Docstring 未提供） |
| `run_record_collector` | `list[dict[str, object]] | None` | `None` | `positional_or_keyword` | （Docstring 未提供） |
| `preloaded_remote_index` | `dict[str, dict[str, object]] | None` | `None` | `positional_or_keyword` | （Docstring 未提供） |
| `pending_manifest_sync_queue_file` | `Path | None` | `None` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`Path | None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`logger.debug`、`_resolve_package_output_root`、`BaiduCredentials`、`resolve_token_store`、`BaiduPanClient`、`len`、`logger.warning`、`ValueError`、`_initialize_remote_upload_layout`、`_resolve_upload_remote_index`、`_current_utc_timestamp`、`_resolve_default_upload_resource_type`、`_process_archives_upload`、`_finalize_upload_manifest`、`client.close`

### 函数 `_resolve_upload_remote_index`

#### `_resolve_upload_remote_index(client: BaiduPanClient, package_root: Path, allow_missing_remote_index: bool, preloaded_remote_index: dict[str, dict[str, object]] | None) -> dict[str, dict[str, object]]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:249`
- 作用：解析本次上传使用的远端索引快照。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 执行 `logger.debug` 触发副作用逻辑。
  3. 调用 `_load_remote_upload_manifest_index` 并写入 `remote_index`。
  4. 执行 `logger.debug` 触发副作用逻辑。
  5. 返回 `remote_index` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `client` | `BaiduPanClient` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `package_root` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `allow_missing_remote_index` | `bool` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `preloaded_remote_index` | `dict[str, dict[str, object]] | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, dict[str, object]]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`logger.debug`、`_load_remote_upload_manifest_index`、`_clone_upload_manifest_index`、`len`

### 函数 `_clone_upload_manifest_index`

#### `_clone_upload_manifest_index(source_index: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:270`
- 作用：复制上传索引，避免调用方状态被就地污染。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 返回 `cloned` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `source_index` | `dict[str, dict[str, object]]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, dict[str, object]]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`source_index.items`、`dict`

### 函数 `_process_archives_upload`

#### `_process_archives_upload(client: BaiduPanClient, archives: tuple[Path, ...], remote_dir: str, game_version: str, remote_index: dict[str, dict[str, object]], executed_at: str, default_resource_type: str) -> tuple[list[dict[str, object]], bool]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:280`
- 作用：处理一批压缩包上传并更新内存索引。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 返回 `(run_entries, has_index_changes)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `client` | `BaiduPanClient` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `archives` | `tuple[Path, ...]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_dir` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_index` | `dict[str, dict[str, object]]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `executed_at` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `default_resource_type` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[list[dict[str, object]], bool]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_build_archive_upload_layout`、`_ensure_remote_directory`、`_archive_remote_old_versions`、`remote_index.get`、`_remote_file_exists`、`_calculate_sha256`、`logger.debug`、`client.upload_file`、`run_entries.append`、`archive.is_file`、`FileNotFoundError`、`run_entries.extend`、`remote_path.casefold`、`_is_same_index_entry`、`RuntimeError`、`archive.stat`、`logger.info`、`isinstance`、`sorted`、`type`

### 函数 `_finalize_upload_manifest`

#### `_finalize_upload_manifest(client: BaiduPanClient, manifest_file: Path, readable_manifest_file: Path, game_version: str, remote_dir: str, remote_index: dict[str, dict[str, object]], run_entries: list[dict[str, object]], has_index_changes: bool, executed_at: str, run_record_collector: list[dict[str, object]] | None = None, refresh_remote_index_before_upload: bool = False, pending_manifest_sync_queue_file: Path | None = None) -> Path`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:397`
- 作用：落地本地索引文件并按需回传到远端。
- 实现方式：
  1. 调用 `_clone_upload_manifest_index` 并写入 `effective_remote_index`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `_build_upload_manifest_payload` 并写入 `manifest_payload`。
  4. 执行 `manifest_file.parent.mkdir` 触发副作用逻辑。
  5. 执行 `manifest_file.write_text` 触发副作用逻辑。
  6. 执行 `readable_manifest_file.write_text` 触发副作用逻辑。
  7. 根据条件分支选择不同处理路径。
  8. 根据条件分支选择不同处理路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `client` | `BaiduPanClient` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `manifest_file` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `readable_manifest_file` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_dir` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_index` | `dict[str, dict[str, object]]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `run_entries` | `list[dict[str, object]]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `has_index_changes` | `bool` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `executed_at` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `run_record_collector` | `list[dict[str, object]] | None` | `None` | `positional_or_keyword` | （Docstring 未提供） |
| `refresh_remote_index_before_upload` | `bool` | `False` | `positional_or_keyword` | （Docstring 未提供） |
| `pending_manifest_sync_queue_file` | `Path | None` | `None` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`Path`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_clone_upload_manifest_index`、`_build_upload_manifest_payload`、`manifest_file.parent.mkdir`、`manifest_file.write_text`、`readable_manifest_file.write_text`、`json.dumps`、`_build_readable_upload_manifest_content`、`run_record_collector.extend`、`logger.debug`、`range`、`logger.info`、`_load_remote_upload_manifest_index`、`_merge_remote_index_for_finalize`、`logger.error`、`_enqueue_pending_manifest_sync`、`logger.warning`、`client.upload_file`、`time.sleep`

### 函数 `_merge_remote_index_for_finalize`

#### `_merge_remote_index_for_finalize(latest_remote_index: dict[str, dict[str, object]], working_remote_index: dict[str, dict[str, object]], run_entries: list[dict[str, object]]) -> dict[str, dict[str, object]]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:491`
- 作用：将本次运行变更叠加到最新远端索引，降低并发覆盖风险。
- 实现方式：
  1. 调用 `_clone_upload_manifest_index` 并写入 `merged`。
  2. 调用 `_collect_remote_index_mutation_keys` 并写入 `upsert_keys, removed_keys`。
  3. 遍历集合并执行批量处理。
  4. 遍历集合并执行批量处理。
  5. 返回 `merged` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `latest_remote_index` | `dict[str, dict[str, object]]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `working_remote_index` | `dict[str, dict[str, object]]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `run_entries` | `list[dict[str, object]]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, dict[str, object]]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_clone_upload_manifest_index`、`_collect_remote_index_mutation_keys`、`merged.pop`、`working_remote_index.get`、`dict`

### 函数 `_collect_remote_index_mutation_keys`

#### `_collect_remote_index_mutation_keys(run_entries: list[dict[str, object]]) -> tuple[set[str], set[str]]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:509`
- 作用：提取本次运行对远端索引的增改键和删除键。
- 实现方式：
  1. 调用 `set` 并写入 `upsert_keys`。
  2. 调用 `set` 并写入 `removed_keys`。
  3. 遍历集合并执行批量处理。
  4. 返回 `(upsert_keys, removed_keys)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `run_entries` | `list[dict[str, object]]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[set[str], set[str]]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`set`、`entry.get`、`isinstance`、`remote_path_obj.strip`、`upsert_keys.add`、`source_remote_path_obj.strip`、`removed_keys.add`、`casefold`、`replace`

### 函数 `_retry_pending_manifest_sync_queue`

#### `_retry_pending_manifest_sync_queue(config: PipelineConfig, queue_file: Path) -> None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:525`
- 作用：重试历史失败的索引回传任务（失败不阻断主流程）。
- 实现方式：
  1. 调用 `_load_pending_manifest_sync_entries` 并写入 `pending_entries`。
  2. 根据条件分支选择不同处理路径。
  3. 根据条件分支选择不同处理路径。
  4. 执行 `logger.info` 触发副作用逻辑。
  5. 调用 `resolve_token_store` 并写入 `token_store`。
  6. 遍历集合并执行批量处理。
  7. 执行 `_save_pending_manifest_sync_entries` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `config` | `PipelineConfig` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `queue_file` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_load_pending_manifest_sync_entries`、`logger.info`、`resolve_token_store`、`_save_pending_manifest_sync_entries`、`logger.warning`、`len`、`entry.get`、`resolve`、`BaiduPanClient`、`client.upload_file`、`client.close`、`isinstance`、`expanduser`、`manifest_file.is_file`、`readable_manifest_file.is_file`、`BaiduCredentials`、`dict`、`str`、`_current_utc_timestamp`、`remaining_entries.append`

### 函数 `_enqueue_pending_manifest_sync`

#### `_enqueue_pending_manifest_sync(queue_file: Path | None, manifest_file: Path, readable_manifest_file: Path, remote_dir: str, error: Exception) -> None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:601`
- 作用：将索引回传失败任务追加到本地待重试队列。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 调用 `_load_pending_manifest_sync_entries` 并写入 `pending_entries`。
  3. 调用 `casefold` 并写入 `entry_key`。
  4. 遍历集合并执行批量处理。
  5. 执行 `next_entries.append` 触发副作用逻辑。
  6. 执行 `_save_pending_manifest_sync_entries` 触发副作用逻辑。
  7. 执行 `logger.warning` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `queue_file` | `Path | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `manifest_file` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `readable_manifest_file` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_dir` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `error` | `Exception` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_load_pending_manifest_sync_entries`、`casefold`、`next_entries.append`、`_save_pending_manifest_sync_entries`、`logger.warning`、`entry.get`、`str`、`_current_utc_timestamp`、`isinstance`、`resolve`、`remote_dir.strip`、`as_posix`、`remote_dir_obj.strip`、`manifest_file.expanduser`、`readable_manifest_file.expanduser`、`expanduser`、`Path`

### 函数 `_load_pending_manifest_sync_entries`

#### `_load_pending_manifest_sync_entries(queue_file: Path) -> list[dict[str, object]]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:646`
- 作用：读取待重试索引回传队列。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 使用异常处理分支兜底失败路径。
  3. 根据条件分支选择不同处理路径。
  4. 遍历集合并执行批量处理。
  5. 返回 `entries` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `queue_file` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`list[dict[str, object]]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`queue_file.is_file`、`json.loads`、`isinstance`、`queue_file.read_text`、`logger.warning`、`entries.append`、`dict`

### 函数 `_save_pending_manifest_sync_entries`

#### `_save_pending_manifest_sync_entries(queue_file: Path, entries: list[dict[str, object]]) -> None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:664`
- 作用：保存待重试索引回传队列。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 执行 `queue_file.parent.mkdir` 触发副作用逻辑。
  3. 执行 `queue_file.write_text` 触发副作用逻辑。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `queue_file` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `entries` | `list[dict[str, object]]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`queue_file.parent.mkdir`、`queue_file.write_text`、`queue_file.unlink`、`json.dumps`

### 函数 `_resolve_package_output_root`

#### `_resolve_package_output_root(config: PipelineConfig, game_version: str) -> Path`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:679`
- 作用：解析当前版本打包产物根目录。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 返回 `config.output_path / 'packages' / game_version` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `config` | `PipelineConfig` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`Path`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：未识别到显式函数调用。

### 函数 `_resolve_pack_extra_files`

#### `_resolve_pack_extra_files(config: PipelineConfig) -> tuple[Path, ...]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:686`
- 作用：解析打包附加文件列表。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 遍历集合并执行批量处理。
  3. 返回 `tuple()` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `config` | `PipelineConfig` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[Path, ...]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`tuple`、`candidate_dirs.append`、`resolve`、`resolved_dir.is_dir`、`file_path.is_file`、`directory.expanduser`、`files.append`

### 函数 `_resolve_pack_archive_type`

#### `_resolve_pack_archive_type(config: PipelineConfig) -> str | None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:708`
- 作用：解析压缩包命名的类型后缀。
- 实现方式：
  1. 调用 `sorted` 并写入 `normalized_types`。
  2. 根据条件分支选择不同处理路径。
  3. 返回 `None` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `config` | `PipelineConfig` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str | None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`sorted`、`len`、`upper`、`item.strip`、`isinstance`

### 函数 `_resolve_default_upload_resource_type`

#### `_resolve_default_upload_resource_type(config: PipelineConfig) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:722`
- 作用：解析上传阶段默认资源类型目录。
- 实现方式：
  1. 调用 `_resolve_pack_archive_type` 并写入 `archive_type`。
  2. 根据条件分支选择不同处理路径。
  3. 遍历集合并执行批量处理。
  4. 返回 `RESOURCE_TYPE_BUCKETS[0]` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `config` | `PipelineConfig` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_resolve_pack_archive_type`、`upper`、`isinstance`、`item.strip`

### 函数 `_build_archive_upload_layout`

#### `_build_archive_upload_layout(archive: Path, remote_dir: str, default_resource_type: str) -> _ArchiveUploadLayout`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:736`
- 作用：解析单个压缩包的远端目录路由。
- 实现方式：
  1. 调用 `_resolve_archive_target_group` 并写入 `target_group`。
  2. 调用 `_parse_archive_file_name` 并写入 `entity_key, _, archive_resource_type`。
  3. 返回 `_ArchiveUploadLayout(remote_name=archive.name, remote_relative_path=remote_relative_path, remote_path=_join_remote_file_path(remote_dir=remote_dir, remote_name=remote_relative_path), target_group=target_group, resource_type=resource_type, entity_key=entity_key)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `archive` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_dir` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `default_resource_type` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`_ArchiveUploadLayout`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_resolve_archive_target_group`、`_parse_archive_file_name`、`_ArchiveUploadLayout`、`_join_remote_file_path`

### 函数 `_resolve_archive_target_group`

#### `_resolve_archive_target_group(archive: Path) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:756`
- 作用：从本地路径解析上传目标分组（champions/maps）。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 返回 `'champions'` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `archive` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`reversed`、`part.casefold`

### 函数 `_parse_archive_file_name`

#### `_parse_archive_file_name(archive_name: str) -> tuple[str, str | None, str | None]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:765`
- 作用：解析压缩包文件名中的实体名、版本和资源类型。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 调用 `stem.strip` 并写入 `normalized_stem`。
  3. 根据条件分支选择不同处理路径。
  4. 调用 `normalized_stem.rsplit` 并写入 `parts`。
  5. 根据条件分支选择不同处理路径。
  6. 调用 `strip` 并写入 `entity_key`。
  7. 调用 `upper` 并写入 `parsed_resource_type`。
  8. 根据条件分支选择不同处理路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `archive_name` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[str, str | None, str | None]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`endswith`、`stem.strip`、`normalized_stem.rsplit`、`strip`、`upper`、`len`、`archive_name.casefold`

### 函数 `_archive_remote_old_versions`

#### `_archive_remote_old_versions(client: BaiduPanClient, remote_dir: str, remote_index: dict[str, dict[str, object]], layout: _ArchiveUploadLayout, expected_game_version: str, executed_at: str) -> list[dict[str, object]]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:789`
- 作用：将同实体旧版本远端文件归档到 `OLD/<target_group>/`。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 返回 `archived_entries` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `client` | `BaiduPanClient` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_dir` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_index` | `dict[str, dict[str, object]]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `layout` | `_ArchiveUploadLayout` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `expected_game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `executed_at` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`list[dict[str, object]]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`tuple`、`remote_index.items`、`_resolve_index_entry_metadata`、`_ensure_remote_directory`、`client.move_path`、`_join_remote_file_path`、`dict`、`updated_entry.update`、`remote_index.pop`、`logger.info`、`archived_entries.append`、`metadata.remote_path.casefold`、`layout.remote_path.casefold`、`archived_remote_path.casefold`

### 函数 `_resolve_index_entry_metadata`

#### `_resolve_index_entry_metadata(entry: dict[str, object], remote_dir: str) -> _IndexedArchiveMetadata`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:862`
- 作用：解析远端索引条目的路由元数据。
- 实现方式：
  1. 调用 `entry.get` 并写入 `remote_path_value`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `replace` 并写入 `remote_path`。
  4. 调用 `strip` 并写入 `remote_name`。
  5. 调用 `_build_relative_remote_path` 并写入 `raw_relative`。
  6. 调用 `_parse_archive_file_name` 并写入 `parsed_entity_key, parsed_version, parsed_resource_type`。
  7. 调用 `entry.get` 并写入 `entry_game_version`。
  8. 调用 `entry.get` 并写入 `entry_resource_type`。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `entry` | `dict[str, object]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_dir` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`_IndexedArchiveMetadata`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`entry.get`、`replace`、`strip`、`_build_relative_remote_path`、`_parse_archive_file_name`、`_IndexedArchiveMetadata`、`ValueError`、`upper`、`casefold`、`entry_game_version.strip`、`isinstance`、`entry_resource_type.strip`、`entry_entity_key.strip`、`entry_target_group.strip`、`remote_path_value.strip`、`str`、`raw_relative.split`、`len`、`Path`

### 函数 `_build_relative_remote_path`

#### `_build_relative_remote_path(remote_path: str, remote_dir: str) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:916`
- 作用：将绝对远端路径转换为工作目录下相对路径。
- 实现方式：
  1. 调用 `replace` 并写入 `normalized_remote_path`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `strip` 并写入 `normalized_dir`。
  4. 根据条件分支选择不同处理路径。
  5. 根据条件分支选择不同处理路径。
  6. 根据条件分支选择不同处理路径。
  7. 返回 `normalized_remote_path.lstrip('/')` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `remote_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_dir` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`replace`、`strip`、`startswith`、`normalized_remote_path.lstrip`、`normalized_remote_path.startswith`、`casefold`、`normalized_remote_path.casefold`、`normalized_work_dir.casefold`、`remote_path.strip`、`remote_dir.strip`、`len`

### 函数 `_ensure_remote_directory`

#### `_ensure_remote_directory(client: BaiduPanClient, relative_dir: str) -> None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:932`
- 作用：确保远端目录存在（按层创建）。
- 实现方式：
  1. 调用 `strip` 并写入 `normalized`。
  2. 根据条件分支选择不同处理路径。
  3. 遍历集合并执行批量处理。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `client` | `BaiduPanClient` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `relative_dir` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`strip`、`normalized.split`、`_remote_file_exists`、`client.create_directory`、`replace`、`relative_dir.strip`

### 函数 `_initialize_remote_upload_layout`

#### `_initialize_remote_upload_layout(client: BaiduPanClient) -> None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:946`
- 作用：初始化远端目录结构。
- 实现方式：
  1. 执行 `client.create_directory` 触发副作用逻辑。
  2. 遍历集合并执行批量处理。
  3. 遍历集合并执行批量处理。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `client` | `BaiduPanClient` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`client.create_directory`、`_ensure_remote_directory`

### 函数 `_build_readable_upload_manifest_content`

#### `_build_readable_upload_manifest_content(index: dict[str, dict[str, object]], game_version: str, executed_at: str, remote_dir: str) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:958`
- 作用：构建给人类阅读和搜索的上传索引文本。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 根据条件分支选择不同处理路径。
  3. 执行 `lines.extend` 触发副作用逻辑。
  4. 根据条件分支选择不同处理路径。
  5. 执行 `lines.append` 触发副作用逻辑。
  6. 返回 `'\n'.join(lines)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `index` | `dict[str, dict[str, object]]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `executed_at` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_dir` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`sorted`、`lines.extend`、`lines.append`、`join`、`index.values`、`_resolve_index_entry_metadata`、`archived_lines.append`、`active_lines.append`、`casefold`、`len`、`str`、`item.get`

### 函数 `_build_upload_database_payload`

#### `_build_upload_database_payload(index: dict[str, dict[str, object]], remote_dir: str) -> dict[str, dict[str, object]]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:1014`
- 作用：将远端索引聚合为实体维度数据库视图。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 遍历集合并执行批量处理。
  3. 返回 `normalized_grouped` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `index` | `dict[str, dict[str, object]]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_dir` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, dict[str, object]]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`sorted`、`grouped.items`、`index.values`、`_resolve_index_entry_metadata`、`casefold`、`grouped.get`、`versions.append`、`value.get`、`next`、`isinstance`、`latest_version.get`、`_parse_game_version_sort_key`、`reversed`、`str`、`bool`、`item.get`

### 函数 `_write_and_upload_update_log_files`

#### `_write_and_upload_update_log_files(config: PipelineConfig, decision: object, game_version: str, target_entities: object, targets: object, secondary_filter_result: object | None, upload_run_records: list[dict[str, object]]) -> tuple[Path, Path]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:1082`
- 作用：生成并上传每次 diff 的详细更新日志（JSON + 文本）。
- 实现方式：
  1. 调用 `_current_utc_timestamp` 并写入 `executed_at`。
  2. 调用 `getattr` 并写入 `previous_version_obj`。
  3. 执行 `report_dir.mkdir` 触发副作用逻辑。
  4. 调用 `_build_update_log_payload` 并写入 `payload`。
  5. 执行 `json_file.write_text` 触发副作用逻辑。
  6. 执行 `text_file.write_text` 触发副作用逻辑。
  7. 根据条件分支选择不同处理路径。
  8. 调用 `BaiduCredentials` 并写入 `credentials`。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `config` | `PipelineConfig` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `decision` | `object` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `target_entities` | `object` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `targets` | `object` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `secondary_filter_result` | `object | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `upload_run_records` | `list[dict[str, object]]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[Path, Path]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`_current_utc_timestamp`、`getattr`、`report_dir.mkdir`、`_build_update_log_payload`、`json_file.write_text`、`text_file.write_text`、`BaiduCredentials`、`resolve_token_store`、`BaiduPanClient`、`isinstance`、`strip`、`json.dumps`、`_build_update_log_text`、`ValueError`、`_ensure_remote_directory`、`client.upload_file`、`client.close`、`replace`、`str`、`executed_at.replace`

### 函数 `_build_update_log_payload`

#### `_build_update_log_payload(decision: object, game_version: str, executed_at: str, target_entities: object, targets: object, secondary_filter_result: object | None, upload_run_records: list[dict[str, object]]) -> dict[str, object]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:1149`
- 作用：构建单次 diff 的结构化更新日志。
- 实现方式：
  1. 调用 `getattr` 并写入 `wad_changes_obj`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `sum` 并写入 `uploaded_count`。
  4. 调用 `sum` 并写入 `skipped_count`。
  5. 调用 `sum` 并写入 `archived_count`。
  6. 调用 `getattr` 并写入 `previous_state_obj`。
  7. 调用 `getattr` 并写入 `previous_version`。
  8. 根据条件分支选择不同处理路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `decision` | `object` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `executed_at` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `target_entities` | `object` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `targets` | `object` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `secondary_filter_result` | `object | None` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `upload_run_records` | `list[dict[str, object]]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, object]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`getattr`、`sum`、`list`、`str`、`tuple`、`filter_decisions.append`、`len`、`bool`、`item.get`

### 函数 `_load_remote_upload_manifest_index`

#### `_load_remote_upload_manifest_index(client: BaiduPanClient, package_root: Path, allow_missing_remote_index: bool) -> dict[str, dict[str, object]]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:1235`
- 作用：读取远端上传索引并构建内存查询表。
- 实现方式：
  1. 使用异常处理分支兜底失败路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `client` | `BaiduPanClient` | `-` | `positional_or_keyword` | 百度网盘客户端。 |
| `package_root` | `Path` | `-` | `positional_or_keyword` | 当前版本打包根目录，用于临时落地远端索引文件。 |
| `allow_missing_remote_index` | `bool` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, dict[str, object]]`
- 返回说明：以 `remote_path.casefold()` 为键的索引字典。
- 可能抛出：
  - `ValueError`
  - `RuntimeError`
- 关键调用：`payload.get`、`_build_upload_manifest_index`、`temp_file.unlink`、`client.download_file`、`json.loads`、`isinstance`、`ValueError`、`logger.info`、`temp_file.read_text`、`RuntimeError`

### 函数 `_build_upload_manifest_payload`

#### `_build_upload_manifest_payload(game_version: str, index: dict[str, dict[str, object]], run_entries: list[dict[str, object]], executed_at: str, remote_dir: str) -> dict[str, object]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:1291`
- 作用：构建上传索引快照。
- 实现方式：
  1. 调用 `tuple` 并写入 `index_entries`。
  2. 调用 `_build_upload_database_payload` 并写入 `database`。
  3. 调用 `sum` 并写入 `uploaded_count`。
  4. 调用 `sum` 并写入 `skipped_count`。
  5. 调用 `sum` 并写入 `archived_count`。
  6. 返回 `{'schema_version': UPLOAD_MANIFEST_SCHEMA_VERSION, 'updated_at': executed_at, 'entry_count': len(index_entries), 'entries': index_entries, 'database_schema_version': UPLOAD_DATABASE_SCHEMA_VERSION, 'database_entry_count': len(database), 'database': database, 'last_run': {'game_version': game_version, 'executed_at': executed_at, 'archive_count': len(run_entries), 'uploaded_count': uploaded_count, 'skipped_count': skipped_count, 'archived_count': archived_count, 'entries': run_entries}}` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `index` | `dict[str, dict[str, object]]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `run_entries` | `list[dict[str, object]]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `executed_at` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_dir` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, object]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`tuple`、`_build_upload_database_payload`、`sum`、`sorted`、`len`、`index.values`、`casefold`、`entry.get`、`str`

### 函数 `_remote_file_exists`

#### `_remote_file_exists(client: BaiduPanClient, remote_path: str) -> bool`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/upload.py:1329`
- 作用：判断远端路径是否已存在。
- 实现方式：
  1. 使用异常处理分支兜底失败路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `client` | `BaiduPanClient` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_path` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`bool`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`client.get_path_entry`

## 模块 `src/rift_audio_pipeline/pipeline/utils.py`
- 模块说明：Pipeline 纯工具函数集合。
- 类数量：0
- 函数/方法数量：13
- 函数索引：`_parse_game_version_sort_key`、`_build_update_log_text`、`_calculate_sha256`、`_build_upload_manifest_index`、`_join_remote_file_path`、`_is_same_index_entry`、`_current_utc_timestamp`、`_coerce_non_negative_int`、`_cleanup_simulated_runtime_files`、`_merge_runtime_wad_paths`、`_normalize_pipeline_game_version`、`_build_runtime_wad_paths_from_manifest_paths`、`_cleanup_version_audio_outputs`

### 函数 `_parse_game_version_sort_key`

#### `_parse_game_version_sort_key(game_version: str, fallback: str) -> tuple[int, ...]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/utils.py:12`
- 作用：将版本号解析为可排序键。
- 实现方式：
  1. 调用 `game_version.strip` 并写入 `normalized`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `normalized.split` 并写入 `parts`。
  4. 遍历集合并执行批量处理。
  5. 在循环中持续处理直到满足退出条件。
  6. 根据条件分支选择不同处理路径。
  7. 返回 `tuple(parsed)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `fallback` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[int, ...]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`game_version.strip`、`normalized.split`、`all`、`tuple`、`part.isdigit`、`len`、`parsed.append`、`sum`、`int`、`ord`、`fallback.casefold`

### 函数 `_build_update_log_text`

#### `_build_update_log_text(payload: dict[str, object]) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/utils.py:33`
- 作用：将结构化更新日志渲染为人类可读文本。
- 实现方式：
  1. 调用 `payload.get` 并写入 `changed_entities_obj`。
  2. 调用 `payload.get` 并写入 `wad_changes_obj`。
  3. 调用 `payload.get` 并写入 `upload_summary_obj`。
  4. 调用 `payload.get` 并写入 `secondary_filter_obj`。
  5. 根据条件分支选择不同处理路径。
  6. 执行 `lines.extend` 触发副作用逻辑。
  7. 调用 `upload_summary.get` 并写入 `entries_obj`。
  8. 根据条件分支选择不同处理路径。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `payload` | `dict[str, object]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`payload.get`、`isinstance`、`lines.extend`、`upload_summary.get`、`lines.append`、`join`、`secondary_filter_obj.get`、`len`、`wad_changes.get`、`changed_entities.get`、`item.get`

### 函数 `_calculate_sha256`

#### `_calculate_sha256(file_path: Path) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/utils.py:107`
- 作用：计算文件 SHA256。
- 实现方式：
  1. 调用 `hashlib.sha256` 并写入 `digest`。
  2. 在上下文管理器中执行资源操作。
  3. 返回 `digest.hexdigest()` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `file_path` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`hashlib.sha256`、`digest.hexdigest`、`file_path.open`、`iter`、`digest.update`、`stream.read`

### 函数 `_build_upload_manifest_index`

#### `_build_upload_manifest_index(entries: object) -> dict[str, dict[str, object]]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/utils.py:117`
- 作用：将远端索引条目转换为高效查询结构。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 遍历集合并执行批量处理。
  3. 返回 `index` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `entries` | `object` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`dict[str, dict[str, object]]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`isinstance`、`ValueError`、`raw_entry.get`、`replace`、`strip`、`_coerce_non_negative_int`、`sha256_obj.strip`、`lower`、`remote_path.casefold`、`remote_path_obj.strip`、`str`、`field_value.strip`、`Path`

### 函数 `_join_remote_file_path`

#### `_join_remote_file_path(remote_dir: str, remote_name: str) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/utils.py:159`
- 作用：拼接远端目录和文件名。
- 实现方式：
  1. 调用 `lstrip` 并写入 `normalized_name`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `strip` 并写入 `normalized_dir`。
  4. 根据条件分支选择不同处理路径。
  5. 返回 `f'/{normalized_dir}/{normalized_name}'` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `remote_dir` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `remote_name` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`lstrip`、`strip`、`ValueError`、`replace`、`remote_name.strip`、`remote_dir.strip`

### 函数 `_is_same_index_entry`

#### `_is_same_index_entry(entry: dict[str, object], expected_remote_name: str, expected_game_version: str) -> bool`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/utils.py:172`
- 作用：按文件名与版本号判断索引条目是否匹配。
- 实现方式：
  1. 调用 `entry.get` 并写入 `indexed_name`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `entry.get` 并写入 `indexed_version`。
  4. 根据条件分支选择不同处理路径。
  5. 根据条件分支选择不同处理路径。
  6. 返回 `indexed_version.strip() == expected_game_version` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `entry` | `dict[str, object]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `expected_remote_name` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `expected_game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`bool`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`entry.get`、`isinstance`、`indexed_name.strip`、`indexed_version.strip`

### 函数 `_current_utc_timestamp`

#### `_current_utc_timestamp() -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/utils.py:192`
- 作用：返回 UTC ISO-8601 时间戳。
- 实现方式：
  1. 返回 `datetime.now(tz=timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')` 作为结果。
- 参数：
参数：无。
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`replace`、`isoformat`、`datetime.now`

### 函数 `_coerce_non_negative_int`

#### `_coerce_non_negative_int(value: object) -> int | None`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/utils.py:198`
- 作用：将对象转换为非负整数。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 根据条件分支选择不同处理路径。
  3. 根据条件分支选择不同处理路径。
  4. 返回 `None` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `value` | `object` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`int | None`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`isinstance`、`value.strip`、`int`

### 函数 `_cleanup_simulated_runtime_files`

#### `_cleanup_simulated_runtime_files(runtime_game_path: Path, runtime_download_dir: Path) -> tuple[int, int]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/utils.py:217`
- 作用：清理模拟目录下临时 WAD 与下载缓存。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 根据条件分支选择不同处理路径。
  3. 根据条件分支选择不同处理路径。
  4. 返回 `(removed_runtime_wads, removed_download_cache)` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `runtime_game_path` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `runtime_download_dir` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[int, int]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`runtime_download_dir.exists`、`directory.rglob`、`resolve`、`runtime_download_dir.rglob`、`shutil.rmtree`、`directory.is_dir`、`item.is_file`、`endswith`、`item.unlink`、`runtime_download_dir.expanduser`、`runtime_game_path.expanduser`、`item.name.casefold`

### 函数 `_merge_runtime_wad_paths`

#### `_merge_runtime_wad_paths(*groups: tuple[str, ...]) -> tuple[str, ...]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/utils.py:248`
- 作用：合并运行时 WAD 路径并去重排序。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 返回 `tuple(sorted(deduped.values(), key=str.casefold))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `*groups` | `tuple[str, ...]` | `-` | `var_positional` | （Docstring 未提供） |
- 返回类型：`tuple[str, ...]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`tuple`、`sorted`、`replace`、`deduped.setdefault`、`deduped.values`、`normalized.casefold`、`path.strip`

### 函数 `_normalize_pipeline_game_version`

#### `_normalize_pipeline_game_version(game_version: str) -> str`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/utils.py:261`
- 作用：将版本号标准化为 `major.minor`，用于本地路径与打包命名。
- 实现方式：
  1. 调用 `game_version.strip` 并写入 `normalized`。
  2. 根据条件分支选择不同处理路径。
  3. 调用 `normalized.split` 并写入 `parts`。
  4. 根据条件分支选择不同处理路径。
  5. 返回 `normalized` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `game_version` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`str`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`game_version.strip`、`normalized.split`、`isdigit`、`len`

### 函数 `_build_runtime_wad_paths_from_manifest_paths`

#### `_build_runtime_wad_paths_from_manifest_paths(manifest_paths: tuple[str, ...], region: str, include_root_wad: bool = True) -> tuple[str, ...]`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/utils.py:273`
- 作用：将 manifest WAD 路径转换为运行时根/区域路径集合。
- 实现方式：
  1. 遍历集合并执行批量处理。
  2. 返回 `tuple(sorted(runtime_paths.values(), key=str.casefold))` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `manifest_paths` | `tuple[str, ...]` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `region` | `str` | `-` | `positional_or_keyword` | （Docstring 未提供） |
| `include_root_wad` | `bool` | `True` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`tuple[str, ...]`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`tuple`、`replace`、`normalized.startswith`、`runtime_paths.setdefault`、`normalized.casefold`、`sorted`、`normalized.removeprefix`、`region_runtime_path.casefold`、`lowered.endswith`、`runtime_paths.values`、`raw_path.strip`、`region_suffix.casefold`、`root_runtime_path.casefold`、`len`

### 函数 `_cleanup_version_audio_outputs`

#### `_cleanup_version_audio_outputs(version_audio_dir: Path) -> int`
- 可见性：内部函数
- 源码位置：`src/rift_audio_pipeline/pipeline/utils.py:303`
- 作用：清理已打包版本的音频目录，降低上传阶段磁盘占用。
- 实现方式：
  1. 根据条件分支选择不同处理路径。
  2. 遍历集合并执行批量处理。
  3. 执行 `shutil.rmtree` 触发副作用逻辑。
  4. 返回 `removed_files` 作为结果。
- 参数：
| 参数 | 类型 | 默认值 | 参数类别 | 说明 |
| --- | --- | --- | --- | --- |
| `version_audio_dir` | `Path` | `-` | `positional_or_keyword` | （Docstring 未提供） |
- 返回类型：`int`
- 返回说明：（Docstring 未提供）
- 可能抛出：未显式声明。
- 关键调用：`version_audio_dir.rglob`、`shutil.rmtree`、`version_audio_dir.is_dir`、`item.is_file`

