# 百度官方 SDK 目录说明

该目录存放百度开放平台官方生成代码（包含 `openapi_client` 与 `demo`），作为第三方依赖直接引用。

## 使用约束

- `openapi_client/` 视为上游生成代码，不在业务逻辑中直接散写调用。
- 业务访问统一通过 `src/rift_audio_pipeline/baidu_pan.py` 适配层。
- 该目录已在 `ruff` 中排除，避免格式化/静态检查干扰上游代码。

## 升级方式

1. 用新的官方 SDK 覆盖本目录内容。
2. 执行一次 `ruff check`（确认仅业务代码受检）。
3. 运行基础导入测试：`python -m rift_audio_pipeline --output-path ./output --dry-run`。
