# `database.json` v2 与网盘布局

本文档是当前 `database.json` v2、百度网盘目录布局，以及 finalize 阶段历史文件迁移规则的正式说明。

当前事实来源：

- `src/rift_audio_pipeline/control_plane/runtime_init.py`
- `src/rift_audio_pipeline/control_plane/finalize_worker.py`
- `src/rift_audio_pipeline/control_plane/state_db.py`
- `src/rift_audio_pipeline/baidu/pan.py`

## 1. 设计目标

v2 方案的目标有三个：

1. 明确区分用户可见 archive 与运行期 meta 文件
2. 让 active 数据库只描述“当前仍然有效的产物”
3. 把历史版本的迁移规则收敛为有限、可验证、可测试的几条规则

## 2. 运行时输入

当前运行时必须区分两个远端根目录：

### `archive_remote_root`

- 默认：`/apps/rift-audio-pipeline-data/`
- 用途：存放用户可见 archive 包
- 当前只允许 active archive 产物落在这里

### `meta_remote_root`

- 默认：`/apps/rift-audio-pipeline-meta/`
- 用途：
  - `database.json`
  - 轮转数据库快照
  - pipeline logs
  - finalize / upload 收据与运行元数据

约束：

- 不要把 `database.json`、日志或收据写到 `archive_remote_root`
- archive 和 meta 必须分根

## 3. 目录布局

### 3.1 archive 根目录

active archive 当前布局：

- `champions/`
- `maps/`

注意：

- 不按类型再拆目录
- 类型只体现在文件名后缀中

示例：

- `champions/103·ahri·九尾妖狐·阿狸-16.5-ALL.7z`
- `champions/103·ahri·九尾妖狐·阿狸-16.6-VO.7z`
- `maps/11·sr·召唤师峡谷-16.5-ALL.7z`

### 3.2 meta 根目录

当前固定放在 `meta_remote_root/` 下的内容：

- `database.json`
- `database-<timestamp>.json`
- pipeline logs
- upload / finalize metadata

### 3.3 history 目录

旧 active 文件迁移后的目标目录：

- `_old_versions/champions/`
- `_old_versions/maps/`

它们也位于 `archive_remote_root` 下面。

## 4. `database.json` v2 结构

顶层字段：

```json
{
  "schema_version": 2,
  "updated_at": "2026-03-14T01:05:00+08:00",
  "archive_remote_root": "/apps/rift-audio-pipeline-data/",
  "meta_remote_root": "/apps/rift-audio-pipeline-meta/",
  "entry_count": 3,
  "entries": {}
}
```

语义：

- `schema_version`
  - 固定为 `2`
- `updated_at`
  - 当前导出时间
- `archive_remote_root`
  - active archive 根目录
- `meta_remote_root`
  - 数据库、日志和收据根目录
- `entry_count`
  - active entity 数量，不是 artifact 数量
- `entries`
  - 以人类可读 `entity_key` 为 key 的 object

### `entries` 结构

```json
{
  "103·ahri·九尾妖狐·阿狸": {
    "id": 103,
    "alias": "ahri",
    "artifacts": [
      {
        "type": "ALL",
        "version": "16.5",
        "remote_path": "/apps/rift-audio-pipeline-data/champions/103·ahri·九尾妖狐·阿狸-16.5-ALL.7z",
        "remote_name": "103·ahri·九尾妖狐·阿狸-16.5-ALL.7z",
        "sha256": "xxx",
        "packaged_at": "2026-03-10T07:58:31+00:00",
        "uploaded_at": "2026-03-10T08:00:00+00:00"
      }
    ]
  }
}
```

artifact 类型当前限制为：

- `ALL`
- `VO`
- `SFX`
- `MUSIC`

## 5. active 规则

### 5.1 什么会进入 active

只有当前仍然有效、仍然应该对外展示的 archive 才会留在 active `entries` 中。

### 5.2 新 `ALL` 覆盖旧单类型

当同一实体在本轮上传了新的 `ALL`，且历史 active 中存在更低版本的：

- `VO`
- `SFX`
- `MUSIC`

这些旧单类型会：

1. 从 active `database.json` 中移除
2. 被移动到 `_old_versions/<group>/`

示例：

- 旧 active：
  - `champions/103·ahri·九尾妖狐·阿狸-16.3-VO.7z`
  - `champions/103·ahri·九尾妖狐·阿狸-16.4-SFX.7z`
- 新上传：
  - `champions/103·ahri·九尾妖狐·阿狸-16.5-ALL.7z`
- 结果：
  - active 只保留 `16.5-ALL`
  - 旧单类型移动到 `_old_versions/champions/`

### 5.3 旧 `ALL` 之后出现更新单类型

若 active 中已有旧 `ALL`，之后又上传了更新版本的单类型，则两者都保留 active。

示例：

- 已有 active：
  - `champions/103·ahri·九尾妖狐·阿狸-16.5-ALL.7z`
- 新上传：
  - `champions/103·ahri·九尾妖狐·阿狸-16.6-VO.7z`
- 结果：
  - `16.5-ALL` 保留 active
  - `16.6-VO` 也保留 active

### 5.4 当前不做的事

当前不会做这些额外语义：

- 不会因为同版本 `ALL` 自动删除本轮新单类型
- 不会跨实体做覆盖判断
- 不会把 `_old_versions/` 中的文件继续写回 active 数据库

## 6. finalize 阶段行为

当前 `finalize_worker` 的顺序是：

1. 从 `state.sqlite3` 读取 `remote_database_entries` 与 `new_file_facts`
2. 生成 database export plan
3. 若计划中存在历史迁移项，则把旧单类型移到 `_old_versions/<group>/`
4. 根据迁移后的 active 集合写本地 `database.json`
5. 上传到 `meta_remote_root/database.json`
6. 若远端已有旧 `database.json`，先轮转成 `database-<timestamp>.json`

## 7. 远端目录存在性策略

所有远端目录操作遵循同一条规则：

- 下载前先确认目录存在
- 创建目录前先确认父目录存在
- 移动前先确认目标目录存在
- 不存在时先递归创建

当前代码已经对这些动作补了目录确保逻辑：

- `runtime_init` 下载 `database.json` 前确保 `meta_remote_root` 存在
- `upload_worker` 上传 archive 前确保目标父目录存在
- `finalize_worker` 轮转 / 上传 `database.json` 前确保 `meta_remote_root` 存在
- `finalize_worker` 移动旧单类型到 `_old_versions/` 前确保目标目录存在

## 8. 当前约束

- 当前正式数据库只支持 `schema_version = 2`
- 默认不兼容旧 `database` / 旧 `entries list`
- 如果未来真的要做迁移兼容，必须由调用方或单独迁移脚本显式承担，不应在主路径里偷偷保留双轨
