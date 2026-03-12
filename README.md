# RiftAudioPipeline

当前仓库已经具备 GitHub Actions `workflow_dispatch -> job_runner -> runtime_init -> pipeline-main -> upload_worker -> finalize_worker` 的主路径。手动触发 workflow 时，`inputs.payload` 必须是一个 JSON 字符串；Python 侧会再把它解析为结构化对象。

更细的协议说明见 `docs/control_plane/faker_github_api.md`，本页只保留直接可用的变量、命令和手动调用方式。

## GitHub Actions 变量

`/.github/workflows/pipeline.yml` 当前会读取以下 GitHub Actions variables / secrets：

| 名称 | 类型 | 是否当前必需 | 作用 |
| --- | --- | --- | --- |
| `RIFT_CONTROL_PLANE_BASE_URL` | Actions variable | 是 | 传给 `job_runner --control-plane-base-url`，当前 relay 仍依赖它 |
| `RIFT_CONTROL_PLANE_BEARER_TOKEN` | Actions secret | 否 | plane Bearer token |
| `RIFT_CONTROL_PLANE_ACCESS_CLIENT_ID` | Actions secret | 否 | Cloudflare Access client id |
| `RIFT_CONTROL_PLANE_ACCESS_CLIENT_SECRET` | Actions secret | 否 | Cloudflare Access client secret |

说明：

- 即使手动 dispatch 时在 `inputs.payload.baidu` 里显式提供了百度三元凭据，当前 workflow 仍然会启动 log relay，并继续使用 `RIFT_CONTROL_PLANE_BASE_URL` 做 bootstrap / heartbeat / logs / report。
- 本次改动只去掉了“百度凭据必须从 `/api/baidu/token` 拉取”的硬依赖，没有把整条运行链改成完全脱离 plane。

## 手动触发用法

### GitHub UI

1. 打开 `Actions -> Pipeline Dispatch -> Run workflow`。
2. `payload` 输入框里填入一个 JSON 字符串，而不是 JSON object。
3. 若只想绕过 plane 的百度凭据接口，可在这个字符串里带上 `baidu.app_key / secret_key / refresh_token`。

### GitHub CLI

先在本地生成 `payload` 字符串：

```bash
payload="$(
  jq -cn \
    --arg current_version "16.5.7519084" \
    --arg current_lcu "https://lol.secure.dyn.riotcdn.net/channels/public/releases/current-lcu.manifest" \
    --arg current_game "https://lol.secure.dyn.riotcdn.net/channels/public/releases/current-game.manifest" \
    --arg previous_version "16.4.7423123" \
    --arg previous_lcu "https://lol.secure.dyn.riotcdn.net/channels/public/releases/previous-lcu.manifest" \
    --arg previous_game "https://lol.secure.dyn.riotcdn.net/channels/public/releases/previous-game.manifest" \
    --arg baidu_app_key "$BAIDU_APP_KEY" \
    --arg baidu_secret_key "$BAIDU_SECRET_KEY" \
    --arg baidu_refresh_token "$BAIDU_REFRESH_TOKEN" \
    '{
      schema_version: "2026-03-12",
      request: {
        mode: "remote",
        stage: "extract"
      },
      game: {
        region: "oc1"
      },
      manifests: {
        current: {
          version: $current_version,
          lcu_url: $current_lcu,
          game_url: $current_game
        },
        previous: {
          version: $previous_version,
          lcu_url: $previous_lcu,
          game_url: $previous_game
        }
      },
      targets: {
        champions: {
          ids: [266, 103]
        },
        maps: {
          ids: [11]
        }
      },
      baidu: {
        app_key: $baidu_app_key,
        secret_key: $baidu_secret_key,
        refresh_token: $baidu_refresh_token
      },
      execution: {
        force_update: false,
        max_workers: 8,
        download_retry_attempts: 5,
        entity_retry_attempts: 2,
        log_level: "INFO"
      },
      metadata: {
        requested_by: "manual-gh"
      }
    }'
)"
```

然后触发 workflow：

```bash
gh workflow run pipeline.yml --ref main -f payload="$payload"
```

不要把完整 object 直接贴到 GitHub CLI / UI 的 `payload` 字段里；这个字段本身要求的是字符串。最稳的做法就是先用 `jq -cn` 生成一整个 JSON 字符串，再作为 `-f payload=...` 传入。

## `inputs.payload` 完整 schema

当前支持的结构如下：

```json
{
  "schema_version": "2026-03-12",
  "request": {
    "mode": "remote",
    "stage": "update"
  },
  "game": {
    "region": "oc1"
  },
  "manifests": {
    "current": {
      "version": "16.5.7519084",
      "lcu_url": "https://example/current-lcu.manifest",
      "game_url": "https://example/current-game.manifest"
    },
    "previous": {
      "version": "16.4.7423123",
      "lcu_url": "https://example/previous-lcu.manifest",
      "game_url": "https://example/previous-game.manifest"
    }
  },
  "targets": {
    "champions": {
      "ids": [266, 103]
    },
    "maps": {
      "ids": [11, 12]
    }
  },
  "baidu": {
    "app_key": "manual-app-key",
    "secret_key": "manual-secret-key",
    "refresh_token": "manual-refresh-token"
  },
  "execution": {
    "force_update": false,
    "max_workers": 8,
    "download_retry_attempts": 5,
    "entity_retry_attempts": 2,
    "log_level": "INFO",
    "archive_password": "optional-archive-password"
  },
  "metadata": {
    "requested_by": "manual-gh"
  }
}
```

字段说明：

- `request.stage` 当前只支持 `update` / `extract` / `mapping`。
- `targets.*.ids` 支持 JSON 数组，也支持逗号分隔字符串。
- `baidu` 整体可选；若提供，就必须同时包含 `app_key`、`secret_key`、`refresh_token` 三项非空字符串。
- 若不提供 `baidu`，`runtime_init` 会回退到 plane `GET /api/baidu/token`。
- `schema_version` 目前主要用于日志与收据，不直接影响 CLI 参数。

## 本地验证

这次变更相关的最小验证命令：

```bash
uv run pytest tests/test_faker_github.py tests/test_github_actions_workflow.py tests/test_control_plane_job_runner.py -q
```
