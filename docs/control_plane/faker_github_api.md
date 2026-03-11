# faker-github API

> 目的：提供一个本地可运行的假 GitHub 服务端，专门承接 plane 发出的 `workflow_dispatch` 请求。  
> 作用边界：只覆盖 `POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches` 和 `GET /healthz`，不模拟完整 GitHub Actions API。  
> 当前事实来源：[`src/rift_audio_pipeline/cloudflare/faker_github.py`](../../src/rift_audio_pipeline/cloudflare/faker_github.py)。

## 1. 设计边界

`faker-github` 现在要求 `inputs` 统一使用一个包装层：`inputs.payload`，并且这个 `payload` 必须是 JSON 字符串。

这样做的目的有两个：

- `inputs` 本身就表达语义层级，不再靠“字段名猜用途”
- Python 侧可以直接反序列化成多层 dataclass，而不是到处维护 `inputs` 字段名和内部变量名的映射关系

当前边界分成两类：

- 业务 `payload`
  - 代表一次 dispatch 的业务请求体
  - 会进入 payload 校验、stdout 调试日志和 dispatch 收据
  - 其中一部分会继续翻译成 `rift_audio_pipeline.pipeline.cli` 参数
- 运行环境配置
  - 代表 `faker-github` 自己启动时注入的固定环境
  - 不属于单次 dispatch 的业务差异
  - 不应混入 `payload`

因此，像 `worker_url`、`worker_token` 这类运行时配置或机密不应放进 `inputs.payload` 对应的 JSON 内容里。

## 2. 启动方式

### 正常模式

```bash
uv run rift-faker-github \
  --host 127.0.0.1 \
  --port 9001 \
  --github-token local-test-token \
  --control-plane-base-url http://localhost:5173
```

### dry-run 模式

```bash
uv run rift-faker-github \
  --host 127.0.0.1 \
  --port 9001 \
  --dry-run
```

如果不传 `--github-token`，启动时会自动生成一个本地测试 token，并打印在启动 JSON 里。

`--dry-run` 的语义：

- 仍然接收并校验 workflow dispatch 请求
- 仍然把请求翻译成 pipeline CLI 命令
- 仍然返回 `204 No Content`
- 不会真实启动 pipeline 子进程
- 会把解析结果写入 dispatch 收据

`--log-http-exchange` 的语义：

- 会把 dispatch 请求入参与响应摘要输出到 stdout
- 便于本地联调观察 plane 发出来的 payload 与 faker-github 的解析结果

## 3. 启动输出

启动后会先打印一份 JSON：

```json
{
  "base_url": "http://127.0.0.1:9001",
  "dispatch_route": "http://127.0.0.1:9001/repos/<owner>/<repo>/actions/workflows/<workflow_id>/dispatches",
  "healthz": "http://127.0.0.1:9001/healthz",
  "storage_root": "temp/faker_github",
  "github_token": "generated-or-provided-token",
  "github_token_source": "generated",
  "github_token_preview": "abc123...wxyz",
  "control_plane_base_url": "http://localhost:5173",
  "dry_run": true,
  "log_http_exchange": false
}
```

关键字段：

| 字段 | 说明 |
| --- | --- |
| `base_url` | 当前 faker-github 监听地址 |
| `dispatch_route` | 本地 workflow dispatch 路径模板 |
| `healthz` | 健康检查地址 |
| `storage_root` | dispatch 收据和子进程日志落盘根目录 |
| `github_token` | 当前 dispatch 必须携带的完整 token |
| `github_token_source` | `provided` 或 `generated` |
| `github_token_preview` | 脱敏后的 token 预览 |
| `control_plane_base_url` | 当前注入给 pipeline 的固定 control plane 地址 |
| `dry_run` | 是否开启 dry-run |
| `log_http_exchange` | 是否把请求/响应摘要输出到 stdout |

## 4. HTTP API

| 方法 | 路径 | 作用 | 成功响应 |
| --- | --- | --- | --- |
| `GET` | `/healthz` | 返回服务存活信息与当前运行配置摘要 | `200 application/json` |
| `POST` | `/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches` | 模拟 GitHub `workflow_dispatch` | `204 No Content` |

未支持的路径会返回 `404 not_found`。

请求异常时可能返回：

- `400 invalid_json`
- `400 invalid_body`
- `401 unauthorized`
- `411 length_required`
- `422 validation_failed`

## 5. `GET /healthz`

### 响应体

```json
{
  "ok": true,
  "base_url": "http://localhost:5173",
  "dry_run": true,
  "auth_required": true,
  "github_token_source": "generated",
  "github_token_preview": "abc123...wxyz"
}
```

### 字段说明

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ok` | `boolean` | 固定为 `true` |
| `base_url` | `string` | 当前注入 pipeline 的 control plane base URL |
| `dry_run` | `boolean` | 当前是否启用 dry-run |
| `auth_required` | `boolean` | 当前固定为 `true` |
| `github_token_source` | `string` | `provided` 或 `generated` |
| `github_token_preview` | `string` | token 的脱敏摘要 |

## 6. `POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches`

这个接口刻意对齐 GitHub 官方 `workflow_dispatch` REST API，只实现本项目本地联调需要的最小子集。

注意：

- `owner`、`repo`、`workflow_id` 当前不会做真实仓库存在性校验
- 它们只用于日志、stdout 输出和 dispatch 收据
- 真正的拦截条件只有两类：鉴权是否合法、payload 是否符合嵌套 schema

### 路径参数

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `owner` | `string` | 仅用于收据和调试输出 |
| `repo` | `string` | 仅用于收据和调试输出 |
| `workflow_id` | `string` | 仅用于收据和调试输出 |

### 请求头

| Header | 必填 | 说明 |
| --- | --- | --- |
| `Authorization: Bearer <token>` | 是 | 推荐写法；token 必须与启动输出中的 `github_token` 一致 |
| `Authorization: token <token>` | 否 | 兼容写法；与 `Bearer` 等价 |
| `Content-Type: application/json` | 是 | 请求体必须是 JSON object |
| `Content-Length` | 是 | 缺失时会返回 `411` |

### 最小请求体

```json
{
  "ref": "main"
}
```

### 推荐请求体

```json
{
  "ref": "main",
  "inputs": {
    "payload": "{\"schema_version\":\"2026-03-11\",\"request\":{\"mode\":\"remote\",\"stage\":\"update\"},\"game\":{\"region\":\"oc1\"},\"manifests\":{\"current\":{\"version\":\"16.5.7519084\",\"lcu_url\":\"https://lol.secure.dyn.riotcdn.net/channels/public/releases/current-lcu.manifest\",\"game_url\":\"https://lol.secure.dyn.riotcdn.net/channels/public/releases/current-game.manifest\"},\"previous\":{\"version\":\"16.4.7423123\",\"lcu_url\":\"https://lol.secure.dyn.riotcdn.net/channels/public/releases/previous-lcu.manifest\",\"game_url\":\"https://lol.secure.dyn.riotcdn.net/channels/public/releases/previous-game.manifest\"}},\"targets\":{\"champions\":{\"ids\":[266,103]},\"maps\":{\"ids\":[11,12]}},\"execution\":{\"force_update\":false,\"max_workers\":8,\"download_retry_attempts\":5,\"entity_retry_attempts\":2,\"log_level\":\"INFO\"},\"metadata\":{\"requested_by\":\"scheduler\"}}"
  }
}
```

## 7. `inputs.payload` schema

### 7.1 顶层结构

`inputs` 顶层当前只接受一个字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `payload` | `string` | 结构化业务请求体对应的 JSON 字符串 |

`inputs.payload` 顶层只接受这些字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `schema_version` | `string` | schema 版本标记，可选 |
| `request` | `object` | 本次 dispatch 的请求维度 |
| `game` | `object` | 游戏上下文 |
| `manifests` | `object` | 当前版与上一版 manifest 信息 |
| `targets` | `object` | 英雄/地图目标 |
| `execution` | `object` | 执行策略 |
| `metadata` | `object` | 请求来源等元信息 |

### 7.2 各层字段

#### `request`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `mode` | `string` | pipeline 模式 |
| `stage` | `string` | 执行阶段意图；当前支持 `update` / `extract` / `mapping` |

#### `game`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `region` | `string` | 游戏区域 |

#### `manifests.current` / `manifests.previous`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `version` | `string` | 版本号 |
| `lcu_url` | `string` | LCU manifest URL |
| `game_url` | `string` | GAME manifest URL |

#### `targets.champions` / `targets.maps`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ids` | `number[]` 或逗号分隔字符串 | 目标 ID 列表 |

说明：

- `maps` 当前只有 `ids`
- `map_aliases` 已从 schema 中移除，因为目前没有实际用途

#### `execution`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `force_update` | `boolean` | 是否强制更新 |
| `max_workers` | `integer` | 并发工作数 |
| `download_retry_attempts` | `integer` | 下载重试次数 |
| `entity_retry_attempts` | `integer` | 单实体重试次数 |
| `log_level` | `string` | pipeline 日志级别 |

#### `metadata`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `requested_by` | `string` | 请求来源 |

### 7.3 校验规则

- 未知字段直接报错，不做静默忽略
- 不再接受扁平 `inputs`
- `inputs` 顶层只允许 `payload`
- `inputs.payload` 必须是 JSON object 字符串
- `string` 字段必须是非空字符串
- `integer` 字段必须是整数，`true`/`false` 不会被当成 `1/0`
- `boolean` 字段接受 JSON 布尔值，也接受 `"true"` / `"false"` 这类常见字符串写法
- `targets.*.ids` 接受：
  - JSON 数组，例如 `[266, 103]`
  - 逗号分隔字符串，例如 `"266,103"`

### 7.4 明确拒绝的输入

以下内容会触发 `422 validation_failed`：

- 扁平字段，例如 `inputs.mode`、`inputs.game_region`、`inputs.requested_by`
- 错误的包装层，例如 `inputs.data`
- 旧别名，例如 `region`、`requestedBy`、`championIds`、`mapIds`
- 已移除字段，例如 `map_aliases`
- 运行时配置或机密，例如 `worker_url`、`worker_token`

## 8. `inputs` 到 pipeline CLI 的映射

### 8.1 当前会下沉到 CLI 的字段

| 结构化路径 | 对应 CLI 参数 |
| --- | --- |
| `request.mode` | `--mode` |
| `request.stage=update` | `--run-update --no-run-extract --no-run-mapping` |
| `request.stage=extract` | `--run-update --run-extract --no-run-mapping` |
| `request.stage=mapping` | `--run-update --run-extract --run-mapping` |
| `game.region` | `--game-region` |
| `manifests.current.version` | `--current-version` |
| `manifests.current.lcu_url` | `--current-lcu-manifest-url` |
| `manifests.current.game_url` | `--current-game-manifest-url` |
| `metadata.requested_by` | `--control-plane-requested-by` |
| `execution.log_level` | `--log-level` |
| `manifests.previous.version` | `--previous-version` |
| `manifests.previous.lcu_url` | `--previous-lcu-manifest-url` |
| `manifests.previous.game_url` | `--previous-game-manifest-url` |
| `targets.champions.ids` | `--champion-ids` |
| `targets.maps.ids` | `--map-ids` |
| `execution.max_workers` | `--max-workers` |
| `execution.download_retry_attempts` | `--download-retry-attempts` |
| `execution.entity_retry_attempts` | `--entity-retry-attempts` |
| `execution.force_update=true` | `--force-update` |
| `execution.force_update=false` | `--no-force-update` |

### 8.2 当前仅保留在 payload/收据的字段

以下字段已经进入结构化 schema，但当前仍不会直接翻译成命令参数：

- `schema_version`

这意味着：

- 它们会出现在请求日志和 dispatch 收据里
- 但不会影响当前 pipeline CLI 的实际启动参数

## 9. 启动时注入的固定参数

除了业务 `inputs.payload`，`faker-github` 还会把自己的启动配置注入到最终 CLI。这些值属于运行环境配置，不属于单次 dispatch 业务差异。

| `rift-faker-github` 启动参数 | 作用到 pipeline CLI |
| --- | --- |
| `--control-plane-base-url` | 转成 `--control-plane-base-url` |
| `--control-plane-bearer-token` | 转成 `--control-plane-bearer-token` |
| `--control-plane-access-client-id` | 转成 `--control-plane-access-client-id` |
| `--control-plane-access-client-secret` | 转成 `--control-plane-access-client-secret` |
| `--default-mode` | 当 `inputs.request.mode` 缺失时作为默认值 |
| `--default-game-region` | 当 `inputs.game.region` 缺失时作为默认值 |
| `--default-requested-by` | 当 `inputs.metadata.requested_by` 缺失时作为默认值 |
| `--output-root` | 转成 `--output-root` |
| `--temp-root` | 转成 `--temp-root` |
| `--log-root` | 转成 `--log-root` |
| `--baidu-remote-root` | 转成 `--baidu-remote-root` |
| `--default-log-level` | 当 `inputs.execution.log_level` 缺失时作为默认值 |
| `--control-plane-timeout-seconds` | 转成 `--control-plane-timeout-seconds` |

## 10. dispatch 收据

每次成功 dispatch 后，都会在 `storage_root/dispatches/<dispatch_id>.json` 写入收据。

示例：

```json
{
  "dispatch_id": "20260311T101530-123456",
  "received_at": "2026-03-11T10:15:30.123456+08:00",
  "owner": "octo",
  "repo": "example",
  "workflow_id": "pipeline.yml",
  "ref": "main",
  "inputs": {
    "payload": "{\"schema_version\":\"2026-03-11\",\"game\":{\"region\":\"euw\"},\"targets\":{\"champions\":{\"ids\":[266,103]}},\"metadata\":{\"requested_by\":\"plane-scheduler\"}}"
  },
  "command": [
    "/path/to/python",
    "-m",
    "rift_audio_pipeline.pipeline.cli",
    "--mode",
    "remote",
    "--game-region",
    "euw",
    "--control-plane-requested-by",
    "plane-scheduler",
    "--champion-ids",
    "266,103"
  ],
  "dry_run": true,
  "pid": null,
  "log_path": null
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `dispatch_id` | 本地生成的唯一 dispatch id |
| `received_at` | 接收请求的时间 |
| `owner` / `repo` / `workflow_id` | 原始请求路径上的标识 |
| `ref` | 原始 workflow ref |
| `inputs` | 通过 schema 校验并规范化后的结构化请求体 |
| `command` | 解析后的完整 pipeline CLI |
| `dry_run` | 是否为 dry-run |
| `pid` | 正常模式下的子进程 PID；dry-run 时为 `null` |
| `log_path` | 正常模式下的日志路径；dry-run 时为 `null` |

正常模式下，pipeline 子进程日志会落在 `storage_root/logs/<dispatch_id>.log`。

## 11. 示例请求

### 健康检查

```bash
curl -s http://127.0.0.1:9001/healthz
```

### 触发一轮 dry-run dispatch

```bash
curl -i \
  -X POST \
  -H 'Authorization: Bearer local-test-token' \
  -H 'Content-Type: application/json' \
  http://127.0.0.1:9001/repos/octo/example/actions/workflows/pipeline.yml/dispatches \
  -d '{
    "ref": "main",
    "inputs": {
      "payload": "{\"schema_version\":\"2026-03-11\",\"request\":{\"mode\":\"remote\"},\"game\":{\"region\":\"euw\"},\"targets\":{\"champions\":{\"ids\":\"266,103\"}},\"execution\":{\"force_update\":false},\"metadata\":{\"requested_by\":\"plane-scheduler\"}}"
    }
  }'
```

预期结果：

- HTTP 响应 `204 No Content`
- 如果启用了 `--log-http-exchange`，stdout 会看到请求与响应摘要
- 如果启用了 `--dry-run`，不会产生真实 pipeline 子进程
- 收据会落在 `temp/faker_github/dispatches/`

## 12. 与 plane 文档的关系

- 这份文档只描述 plane 调用 GitHub/faker-github 的 dispatch 链路
- pipeline 回调 plane 的契约不在本文档范围内
- 当前 `faker-github` 不实现 GitHub Actions 的其他接口，只覆盖本项目本地联调需要的最小子集
