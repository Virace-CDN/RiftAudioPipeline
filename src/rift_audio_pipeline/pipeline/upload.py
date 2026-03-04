"""Pipeline 上传、索引与日志模块。"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time

from loguru import logger

from rift_audio_pipeline.baidu.oauth import resolve_token_store
from rift_audio_pipeline.baidu.pan import BaiduPanApiError
from rift_audio_pipeline.baidu.pan import BaiduCredentials
from rift_audio_pipeline.baidu.pan import BaiduPanClient
from rift_audio_pipeline.config import PipelineConfig
from rift_audio_pipeline.packer import pack_all
from rift_audio_pipeline.pipeline.utils import _build_update_log_text
from rift_audio_pipeline.pipeline.utils import _build_upload_manifest_index
from rift_audio_pipeline.pipeline.utils import _calculate_sha256
from rift_audio_pipeline.pipeline.utils import _current_utc_timestamp
from rift_audio_pipeline.pipeline.utils import _is_same_index_entry
from rift_audio_pipeline.pipeline.utils import _join_remote_file_path
from rift_audio_pipeline.pipeline.utils import _parse_game_version_sort_key

DEFAULT_BUNDLED_PACK_EXTRA_DIR = Path(__file__).resolve().parents[1] / "pack_extra"

DEFAULT_PACK_EXTRA_FILES = ("食用说明.txt", "license.txt")

UPLOAD_MANIFEST_FILE_NAME = "upload_manifest.json"

UPLOAD_MANIFEST_TEXT_FILE_NAME = "upload_manifest_readable.txt"

UPLOAD_MANIFEST_SCHEMA_VERSION = 2

RESOURCE_TYPE_BUCKETS = ("VO", "SFX", "MUSIC")

OLD_RESOURCE_BUCKET = "OLD"

RESOURCE_TARGET_GROUPS = ("champions", "maps")

UPLOAD_DATABASE_SCHEMA_VERSION = 1

UPDATE_LOG_SCHEMA_VERSION = 1

UPDATE_LOG_REMOTE_DIR = "update_logs"

PENDING_MANIFEST_SYNC_QUEUE_FILE_NAME = "pending_manifest_sync_queue.json"

MANIFEST_UPLOAD_MAX_ATTEMPTS = 3

@dataclass(frozen=True, slots=True)
class _ArchiveUploadLayout:
    """压缩包上传路由信息。"""

    remote_name: str
    remote_relative_path: str
    remote_path: str
    target_group: str
    resource_type: str
    entity_key: str

@dataclass(frozen=True, slots=True)
class _IndexedArchiveMetadata:
    """远端索引条目解析结果。"""

    remote_path: str
    remote_name: str
    game_version: str | None
    target_group: str | None
    resource_type: str | None
    entity_key: str | None
    is_old_bucket: bool

def _pack_unpacked_outputs(config: PipelineConfig, game_version: str) -> tuple[Path, ...]:
    """将当前版本解包产物按目录批量打包。"""

    version_audio_dir = config.output_path / "audios" / game_version
    if not version_audio_dir.is_dir():
        logger.warning("未找到可打包目录：{}", version_audio_dir)
        return tuple()

    if config.pack_output_dir is not None:
        pack_root = config.pack_output_dir
    else:
        pack_root = _resolve_package_output_root(config=config, game_version=game_version)

    archives: list[Path] = []
    extra_files = _resolve_pack_extra_files(config=config)
    archive_audio_type = _resolve_pack_archive_type(config=config)
    if extra_files:
        logger.info("打包附加文件已启用：{}", ", ".join(str(item) for item in extra_files))
    if archive_audio_type is not None:
        logger.info("打包命名类型后缀：{}", archive_audio_type)
    pack_targets = (
        (
            "champions",
            version_audio_dir / "champions",
            config.output_path / "reports" / game_version / "champions",
        ),
        (
            "maps",
            version_audio_dir / "maps",
            config.output_path / "reports" / game_version / "maps",
        ),
    )
    for target_name, target_dir, report_dir in pack_targets:
        if not target_dir.is_dir():
            continue
        target_output_dir = pack_root / target_name
        packed = pack_all(
            audio_dir=target_dir,
            output_dir=target_output_dir,
            version=game_version,
            audio_type=archive_audio_type,
            report_dir=report_dir,
            password=config.pack_password,
            encrypt_filenames=config.pack_encrypt_filenames,
            extra_files=extra_files,
        )
        archives.extend(packed)
        logger.info(
            "打包完成：target={}, source={}, archive_count={}",
            target_name,
            target_dir,
            len(packed),
        )

    return tuple(sorted(archives, key=lambda path: path.as_posix().casefold()))

def _preflight_remote_upload_index(
    config: PipelineConfig,
    package_root: Path,
    allow_missing_remote_index: bool,
) -> dict[str, dict[str, object]]:
    """在主线更新确认阶段预检远端上传索引。"""

    if not (
        config.baidu_pan_app_key and config.baidu_pan_secret_key and config.baidu_pan_refresh_token
    ):
        raise ValueError("上传索引预检失败：缺少百度凭据，请配置 app_key/secret_key/refresh_token")

    credentials = BaiduCredentials(
        app_key=config.baidu_pan_app_key,
        secret_key=config.baidu_pan_secret_key,
        refresh_token=config.baidu_pan_refresh_token,
    )
    token_store = resolve_token_store()
    client = BaiduPanClient(
        credentials=credentials,
        remote_dir=config.baidu_pan_remote_dir,
        token_store=token_store,
    )
    try:
        _initialize_remote_upload_layout(client=client)
        remote_index = _load_remote_upload_manifest_index(
            client=client,
            package_root=package_root,
            allow_missing_remote_index=allow_missing_remote_index,
        )
        if remote_index:
            logger.info("更新确认阶段远端索引预检通过：entry_count={}", len(remote_index))
        elif allow_missing_remote_index:
            logger.info("更新确认阶段远端索引缺失，首次全量流程将自动初始化索引。")
        else:
            logger.info("更新确认阶段远端索引为空：entry_count=0")
        return _clone_upload_manifest_index(remote_index)
    finally:
        client.close()

def _upload_archives_and_manifest(
    config: PipelineConfig,
    game_version: str,
    archives: tuple[Path, ...],
    allow_missing_remote_index: bool = True,
    run_record_collector: list[dict[str, object]] | None = None,
    preloaded_remote_index: dict[str, dict[str, object]] | None = None,
    pending_manifest_sync_queue_file: Path | None = None,
) -> Path | None:
    """将打包产物上传到百度网盘，并同步本次上传清单。"""

    logger.debug(
        "进入上传阶段：game_version={}, archive_count={}, remote_dir={}",
        game_version,
        len(archives),
        config.baidu_pan_remote_dir,
    )
    if not archives:
        logger.warning("上传阶段跳过：无可上传压缩包。")
        return None

    if not (
        config.baidu_pan_app_key and config.baidu_pan_secret_key and config.baidu_pan_refresh_token
    ):
        raise ValueError("上传阶段缺少百度凭据，请配置 app_key/secret_key/refresh_token")

    package_root = _resolve_package_output_root(config=config, game_version=game_version)
    manifest_file = package_root / UPLOAD_MANIFEST_FILE_NAME
    readable_manifest_file = package_root / UPLOAD_MANIFEST_TEXT_FILE_NAME

    credentials = BaiduCredentials(
        app_key=config.baidu_pan_app_key,
        secret_key=config.baidu_pan_secret_key,
        refresh_token=config.baidu_pan_refresh_token,
    )
    token_store = resolve_token_store()
    client = BaiduPanClient(
        credentials=credentials,
        remote_dir=config.baidu_pan_remote_dir,
        token_store=token_store,
    )
    try:
        _initialize_remote_upload_layout(client=client)
        logger.debug("远端上传目录初始化完成。")
        remote_index = _resolve_upload_remote_index(
            client=client,
            package_root=package_root,
            allow_missing_remote_index=allow_missing_remote_index,
            preloaded_remote_index=preloaded_remote_index,
        )
        executed_at = _current_utc_timestamp()
        default_resource_type = _resolve_default_upload_resource_type(config=config)
        run_entries, has_index_changes = _process_archives_upload(
            client=client,
            archives=archives,
            remote_dir=config.baidu_pan_remote_dir,
            game_version=game_version,
            remote_index=remote_index,
            executed_at=executed_at,
            default_resource_type=default_resource_type,
        )
        return _finalize_upload_manifest(
            client=client,
            manifest_file=manifest_file,
            readable_manifest_file=readable_manifest_file,
            game_version=game_version,
            remote_dir=config.baidu_pan_remote_dir,
            remote_index=remote_index,
            run_entries=run_entries,
            has_index_changes=has_index_changes,
            executed_at=executed_at,
            run_record_collector=run_record_collector,
            refresh_remote_index_before_upload=preloaded_remote_index is not None,
            pending_manifest_sync_queue_file=pending_manifest_sync_queue_file,
        )
    finally:
        client.close()

def _resolve_upload_remote_index(
    client: BaiduPanClient,
    package_root: Path,
    allow_missing_remote_index: bool,
    preloaded_remote_index: dict[str, dict[str, object]] | None,
) -> dict[str, dict[str, object]]:
    """解析本次上传使用的远端索引快照。"""

    if preloaded_remote_index is not None:
        cloned = _clone_upload_manifest_index(preloaded_remote_index)
        logger.debug("上传阶段复用预加载索引快照：entry_count={}", len(cloned))
        return cloned
    logger.debug("开始加载远端上传索引。")
    remote_index = _load_remote_upload_manifest_index(
        client=client,
        package_root=package_root,
        allow_missing_remote_index=allow_missing_remote_index,
    )
    logger.debug("远端上传索引加载完成：entry_count={}", len(remote_index))
    return remote_index

def _clone_upload_manifest_index(
    source_index: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    """复制上传索引，避免调用方状态被就地污染。"""

    cloned: dict[str, dict[str, object]] = {}
    for key, value in source_index.items():
        cloned[key] = dict(value)
    return cloned

def _process_archives_upload(
    client: BaiduPanClient,
    archives: tuple[Path, ...],
    remote_dir: str,
    game_version: str,
    remote_index: dict[str, dict[str, object]],
    executed_at: str,
    default_resource_type: str,
) -> tuple[list[dict[str, object]], bool]:
    """处理一批压缩包上传并更新内存索引。"""

    run_entries: list[dict[str, object]] = []
    has_index_changes = False
    for archive in archives:
        if not archive.is_file():
            raise FileNotFoundError(f"上传失败：压缩包不存在：{archive}")

        upload_layout = _build_archive_upload_layout(
            archive=archive,
            remote_dir=remote_dir,
            default_resource_type=default_resource_type,
        )
        _ensure_remote_directory(
            client=client,
            relative_dir=f"{upload_layout.resource_type}/{upload_layout.target_group}",
        )
        archived_entries = _archive_remote_old_versions(
            client=client,
            remote_dir=remote_dir,
            remote_index=remote_index,
            layout=upload_layout,
            expected_game_version=game_version,
            executed_at=executed_at,
        )
        if archived_entries:
            has_index_changes = True
            run_entries.extend(archived_entries)

        remote_name = upload_layout.remote_name
        remote_path = upload_layout.remote_path
        existing_entry = remote_index.get(remote_path.casefold())
        if existing_entry is not None:
            if _is_same_index_entry(
                entry=existing_entry,
                expected_remote_name=remote_name,
                expected_game_version=game_version,
            ):
                logger.info("远端索引命中同文件，跳过上传：{}", remote_path)
                run_entries.append(
                    {
                        "local_path": str(archive),
                        "remote_path": remote_path,
                        "remote_name": remote_name,
                        "game_version": game_version,
                        "target_group": upload_layout.target_group,
                        "resource_type": upload_layout.resource_type,
                        "entity_key": upload_layout.entity_key,
                        "status": "skipped",
                        "reason": "remote_index_hit_same_version",
                    }
                )
                continue
            raise RuntimeError(
                "上传阶段终止：远端索引存在同路径但版本不一致文件，"
                f"remote_path={remote_path}, expected_game_version={game_version}"
            )

        if _remote_file_exists(client=client, remote_path=upload_layout.remote_relative_path):
            raise RuntimeError(
                "上传阶段终止：检测到远端已存在同名文件但索引缺失，"
                f"remote_path={remote_path}。请先修复远端索引后再重试。"
            )

        file_size = archive.stat().st_size
        file_sha256 = _calculate_sha256(archive)
        logger.debug(
            "开始上传压缩包：local={}, remote_path={}, size={}",
            archive,
            upload_layout.remote_relative_path,
            file_size,
        )
        response = client.upload_file(local_path=archive, remote_path=upload_layout.remote_relative_path)
        logger.debug(
            "压缩包上传完成：remote_path={}, response_keys={}",
            upload_layout.remote_relative_path,
            sorted(response.keys()) if isinstance(response, dict) else type(response),
        )
        has_index_changes = True
        remote_index[remote_path.casefold()] = {
            "remote_path": remote_path,
            "remote_name": remote_name,
            "bucket": upload_layout.resource_type,
            "game_version": game_version,
            "target_group": upload_layout.target_group,
            "resource_type": upload_layout.resource_type,
            "entity_key": upload_layout.entity_key,
            "size": file_size,
            "sha256": file_sha256,
            "uploaded_at": executed_at,
        }
        run_entries.append(
            {
                "local_path": str(archive),
                "remote_path": remote_path,
                "remote_name": remote_name,
                "size": file_size,
                "sha256": file_sha256,
                "target_group": upload_layout.target_group,
                "resource_type": upload_layout.resource_type,
                "entity_key": upload_layout.entity_key,
                "status": "uploaded",
                "reason": "uploaded",
                "response": response,
            }
        )
    return run_entries, has_index_changes

def _finalize_upload_manifest(
    client: BaiduPanClient,
    manifest_file: Path,
    readable_manifest_file: Path,
    game_version: str,
    remote_dir: str,
    remote_index: dict[str, dict[str, object]],
    run_entries: list[dict[str, object]],
    has_index_changes: bool,
    executed_at: str,
    run_record_collector: list[dict[str, object]] | None = None,
    refresh_remote_index_before_upload: bool = False,
    pending_manifest_sync_queue_file: Path | None = None,
) -> Path:
    """落地本地索引文件并按需回传到远端。"""

    effective_remote_index = _clone_upload_manifest_index(remote_index)
    if has_index_changes and refresh_remote_index_before_upload:
        try:
            latest_remote_index = _load_remote_upload_manifest_index(
                client=client,
                package_root=manifest_file.parent,
                allow_missing_remote_index=True,
            )
            effective_remote_index = _merge_remote_index_for_finalize(
                latest_remote_index=latest_remote_index,
                working_remote_index=effective_remote_index,
                run_entries=run_entries,
            )
        except Exception as error:  # noqa: BLE001
            logger.warning(
                "索引回传前刷新远端快照失败，降级使用本地索引：error={}",
                error,
            )

    manifest_payload = _build_upload_manifest_payload(
        game_version=game_version,
        index=effective_remote_index,
        run_entries=run_entries,
        executed_at=executed_at,
        remote_dir=remote_dir,
    )
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    manifest_file.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    readable_manifest_file.write_text(
        _build_readable_upload_manifest_content(
            index=effective_remote_index,
            game_version=game_version,
            executed_at=executed_at,
            remote_dir=remote_dir,
        ),
        encoding="utf-8",
    )
    if run_record_collector is not None:
        run_record_collector.extend(run_entries)
    if has_index_changes:
        logger.debug("开始回传上传索引文件。")
        upload_error: Exception | None = None
        for attempt in range(1, MANIFEST_UPLOAD_MAX_ATTEMPTS + 1):
            try:
                client.upload_file(local_path=manifest_file, remote_path=UPLOAD_MANIFEST_FILE_NAME)
                client.upload_file(
                    local_path=readable_manifest_file,
                    remote_path=UPLOAD_MANIFEST_TEXT_FILE_NAME,
                )
                upload_error = None
                logger.debug("上传索引文件回传完成。")
                break
            except Exception as error:  # noqa: BLE001
                upload_error = error
                logger.warning(
                    "上传索引文件失败，准备重试：attempt={}/{}, error={}",
                    attempt,
                    MANIFEST_UPLOAD_MAX_ATTEMPTS,
                    error,
                )
                if attempt < MANIFEST_UPLOAD_MAX_ATTEMPTS:
                    time.sleep(attempt)
        if upload_error is not None:
            logger.error("上传索引文件最终失败，将写入待重试队列：error={}", upload_error)
            _enqueue_pending_manifest_sync(
                queue_file=pending_manifest_sync_queue_file,
                manifest_file=manifest_file,
                readable_manifest_file=readable_manifest_file,
                remote_dir=remote_dir,
                error=upload_error,
            )
    else:
        logger.info("远端索引无变化，跳过索引文件回传。")
    return manifest_file

def _merge_remote_index_for_finalize(
    latest_remote_index: dict[str, dict[str, object]],
    working_remote_index: dict[str, dict[str, object]],
    run_entries: list[dict[str, object]],
) -> dict[str, dict[str, object]]:
    """将本次运行变更叠加到最新远端索引，降低并发覆盖风险。"""

    merged = _clone_upload_manifest_index(latest_remote_index)
    upsert_keys, removed_keys = _collect_remote_index_mutation_keys(run_entries=run_entries)
    for key in removed_keys:
        merged.pop(key, None)
    for key in upsert_keys:
        entry = working_remote_index.get(key)
        if entry is None:
            continue
        merged[key] = dict(entry)
    return merged

def _collect_remote_index_mutation_keys(
    run_entries: list[dict[str, object]],
) -> tuple[set[str], set[str]]:
    """提取本次运行对远端索引的增改键和删除键。"""

    upsert_keys: set[str] = set()
    removed_keys: set[str] = set()
    for entry in run_entries:
        remote_path_obj = entry.get("remote_path")
        if isinstance(remote_path_obj, str) and remote_path_obj.strip():
            upsert_keys.add(remote_path_obj.strip().replace("\\", "/").casefold())
        source_remote_path_obj = entry.get("source_remote_path")
        if isinstance(source_remote_path_obj, str) and source_remote_path_obj.strip():
            removed_keys.add(source_remote_path_obj.strip().replace("\\", "/").casefold())
    return upsert_keys, removed_keys

def _retry_pending_manifest_sync_queue(
    config: PipelineConfig,
    queue_file: Path,
) -> None:
    """重试历史失败的索引回传任务（失败不阻断主流程）。"""

    pending_entries = _load_pending_manifest_sync_entries(queue_file=queue_file)
    if not pending_entries:
        return
    if not (
        config.baidu_pan_app_key and config.baidu_pan_secret_key and config.baidu_pan_refresh_token
    ):
        logger.warning("待重试索引任务跳过：缺少百度凭据，queue_file={}", queue_file)
        return

    logger.info("检测到待重试索引任务：count={}, queue_file={}", len(pending_entries), queue_file)
    token_store = resolve_token_store()
    remaining_entries: list[dict[str, object]] = []
    for entry in pending_entries:
        remote_dir_obj = entry.get("remote_dir")
        manifest_file_obj = entry.get("manifest_file")
        readable_manifest_file_obj = entry.get("readable_manifest_file")
        if not (
            isinstance(remote_dir_obj, str)
            and isinstance(manifest_file_obj, str)
            and isinstance(readable_manifest_file_obj, str)
        ):
            logger.warning("待重试索引任务格式非法，已丢弃：entry={}", entry)
            continue
        manifest_file = Path(manifest_file_obj).expanduser().resolve()
        readable_manifest_file = Path(readable_manifest_file_obj).expanduser().resolve()
        if not (manifest_file.is_file() and readable_manifest_file.is_file()):
            logger.warning(
                "待重试索引任务文件缺失，已丢弃：manifest_file={}, readable_manifest_file={}",
                manifest_file,
                readable_manifest_file,
            )
            continue
        client = BaiduPanClient(
            credentials=BaiduCredentials(
                app_key=config.baidu_pan_app_key,
                secret_key=config.baidu_pan_secret_key,
                refresh_token=config.baidu_pan_refresh_token,
            ),
            remote_dir=remote_dir_obj,
            token_store=token_store,
        )
        try:
            client.upload_file(local_path=manifest_file, remote_path=UPLOAD_MANIFEST_FILE_NAME)
            client.upload_file(
                local_path=readable_manifest_file,
                remote_path=UPLOAD_MANIFEST_TEXT_FILE_NAME,
            )
            logger.info(
                "待重试索引任务回传成功：manifest_file={}, remote_dir={}",
                manifest_file,
                remote_dir_obj,
            )
        except Exception as error:  # noqa: BLE001
            logger.warning(
                "待重试索引任务仍失败，保留到队列：manifest_file={}, error={}",
                manifest_file,
                error,
            )
            updated_entry = dict(entry)
            updated_entry["last_error"] = str(error)
            updated_entry["last_attempt_at"] = _current_utc_timestamp()
            remaining_entries.append(updated_entry)
        finally:
            client.close()

    _save_pending_manifest_sync_entries(
        queue_file=queue_file,
        entries=remaining_entries,
    )

def _enqueue_pending_manifest_sync(
    queue_file: Path | None,
    manifest_file: Path,
    readable_manifest_file: Path,
    remote_dir: str,
    error: Exception,
) -> None:
    """将索引回传失败任务追加到本地待重试队列。"""

    if queue_file is None:
        logger.warning(
            "索引回传失败且未配置待重试队列：manifest_file={}, error={}",
            manifest_file,
            error,
        )
        return

    pending_entries = _load_pending_manifest_sync_entries(queue_file=queue_file)
    entry_key = f"{remote_dir.strip()}|{manifest_file.expanduser().resolve().as_posix()}".casefold()
    next_entries: list[dict[str, object]] = []
    for entry in pending_entries:
        remote_dir_obj = entry.get("remote_dir")
        manifest_file_obj = entry.get("manifest_file")
        if not (isinstance(remote_dir_obj, str) and isinstance(manifest_file_obj, str)):
            continue
        current_key = f"{remote_dir_obj.strip()}|{Path(manifest_file_obj).expanduser().resolve().as_posix()}".casefold()
        if current_key == entry_key:
            continue
        next_entries.append(entry)
    next_entries.append(
        {
            "remote_dir": remote_dir,
            "manifest_file": str(manifest_file.expanduser().resolve()),
            "readable_manifest_file": str(readable_manifest_file.expanduser().resolve()),
            "queued_at": _current_utc_timestamp(),
            "last_error": str(error),
        }
    )
    _save_pending_manifest_sync_entries(queue_file=queue_file, entries=next_entries)
    logger.warning(
        "索引回传失败已加入待重试队列：queue_file={}, manifest_file={}",
        queue_file,
        manifest_file,
    )

def _load_pending_manifest_sync_entries(queue_file: Path) -> list[dict[str, object]]:
    """读取待重试索引回传队列。"""

    if not queue_file.is_file():
        return []
    try:
        payload = json.loads(queue_file.read_text(encoding="utf-8"))
    except Exception as error:  # noqa: BLE001
        logger.warning("读取待重试索引队列失败，按空队列处理：queue_file={}, error={}", queue_file, error)
        return []
    if not isinstance(payload, list):
        return []
    entries: list[dict[str, object]] = []
    for item in payload:
        if isinstance(item, dict):
            entries.append(dict(item))
    return entries

def _save_pending_manifest_sync_entries(
    queue_file: Path,
    entries: list[dict[str, object]],
) -> None:
    """保存待重试索引回传队列。"""

    if not entries:
        queue_file.unlink(missing_ok=True)
        return
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    queue_file.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def _resolve_package_output_root(config: PipelineConfig, game_version: str) -> Path:
    """解析当前版本打包产物根目录。"""

    if config.pack_output_dir is not None:
        return config.pack_output_dir
    return config.output_path / "packages" / game_version

def _resolve_pack_extra_files(config: PipelineConfig) -> tuple[Path, ...]:
    """解析打包附加文件列表。"""

    candidate_dirs: list[Path] = []
    if config.pack_extra_dir is not None:
        candidate_dirs.append(config.pack_extra_dir)
    else:
        candidate_dirs.append(DEFAULT_BUNDLED_PACK_EXTRA_DIR)

    for directory in candidate_dirs:
        resolved_dir = directory.expanduser().resolve()
        if not resolved_dir.is_dir():
            continue
        files: list[Path] = []
        for file_name in DEFAULT_PACK_EXTRA_FILES:
            file_path = resolved_dir / file_name
            if file_path.is_file():
                files.append(file_path)
        if files:
            return tuple(files)
    return tuple()

def _resolve_pack_archive_type(config: PipelineConfig) -> str | None:
    """解析压缩包命名的类型后缀。"""

    normalized_types = sorted(
        {
            item.strip().upper()
            for item in config.audio_types
            if isinstance(item, str) and item.strip()
        }
    )
    if len(normalized_types) == 1:
        return normalized_types[0]
    return None

def _resolve_default_upload_resource_type(config: PipelineConfig) -> str:
    """解析上传阶段默认资源类型目录。"""

    archive_type = _resolve_pack_archive_type(config=config)
    if archive_type in RESOURCE_TYPE_BUCKETS:
        return archive_type
    for item in config.audio_types:
        if not isinstance(item, str):
            continue
        normalized = item.strip().upper()
        if normalized in RESOURCE_TYPE_BUCKETS:
            return normalized
    return RESOURCE_TYPE_BUCKETS[0]

def _build_archive_upload_layout(
    archive: Path,
    remote_dir: str,
    default_resource_type: str,
) -> _ArchiveUploadLayout:
    """解析单个压缩包的远端目录路由。"""

    target_group = _resolve_archive_target_group(archive=archive)
    entity_key, _, archive_resource_type = _parse_archive_file_name(archive.name)
    resource_type = archive_resource_type or default_resource_type
    remote_relative_path = f"{resource_type}/{target_group}/{archive.name}"
    return _ArchiveUploadLayout(
        remote_name=archive.name,
        remote_relative_path=remote_relative_path,
        remote_path=_join_remote_file_path(remote_dir=remote_dir, remote_name=remote_relative_path),
        target_group=target_group,
        resource_type=resource_type,
        entity_key=entity_key,
    )

def _resolve_archive_target_group(archive: Path) -> str:
    """从本地路径解析上传目标分组（champions/maps）。"""

    for part in reversed(archive.parts[:-1]):
        lowered = part.casefold()
        if lowered in RESOURCE_TARGET_GROUPS:
            return lowered
    return "champions"

def _parse_archive_file_name(
    archive_name: str,
) -> tuple[str, str | None, str | None]:
    """解析压缩包文件名中的实体名、版本和资源类型。"""

    if archive_name.casefold().endswith(".7z"):
        stem = archive_name[:-3]
    else:
        stem = archive_name
    normalized_stem = stem.strip()
    if not normalized_stem:
        return archive_name, None, None
    parts = normalized_stem.rsplit("-", maxsplit=2)
    if len(parts) != 3:
        return normalized_stem, None, None
    entity_key = parts[0].strip()
    parsed_version = parts[1].strip() or None
    parsed_resource_type = parts[2].strip().upper()
    if not entity_key:
        return normalized_stem, None, None
    if parsed_resource_type not in RESOURCE_TYPE_BUCKETS:
        return normalized_stem, None, None
    return entity_key, parsed_version, parsed_resource_type

def _archive_remote_old_versions(
    client: BaiduPanClient,
    remote_dir: str,
    remote_index: dict[str, dict[str, object]],
    layout: _ArchiveUploadLayout,
    expected_game_version: str,
    executed_at: str,
) -> list[dict[str, object]]:
    """将同实体旧版本远端文件归档到 `OLD/<target_group>/`。"""

    archived_entries: list[dict[str, object]] = []
    old_relative_dir = f"{OLD_RESOURCE_BUCKET}/{layout.target_group}"
    for index_key, index_entry in tuple(remote_index.items()):
        metadata = _resolve_index_entry_metadata(entry=index_entry, remote_dir=remote_dir)
        if metadata.remote_path.casefold() == layout.remote_path.casefold():
            continue
        if metadata.is_old_bucket:
            continue
        if metadata.target_group != layout.target_group:
            continue
        if metadata.resource_type != layout.resource_type:
            continue
        if metadata.entity_key != layout.entity_key:
            continue
        if metadata.game_version is None or metadata.game_version == expected_game_version:
            continue

        _ensure_remote_directory(client=client, relative_dir=old_relative_dir)
        client.move_path(
            source_path=metadata.remote_path,
            destination_dir=old_relative_dir,
            new_name=metadata.remote_name,
        )
        archived_remote_relative = f"{old_relative_dir}/{metadata.remote_name}"
        archived_remote_path = _join_remote_file_path(
            remote_dir=remote_dir,
            remote_name=archived_remote_relative,
        )
        updated_entry = dict(index_entry)
        updated_entry.update(
            {
                "remote_path": archived_remote_path,
                "remote_name": metadata.remote_name,
                "game_version": metadata.game_version,
                "bucket": OLD_RESOURCE_BUCKET,
                "target_group": layout.target_group,
                "resource_type": layout.resource_type,
                "entity_key": layout.entity_key,
                "uploaded_at": executed_at,
            }
        )
        remote_index.pop(index_key, None)
        remote_index[archived_remote_path.casefold()] = updated_entry
        logger.info(
            "发现同实体旧版本，已归档到 OLD：source={}, destination={}",
            metadata.remote_path,
            archived_remote_path,
        )
        archived_entries.append(
            {
                "remote_path": archived_remote_path,
                "source_remote_path": metadata.remote_path,
                "remote_name": metadata.remote_name,
                "game_version": metadata.game_version,
                "target_group": layout.target_group,
                "resource_type": layout.resource_type,
                "entity_key": layout.entity_key,
                "status": "archived_old",
                "reason": "previous_version_archived_to_old_bucket",
            }
        )
    return archived_entries

def _resolve_index_entry_metadata(
    entry: dict[str, object],
    remote_dir: str,
) -> _IndexedArchiveMetadata:
    """解析远端索引条目的路由元数据。"""

    remote_path_value = entry.get("remote_path")
    if not (isinstance(remote_path_value, str) and remote_path_value.strip()):
        raise ValueError(f"远端索引条目缺少 remote_path：{entry}")
    remote_path = remote_path_value.strip().replace("\\", "/")
    remote_name = str(entry.get("remote_name") or Path(remote_path).name).strip()
    raw_relative = _build_relative_remote_path(remote_path=remote_path, remote_dir=remote_dir)
    path_parts = [item for item in raw_relative.split("/") if item]
    bucket = path_parts[0].upper() if path_parts else ""
    target_group = (
        path_parts[1].casefold()
        if len(path_parts) >= 2 and path_parts[1].casefold() in RESOURCE_TARGET_GROUPS
        else None
    )
    parsed_entity_key, parsed_version, parsed_resource_type = _parse_archive_file_name(remote_name)
    entry_game_version = entry.get("game_version")
    game_version = (
        entry_game_version.strip()
        if isinstance(entry_game_version, str) and entry_game_version.strip()
        else parsed_version
    )
    entry_resource_type = entry.get("resource_type")
    if isinstance(entry_resource_type, str) and entry_resource_type.strip():
        resource_type = entry_resource_type.strip().upper()
    elif bucket in RESOURCE_TYPE_BUCKETS:
        resource_type = bucket
    else:
        resource_type = parsed_resource_type
    entry_entity_key = entry.get("entity_key")
    if isinstance(entry_entity_key, str) and entry_entity_key.strip():
        entity_key = entry_entity_key.strip()
    else:
        entity_key = parsed_entity_key
    entry_target_group = entry.get("target_group")
    if isinstance(entry_target_group, str) and entry_target_group.strip():
        normalized_target = entry_target_group.strip().casefold()
        if normalized_target in RESOURCE_TARGET_GROUPS:
            target_group = normalized_target
    is_old_bucket = bucket == OLD_RESOURCE_BUCKET
    return _IndexedArchiveMetadata(
        remote_path=remote_path,
        remote_name=remote_name,
        game_version=game_version,
        target_group=target_group,
        resource_type=resource_type,
        entity_key=entity_key,
        is_old_bucket=is_old_bucket,
    )

def _build_relative_remote_path(remote_path: str, remote_dir: str) -> str:
    """将绝对远端路径转换为工作目录下相对路径。"""

    normalized_remote_path = remote_path.strip().replace("\\", "/")
    if not normalized_remote_path.startswith("/"):
        normalized_remote_path = f"/{normalized_remote_path.lstrip('/')}"
    normalized_dir = remote_dir.strip().replace("\\", "/").strip("/")
    normalized_work_dir = f"/{normalized_dir}" if normalized_dir else "/"
    if normalized_work_dir == "/":
        return normalized_remote_path.lstrip("/")
    if normalized_remote_path.casefold().startswith(f"{normalized_work_dir}/".casefold()):
        return normalized_remote_path[len(normalized_work_dir) + 1 :]
    if normalized_remote_path.casefold() == normalized_work_dir.casefold():
        return ""
    return normalized_remote_path.lstrip("/")

def _ensure_remote_directory(client: BaiduPanClient, relative_dir: str) -> None:
    """确保远端目录存在（按层创建）。"""

    normalized = relative_dir.strip().replace("\\", "/").strip("/")
    if not normalized:
        return

    current = ""
    for segment in normalized.split("/"):
        current = f"{current}/{segment}" if current else segment
        if _remote_file_exists(client=client, remote_path=current):
            continue
        client.create_directory(dir_path=current)

def _initialize_remote_upload_layout(client: BaiduPanClient) -> None:
    """初始化远端目录结构。"""

    client.create_directory(dir_path=client.remote_dir)
    for resource_type in RESOURCE_TYPE_BUCKETS:
        for target_group in RESOURCE_TARGET_GROUPS:
            _ensure_remote_directory(client=client, relative_dir=f"{resource_type}/{target_group}")
    for target_group in RESOURCE_TARGET_GROUPS:
        _ensure_remote_directory(
            client=client, relative_dir=f"{OLD_RESOURCE_BUCKET}/{target_group}"
        )

def _build_readable_upload_manifest_content(
    index: dict[str, dict[str, object]],
    game_version: str,
    executed_at: str,
    remote_dir: str,
) -> str:
    """构建给人类阅读和搜索的上传索引文本。"""

    active_lines: list[str] = []
    archived_lines: list[str] = []
    for entry in sorted(
        index.values(),
        key=lambda item: str(item.get("remote_path", "")).casefold(),
    ):
        metadata = _resolve_index_entry_metadata(entry=entry, remote_dir=remote_dir)
        bucket = (
            OLD_RESOURCE_BUCKET if metadata.is_old_bucket else (metadata.resource_type or "UNKNOWN")
        )
        group = metadata.target_group or "unknown"
        entity_key = metadata.entity_key or metadata.remote_name
        version = metadata.game_version or "unknown"
        line = (
            f"- {bucket}/{group} | {metadata.remote_name} | version={version} | "
            f"entity={entity_key} | path={metadata.remote_path}"
        )
        if metadata.is_old_bucket:
            archived_lines.append(line)
        else:
            active_lines.append(line)

    lines: list[str] = [
        "# RiftAudioPipeline 网盘索引（可读版）",
        "",
        f"更新时间(UTC): {executed_at}",
        f"当前运行版本: {game_version}",
        f"总条目数: {len(index)}",
        "",
        "## 在线资源",
    ]
    if active_lines:
        lines.extend(active_lines)
    else:
        lines.append("- （无）")
    lines.extend(
        (
            "",
            "## OLD 归档资源",
        )
    )
    if archived_lines:
        lines.extend(archived_lines)
    else:
        lines.append("- （无）")
    lines.append("")
    return "\n".join(lines)

def _build_upload_database_payload(
    index: dict[str, dict[str, object]],
    remote_dir: str,
) -> dict[str, dict[str, object]]:
    """将远端索引聚合为实体维度数据库视图。"""

    grouped: dict[str, dict[str, object]] = {}
    for entry in sorted(
        index.values(),
        key=lambda item: str(item.get("remote_path", "")).casefold(),
    ):
        metadata = _resolve_index_entry_metadata(entry=entry, remote_dir=remote_dir)
        if metadata.target_group is None or metadata.resource_type is None:
            continue
        entity_key = metadata.entity_key or metadata.remote_name
        bucket = OLD_RESOURCE_BUCKET if metadata.is_old_bucket else metadata.resource_type
        db_key = f"{metadata.target_group}|{metadata.resource_type}|{entity_key}".casefold()
        bucket_obj = grouped.get(db_key)
        if bucket_obj is None:
            bucket_obj = {
                "entity_key": entity_key,
                "target_group": metadata.target_group,
                "resource_type": metadata.resource_type,
                "versions": [],
            }
            grouped[db_key] = bucket_obj
        versions = bucket_obj["versions"]
        if not isinstance(versions, list):
            continue
        versions.append(
            {
                "game_version": metadata.game_version,
                "remote_name": metadata.remote_name,
                "remote_path": metadata.remote_path,
                "bucket": bucket,
                "is_archived": metadata.is_old_bucket,
            }
        )

    normalized_grouped: dict[str, dict[str, object]] = {}
    for key, value in grouped.items():
        versions_obj = value.get("versions")
        versions = versions_obj if isinstance(versions_obj, list) else []
        sorted_versions = sorted(
            versions,
            key=lambda item: _parse_game_version_sort_key(
                str(item.get("game_version") or ""),
                str(item.get("remote_name") or ""),
            ),
        )
        latest_version = next(
            (
                item
                for item in reversed(sorted_versions)
                if not bool(item.get("is_archived", False))
            ),
            sorted_versions[-1] if sorted_versions else None,
        )
        normalized_grouped[key] = {
            "entity_key": value.get("entity_key"),
            "target_group": value.get("target_group"),
            "resource_type": value.get("resource_type"),
            "latest_game_version": latest_version.get("game_version") if latest_version else None,
            "latest_remote_name": latest_version.get("remote_name") if latest_version else None,
            "versions": sorted_versions,
        }
    return normalized_grouped

def _write_and_upload_update_log_files(
    config: PipelineConfig,
    decision: object,
    game_version: str,
    target_entities: object,
    targets: object,
    secondary_filter_result: object | None,
    upload_run_records: list[dict[str, object]],
) -> tuple[Path, Path]:
    """生成并上传每次 diff 的详细更新日志（JSON + 文本）。"""

    executed_at = _current_utc_timestamp()
    previous_version_obj = getattr(getattr(decision, "previous_state", None), "game_version", None)
    previous_version = (
        str(previous_version_obj).strip() if isinstance(previous_version_obj, str) else "unknown"
    )
    version_pair = f"{previous_version}~{game_version}"
    log_stem = f"{version_pair}_{executed_at.replace(':', '').replace('-', '')}"
    report_dir = config.output_path / "reports" / "update_logs" / game_version
    report_dir.mkdir(parents=True, exist_ok=True)
    json_file = report_dir / f"{log_stem}.json"
    text_file = report_dir / f"{log_stem}.txt"

    payload = _build_update_log_payload(
        decision=decision,
        game_version=game_version,
        executed_at=executed_at,
        target_entities=target_entities,
        targets=targets,
        secondary_filter_result=secondary_filter_result,
        upload_run_records=upload_run_records,
    )
    json_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    text_file.write_text(_build_update_log_text(payload=payload), encoding="utf-8")

    if not (
        config.baidu_pan_app_key and config.baidu_pan_secret_key and config.baidu_pan_refresh_token
    ):
        raise ValueError("更新日志上传失败：缺少百度凭据")

    credentials = BaiduCredentials(
        app_key=config.baidu_pan_app_key,
        secret_key=config.baidu_pan_secret_key,
        refresh_token=config.baidu_pan_refresh_token,
    )
    token_store = resolve_token_store()
    client = BaiduPanClient(
        credentials=credentials,
        remote_dir=config.baidu_pan_remote_dir,
        token_store=token_store,
    )
    try:
        remote_log_dir = f"{UPDATE_LOG_REMOTE_DIR}/{game_version}"
        _ensure_remote_directory(client=client, relative_dir=remote_log_dir)
        client.upload_file(
            local_path=json_file,
            remote_path=f"{remote_log_dir}/{json_file.name}",
        )
        client.upload_file(
            local_path=text_file,
            remote_path=f"{remote_log_dir}/{text_file.name}",
        )
    finally:
        client.close()

    return json_file, text_file

def _build_update_log_payload(
    decision: object,
    game_version: str,
    executed_at: str,
    target_entities: object,
    targets: object,
    secondary_filter_result: object | None,
    upload_run_records: list[dict[str, object]],
) -> dict[str, object]:
    """构建单次 diff 的结构化更新日志。"""

    changed_entities = {
        "champion_aliases": list(getattr(target_entities, "champion_aliases", tuple())),
        "map_ids": list(getattr(target_entities, "map_ids", tuple())),
    }
    processing_targets = {
        "champion_ids": list(getattr(targets, "champion_ids", tuple())),
        "map_ids": list(getattr(targets, "map_ids", tuple())),
    }
    wad_changes_obj = getattr(decision, "wad_changes", None)
    wad_changes = {
        "added_paths": list(getattr(wad_changes_obj, "added_paths", tuple())),
        "changed_paths": list(getattr(wad_changes_obj, "changed_paths", tuple())),
        "removed_paths": list(getattr(wad_changes_obj, "removed_paths", tuple())),
        "update_paths": list(getattr(wad_changes_obj, "update_paths", tuple())),
    }

    secondary_filter: dict[str, object] | None = None
    if secondary_filter_result is not None:
        decisions_obj = getattr(secondary_filter_result, "decisions", tuple())
        filter_decisions: list[dict[str, object]] = []
        for item in decisions_obj:
            path_statuses_obj = getattr(item, "path_statuses", tuple())
            path_statuses = [
                {
                    "path": str(getattr(status_item, "path", "")),
                    "status": str(getattr(status_item, "status", "")),
                    "path_type": str(getattr(status_item, "path_type", "")),
                }
                for status_item in path_statuses_obj
            ]
            filter_decisions.append(
                {
                    "region_wad_path": str(getattr(item, "region_wad_path", "")),
                    "root_wad_path": getattr(item, "root_wad_path", None),
                    "entity_type": str(getattr(item, "entity_type", "")),
                    "matched_bin_paths": list(getattr(item, "matched_bin_paths", tuple())),
                    "changed_audio_paths": list(getattr(item, "changed_audio_paths", tuple())),
                    "changed_event_paths": list(getattr(item, "changed_event_paths", tuple())),
                    "should_unpack": bool(getattr(item, "should_unpack", False)),
                    "skip_reason": getattr(item, "skip_reason", None),
                    "path_statuses": path_statuses,
                }
            )
        secondary_filter = {
            "unpack_paths": list(getattr(secondary_filter_result, "unpack_paths", tuple())),
            "skipped_paths": list(getattr(secondary_filter_result, "skipped_paths", tuple())),
            "decisions": filter_decisions,
        }

    uploaded_count = sum(1 for item in upload_run_records if item.get("status") == "uploaded")
    skipped_count = sum(1 for item in upload_run_records if item.get("status") == "skipped")
    archived_count = sum(1 for item in upload_run_records if item.get("status") == "archived_old")
    previous_state_obj = getattr(decision, "previous_state", None)
    previous_version = getattr(previous_state_obj, "game_version", None)
    payload: dict[str, object] = {
        "schema_version": UPDATE_LOG_SCHEMA_VERSION,
        "executed_at": executed_at,
        "decision_reason": str(getattr(decision, "reason", "")),
        "from_game_version": previous_version,
        "to_game_version": game_version,
        "changed_entities": changed_entities,
        "wad_changes": wad_changes,
        "processing_targets": processing_targets,
        "upload_summary": {
            "run_entry_count": len(upload_run_records),
            "uploaded_count": uploaded_count,
            "skipped_count": skipped_count,
            "archived_count": archived_count,
            "entries": upload_run_records,
        },
    }
    if secondary_filter is not None:
        payload["secondary_filter"] = secondary_filter
    return payload

def _load_remote_upload_manifest_index(
    client: BaiduPanClient,
    package_root: Path,
    allow_missing_remote_index: bool,
) -> dict[str, dict[str, object]]:
    """读取远端上传索引并构建内存查询表。

    Args:
        client: 百度网盘客户端。
        package_root: 当前版本打包根目录，用于临时落地远端索引文件。

    Returns:
        以 `remote_path.casefold()` 为键的索引字典。

    Raises:
        ValueError: 远端索引不是合法 JSON 或缺少 `entries` 列表。
        RuntimeError: 不允许缺失索引时，远端未找到索引文件。
    """

    temp_file = package_root / ".remote_upload_manifest.json"
    try:
        try:
            client.download_file(remote_path=UPLOAD_MANIFEST_FILE_NAME, local_path=temp_file)
        except FileNotFoundError:
            if not allow_missing_remote_index:
                raise RuntimeError(
                    "上传阶段终止：远端缺少上传索引 upload_manifest.json，"
                    "当前为差异更新流程，可能存在文件被手工移动或索引丢失，请先修复索引。"
                )
            logger.info("远端索引不存在，将创建新索引：{}", UPLOAD_MANIFEST_FILE_NAME)
            return {}
        except BaiduPanApiError as error:
            if error.errno == -9:
                if not allow_missing_remote_index:
                    raise RuntimeError(
                        "上传阶段终止：远端缺少上传索引 upload_manifest.json，"
                        "当前为差异更新流程，可能存在文件被手工移动或索引丢失，请先修复索引。"
                    ) from error
                logger.info("远端索引不存在（errno=-9），将创建新索引：{}", UPLOAD_MANIFEST_FILE_NAME)
                return {}
            raise

        try:
            payload = json.loads(temp_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(
                f"远端索引解析失败：{UPLOAD_MANIFEST_FILE_NAME} 不是合法 JSON。"
            ) from error

        if not isinstance(payload, dict):
            raise ValueError(f"远端索引格式错误：{UPLOAD_MANIFEST_FILE_NAME} 根对象必须为字典。")
        entries = payload.get("entries")
        return _build_upload_manifest_index(entries=entries)
    finally:
        temp_file.unlink(missing_ok=True)

def _build_upload_manifest_payload(
    game_version: str,
    index: dict[str, dict[str, object]],
    run_entries: list[dict[str, object]],
    executed_at: str,
    remote_dir: str,
) -> dict[str, object]:
    """构建上传索引快照。"""

    index_entries = tuple(
        sorted(
            index.values(),
            key=lambda entry: str(entry.get("remote_path", "")).casefold(),
        )
    )
    database = _build_upload_database_payload(index=index, remote_dir=remote_dir)
    uploaded_count = sum(1 for entry in run_entries if entry.get("status") == "uploaded")
    skipped_count = sum(1 for entry in run_entries if entry.get("status") == "skipped")
    archived_count = sum(1 for entry in run_entries if entry.get("status") == "archived_old")
    return {
        "schema_version": UPLOAD_MANIFEST_SCHEMA_VERSION,
        "updated_at": executed_at,
        "entry_count": len(index_entries),
        "entries": index_entries,
        "database_schema_version": UPLOAD_DATABASE_SCHEMA_VERSION,
        "database_entry_count": len(database),
        "database": database,
        "last_run": {
            "game_version": game_version,
            "executed_at": executed_at,
            "archive_count": len(run_entries),
            "uploaded_count": uploaded_count,
            "skipped_count": skipped_count,
            "archived_count": archived_count,
            "entries": run_entries,
        },
    }

def _remote_file_exists(client: BaiduPanClient, remote_path: str) -> bool:
    """判断远端路径是否已存在。"""

    try:
        client.get_path_entry(remote_path=remote_path)
        return True
    except FileNotFoundError:
        return False
