# 当前 Plane 必需接口清单

> 状态：2026-03-12 当前实现真相源  
> 目的：只记录 **当前仓库真实运行路径** 对 plane 的最小必需接口、请求参数、响应字段与调用来源。  
> 适用范围：`job_runner -> runtime_init -> log_relay -> upload_worker -> finalize_worker` 当前主路径，以及本地 `rift_localdev.plane.mock_server` / `mock_smoke` / `e2e_simulation` 联调。

---

## 1. 先说结论

在“完整 control-plane 集成模式”下，当前 plane 需要实现的业务接口一共 6 个：

1. `GET /api/baidu/token`
2. `POST /api/pipeline/bootstrap`
3. `POST /api/pipeline/runs/{run_id}/heartbeat`
4. `POST /api/pipeline/runs/{run_id}/logs`
5. `POST /api/pipeline/runs/{run_id}/logs/finalize`
6. `POST /api/pipeline/runs/{run_id}/report`

另外建议保留：

- `GET /healthz`

这是本地 mock plane 当前已经实现的健康检查入口，便于本地联调和进程存活探测，但不是 Python 执行端的业务强依赖。

若 workflow / job runner 明确不提供 `control_plane_base_url`，当前运行会进入纯 pipeline smoke 模式，此时不会启动 relay，也不会调用下列 plane 接口。

### 1.1 当前不要再按旧模型理解的点

- `bootstrap` 现在不是“配置下发 / manifest pair 回填”接口，而是**任务启动通知**。
- 当前主路径里，pipeline 主线不再直接请求 plane。
- `GET /api/baidu/token` 现在是默认的运行前配置拉取接口；若 workflow dispatch 显式携带 `inputs.payload.baidu`，`runtime_init` 会跳过这一步。
- `report` 现在也不是旧版的 `from_version/to_version/summary/uploaded_archives/...` 大 payload；当前已收敛为 `run_id + status + finished_at + changes`。
- 当前 `logs/finalize` 才是终态大摘要；`report` 更像最终变更清单回报。

---

## 2. 真相源

本页结论来自以下当前实现：

- `src/rift_audio_pipeline/control_plane/models.py`
- `src/rift_audio_pipeline/control_plane/service.py`
- `src/rift_audio_pipeline/control_plane/runtime_init.py`
- `src/rift_audio_pipeline/control_plane/log_relay.py`
- `src/rift_audio_pipeline/control_plane/finalize_worker.py`
- `src/rift_localdev/plane/mock_server.py`
- `tests/test_control_plane_service.py`
- `tests/test_control_plane_mock_server.py`
- `tests/test_control_plane_job_runner.py`
- `tests/test_control_plane_log_relay.py`

如果本文与旧文档冲突，以以上代码和测试为准。

---

## 3. 当前主路径

当前稳定主路径是：

`workflow_dispatch.inputs.payload`
-> `dispatch-payload.json`
-> `job_runner`
-> `runtime_init`
-> `log_relay + pipeline-main + upload_worker`
-> `finalize_worker`

其中与 plane 的交互分布如下：

### 3.1 `runtime_init`

负责：

1. 若 `inputs.payload.baidu` 缺失，则调 `GET /api/baidu/token`
2. 校验 `access_token`
3. 写本地 `baidu-token.json`
4. 用这组三元凭据去百度远端拉 `database.json`

### 3.2 `log_relay`

负责：

- 收到 `start` envelope 时发 `POST /api/pipeline/bootstrap`
- 运行中按需发 `POST /api/pipeline/runs/{run_id}/heartbeat`
- 转发结构化日志到 `POST /api/pipeline/runs/{run_id}/logs`
- 收到终态摘要时发 `POST /api/pipeline/runs/{run_id}/logs/finalize`
- 收到 `report` envelope 时发 `POST /api/pipeline/runs/{run_id}/report`

### 3.3 `finalize_worker`

负责：

1. 等待 upload drain
2. 用百度凭据轮转并上传新的 `database.json`
3. 构造最终 `report` payload
4. 通过 relay socket 把 `report` envelope 交给 relay

---

## 4. 请求头约定

当前 Python client 统一使用：

| Header | 必填 | 说明 |
| --- | --- | --- |
| `Accept: application/json` | 是 | 固定要求 |
| `User-Agent` | 是 | 不应为空 |
| `Authorization: Bearer <token>` | 否 | 若配置了 bearer token 就会发送 |
| `CF-Access-Client-Id` | 否 | 与 `CF-Access-Client-Secret` 成对出现 |
| `CF-Access-Client-Secret` | 否 | 与 `CF-Access-Client-Id` 成对出现 |

说明：

- plane 应允许 `Authorization` 与 `CF-Access-*` 同时存在。
- 当前所有业务参数都走 JSON body；没有 query 参数协定。

---

## 5. 接口清单

## 5.1 `GET /api/baidu/token`

### 调用方

- `runtime_init`

### 作用

- 在 workflow 未显式传入 `inputs.payload.baidu` 时，提供当前运行必需的百度三元凭据。

### 请求

- 无 body

### 响应体最小要求

```json
{
  "access_token": "plane-access-token"
}
```

### 字段要求

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `access_token` | `string` | 是 | 非空 |

### 可选字段

当前 `runtime_init` 只硬校验 `access_token`。若 plane 想额外返回 `expires_at`、`token_source` 等字段，可以带，但当前主路径不依赖。

### 错误后果

缺任一字段都会直接让初始化失败：

- `plane /api/baidu/token 缺少必需字段：...`

### 什么时候不是必需

当 workflow dispatch 的 `inputs.payload` 已经显式携带：

```json
{
  "baidu": {
    "access_token": "manual-access-token"
  }
}
```

此时 `runtime_init` 会直接使用 payload 中的值，不再请求本接口。

---

## 5.2 `POST /api/pipeline/bootstrap`

### 当前真实语义

- 任务启动通知

### 调用方

- `log_relay` 在收到 `start` envelope 后发送

### 请求体

```json
{
  "run_id": "99887766",
  "started_at": "2026-03-12T10:00:00+08:00"
}
```

### 字段要求

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `run_id` | `string` | 是 | 运行唯一标识 |
| `started_at` | `string` | 是 | 带时区 ISO 8601 |

### 响应要求

- 任意 `2xx` 即视为成功
- 响应 body 当前可为空
- 若 plane 需要补 trace 字段，也可以返回 JSON object，但 Python 执行端当前不会消费

### 明确不是当前职责的字段

当前主路径不再要求 bootstrap 返回：

- `current_version`
- `current_pair`
- `previous_version`
- `previous_pair`
- `baidu_access_grant`

这些属于旧阶段协议设计，不是当前 runtime worker 必需接口的一部分。

---

## 5.3 `POST /api/pipeline/runs/{run_id}/heartbeat`

### 调用方

- `log_relay`

### 作用

- 回报 relay 当前观察到的运行态。

### 请求体最小形状

```json
{
  "run_id": "99887766",
  "status": "running",
  "last_log_at": "2026-03-12T10:00:05+08:00",
  "progress": {
    "stage": "extract",
    "last_seq": 12,
    "relay_runtime": {
      "managed": true,
      "status": "running",
      "status_reason": null,
      "start_signal_received": true,
      "terminal_summary_received": false,
      "attention_detected": false,
      "main_pid": 12345,
      "last_stage": "extract",
      "last_seq": 12,
      "last_log_at": "2026-03-12T10:00:05+08:00"
    }
  }
}
```

### 字段要求

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `run_id` | `string` | 是 | 路径参数同值 |
| `status` | `string` | 是 | 当前常见 `running / success / partial_success / failed` |
| `last_log_at` | `string` | 是 | 带时区 ISO 8601 |
| `progress` | `object \\| null` | 否 | 当前 relay 默认会带 |

### `progress` 当前稳定字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `stage` | `string` | 是 | relay 最近观察到的阶段 |
| `last_seq` | `integer` | 是 | relay 最近观察到的日志序号 |
| `relay_runtime` | `object` | 是 | relay 稳定运行态快照 |

### `relay_runtime` 当前稳定字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `managed` | `boolean` | 是 | 固定为 `true` |
| `status` | `string` | 是 | 与 heartbeat 状态一致或同语义 |
| `status_reason` | `string \\| null` | 否 | 失败/降级原因 |
| `start_signal_received` | `boolean` | 是 | 是否收到了 start |
| `terminal_summary_received` | `boolean` | 是 | 是否已收终态摘要 |
| `attention_detected` | `boolean` | 是 | 是否见到 warning/error |
| `main_pid` | `integer \\| null` | 否 | 主进程 PID |
| `last_stage` | `string` | 是 | 最近阶段 |
| `last_seq` | `integer` | 是 | 最近日志序号 |
| `last_log_at` | `string` | 是 | 最近日志时间 |

### 响应要求

- 任意 `2xx` 即视为成功
- 响应 body 当前可为空

---

## 5.4 `POST /api/pipeline/runs/{run_id}/logs`

### 调用方

- `log_relay`

### 作用

- 向 plane 发送精简后的结构化事件流。

### 请求体最小形状

```json
{
  "run_id": "99887766",
  "event": {
    "schema_version": 1,
    "run_id": "99887766",
    "seq": 1,
    "created_at": "2026-03-12T10:00:05+08:00",
    "source": "pipeline",
    "level": "INFO",
    "stage": "init",
    "event_type": "run_started",
    "message": "pipeline 开始运行"
  }
}
```

### `event` 当前常见字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `schema_version` | `integer` | 是 | 当前默认 `1` |
| `run_id` | `string` | 是 | 与外层 run_id 一致 |
| `seq` | `integer` | 是 | 单调递增 |
| `created_at` | `string` | 是 | 事件时间 |
| `source` | `string` | 是 | 当前常见 `pipeline` / `relay` |
| `level` | `string` | 是 | `INFO/WARNING/ERROR/...` |
| `stage` | `string` | 是 | 阶段名 |
| `event_type` | `string` | 是 | 事件类型 |
| `message` | `string` | 是 | 摘要消息 |
| `status_hint` | `string \\| null` | 否 | 当前状态提示 |
| `entity_type` | `string \\| null` | 否 | 如 `champion/map` |
| `entity_id` | `integer \\| null` | 否 | 实体 ID |
| `entity_alias` | `string \\| null` | 否 | 实体别名 |
| `attempt` | `integer \\| null` | 否 | 重试次数 |
| `operation` | `string \\| null` | 否 | 操作名 |
| `payload` | `object` | 否 | 附加上下文 |
| `error_type` | `string \\| null` | 否 | 错误类别 |
| `error_message` | `string \\| null` | 否 | 错误摘要 |
| `code_file` | `string \\| null` | 否 | 错误文件 |
| `code_function` | `string \\| null` | 否 | 错误函数 |
| `code_line` | `integer \\| null` | 否 | 错误行号 |
| `exception_module` | `string \\| null` | 否 | 异常模块 |

### plane 不应再依赖的旧噪音字段

relay 在转发前会主动清洗，不应要求这些字段：

- `thread_name`
- `traceback`
- `cause_chain`
- 其他主线程内部噪音字段

### 响应要求

- 任意 `2xx` 即视为成功
- 响应 body 当前可为空
- `next_expected_seq` 已不是当前主路径依赖项；若 plane 想保留调试/追踪值，可以继续返回，但 Python 执行端会忽略

---

## 5.5 `POST /api/pipeline/runs/{run_id}/logs/finalize`

### 调用方

- `log_relay`

### 作用

- 把运行的终态日志摘要交给 plane。

### 请求体最小形状

```json
{
  "run_id": "99887766",
  "summary": {
    "run_id": "99887766",
    "finished_at": "2026-03-12T10:10:00+08:00",
    "final_status": "success",
    "final_stage": "finalize",
    "last_seq": 12,
    "processed_targets": 10,
    "succeeded_targets": 10,
    "failed_targets": 0,
    "uploaded_archives": 10,
    "raw_log_bundle_ready": true,
    "raw_log_local_dir": "/abs/path/to/logs/99887766",
    "raw_log_remote_path": null,
    "summary": {
      "status": "success",
      "relay_runtime": {}
    },
    "error_brief": null,
    "schema_version": 1
  }
}
```

### `summary` 当前稳定字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `run_id` | `string` | 是 | 当前 run |
| `finished_at` | `string` | 是 | 结束时间 |
| `final_status` | `string` | 是 | 终态 |
| `final_stage` | `string` | 是 | 结束阶段 |
| `last_seq` | `integer` | 是 | 最后事件序号 |
| `processed_targets` | `integer` | 是 | 处理目标数 |
| `succeeded_targets` | `integer` | 是 | 成功目标数 |
| `failed_targets` | `integer` | 是 | 失败目标数 |
| `uploaded_archives` | `integer` | 是 | 已上传归档数 |
| `raw_log_bundle_ready` | `boolean` | 是 | 本地 RAW 是否完整 |
| `raw_log_local_dir` | `string` | 是 | 本地 RAW 目录 |
| `raw_log_remote_path` | `string \\| null` | 否 | 若有远端日志根路径可带 |
| `summary` | `object` | 是 | 至少含 `status` 和 `relay_runtime` |
| `error_brief` | `object \\| null` | 否 | 错误摘要 |
| `schema_version` | `integer` | 是 | 当前默认 `1` |

### `summary.summary.relay_runtime`

这里的 `relay_runtime` 与 heartbeat 里的同构，当前 mock plane 也会专门提取这块做状态记录。

### 响应要求

- 任意 `2xx` 即视为成功
- 响应 body 当前可为空
- `worker_status` 已不是当前主路径依赖项；若 plane 想保留展示值，可以继续返回

---

## 5.6 `POST /api/pipeline/runs/{run_id}/report`

### 当前真实语义

- 最终变更清单回报

### 调用方

- `finalize_worker` 先构造 report payload
- 再通过 relay socket 发 `report` envelope
- 最终由 `log_relay` 真正发 HTTP 请求到 plane

### 请求体最小形状

```json
{
  "run_id": "99887766",
  "status": "success",
  "finished_at": "2026-03-12T10:12:00+08:00",
  "changes": [
    {
      "remote_path": "/apps/rift-audio-pipeline/VO/champions/demo.7z",
      "file_name": "demo.7z"
    }
  ]
}
```

### 字段要求

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `run_id` | `string` | 是 | 当前 run |
| `status` | `string` | 是 | 当前终态 |
| `changes` | `object[]` | 否 | 当前默认会带，允许空数组 |
| `finished_at` | `string \\| null` | 否 | 完成时间 |

### `changes` 当前来源

- `finalize_worker.build_report_payload()`
- `state.sqlite3` 中本轮收敛出的文件变更事实

当前 `changes` 的元素至少可能包含：

- `remote_path`
- `file_name`

后续如果 SQLite 导出项扩展，plane 应对附加字段保持前向兼容。

### 响应要求

- 任意 `2xx` 即视为成功
- 响应 body 当前可为空
- `next_head_version` 已不是当前主路径依赖项；若 plane 想保留调试字段，可以继续返回

### 明确不是当前职责的旧字段

当前主路径不再要求 report 带这些旧字段：

- `from_version`
- `to_version`
- `summary`
- `uploaded_archives`
- `diff_artifacts_key`
- `r2_summary_key`
- `baidu_log_path`

---

## 6. 本地 mock plane 当前实现的对应关系

当前本地 mock plane 真正的实现文件在：

- `src/rift_localdev/plane/mock_server.py`

它当前提供：

- `GET /healthz`
- `GET /api/baidu/token`
- `POST /api/pipeline/bootstrap`
- `POST /api/pipeline/runs/{run_id}/heartbeat`
- `POST /api/pipeline/runs/{run_id}/logs`
- `POST /api/pipeline/runs/{run_id}/logs/finalize`
- `POST /api/pipeline/runs/{run_id}/report`

它当前的默认响应策略：

- `/api/baidu/token` 返回完整百度三元凭据
- 其他 callback 默认返回空 JSON object，由 HTTP `2xx` 语义表示成功

因此，如果新的 TS plane 要先做最小可运行联调，对齐到 mock plane 这一层即可。

---

## 7. 实现建议

如果要在新的 plane 里先做“最小可运行版”，建议按这个优先级实现：

1. `GET /healthz`
2. `GET /api/baidu/token`
3. `POST /api/pipeline/bootstrap`
4. `POST /api/pipeline/runs/{run_id}/heartbeat`
5. `POST /api/pipeline/runs/{run_id}/logs`
6. `POST /api/pipeline/runs/{run_id}/logs/finalize`
7. `POST /api/pipeline/runs/{run_id}/report`

其中最先不能缺的是：

- `/api/baidu/token`
- `/api/pipeline/bootstrap`
- `/api/pipeline/runs/{run_id}/heartbeat`
- `/api/pipeline/runs/{run_id}/logs`
- `/api/pipeline/runs/{run_id}/logs/finalize`
- `/api/pipeline/runs/{run_id}/report`

缺少其中任一项，都无法完整跑通当前 `job_runner` 主路径。

---

## 8. 阅读顺序

当前建议的阅读顺序是：

1. 本文 `plane_required_interfaces_current.md`
2. `runtime_worker_rearchitecture_2026-03-11.md`
3. `pipeline_protocol_contracts.md`

如果几者冲突：

- 以当前代码和测试为准
- 以本文描述的当前接口模型为准
