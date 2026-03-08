"""Pipeline 真实数据测试。

这组测试与单元测试分离，默认不运行。
启用方式：

```bash
RIFT_REAL_DATA_RUN=1 uv run pytest tests/test_pipeline_real_data.py -q -m real_data
```
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path

import pytest

import rift_audio_pipeline.pipeline.orchestrator as orchestrator
from rift_audio_pipeline.pipeline.models import ManifestPairRef
from rift_audio_pipeline.pipeline.models import PipelineMode
from rift_audio_pipeline.pipeline.models import PipelineRunConfig
from rift_audio_pipeline.pipeline.remote import build_remote_app_context
from rift_audio_pipeline.pipeline.remote import resolve_remote_manifest_pair

pytestmark = pytest.mark.real_data

REAL_DATA_ENV = "RIFT_REAL_DATA_RUN"
REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_ROOT = REPO_ROOT / "temp" / "real_data_cache" / "pipeline"
LATEST_PAIR_FILE = CACHE_ROOT / "latest_pair.json"
RECENT_PAIRS_FILE = CACHE_ROOT / "recent_pairs.json"
PREVIOUS_PAIR_FILE = CACHE_ROOT / "previous_pair.json"
REMOTE_CONTEXT_FILE = CACHE_ROOT / "remote_context.json"
MANIFEST_DIFF_FILE = CACHE_ROOT / "manifest_diff.json"
WAD_DIFF_FILE = CACHE_ROOT / "wad_diff.json"
RESOLVED_WAD_DIFF_FILE = CACHE_ROOT / "resolved_wad_diff.json"
PROCESSING_TARGETS_FILE = CACHE_ROOT / "processing_targets.json"


def test_real_resolve_remote_manifest_pair_should_cache_latest_pair() -> None:
    """应解析 live manifest pair 并缓存到本地。"""

    _require_real_data_enabled()
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)

    config = _build_real_data_config()
    pair = resolve_remote_manifest_pair(config)
    previous_payload = _load_json_file(LATEST_PAIR_FILE)
    current_payload = {
        **asdict(pair),
        "resolved_at": datetime.now().astimezone().isoformat(),
        "remote_live_region": config.remote_live_region,
    }

    recent_pairs = _update_recent_pairs_cache(current_payload)
    previous_distinct_pair = _find_previous_distinct_pair(recent_pairs)
    if previous_distinct_pair is not None:
        _write_json(PREVIOUS_PAIR_FILE, previous_distinct_pair)
    _write_json(LATEST_PAIR_FILE, current_payload)

    assert pair.version
    assert pair.lcu_manifest_url.startswith("https://")
    assert pair.game_manifest_url.startswith("https://")
    assert LATEST_PAIR_FILE.exists()
    assert RECENT_PAIRS_FILE.exists()
    if previous_payload is not None and _pair_payload_changed(previous_payload, current_payload):
        assert previous_distinct_pair is not None


def test_real_build_remote_app_context_should_cache_context_snapshot() -> None:
    """应基于真实 manifest trio 构造 remote 上下文并缓存关键字段。"""

    _require_real_data_enabled()
    pair = _load_pair_from_cache(LATEST_PAIR_FILE)
    if pair is None:
        pytest.skip("缺少 latest_pair 缓存，请先运行 manifest pair 真实测试。")

    config = _build_real_data_config()
    ctx = build_remote_app_context(config, pair)
    context_payload = {
        "source_mode": getattr(ctx.config.source_mode, "value", str(ctx.config.source_mode)),
        "game_region": ctx.config.game_region,
        "output_path": str(ctx.config.output_path),
        "remote_version": ctx.config.remote_snapshot.version
        if ctx.config.remote_snapshot
        else None,
        "remote_lcu_manifest_url": (
            ctx.config.remote_snapshot.lcu_manifest_url if ctx.config.remote_snapshot else None
        ),
        "remote_game_manifest_url": (
            ctx.config.remote_snapshot.game_manifest_url if ctx.config.remote_snapshot else None
        ),
        "generated_at": datetime.now().astimezone().isoformat(),
    }
    _write_json(REMOTE_CONTEXT_FILE, context_payload)

    assert context_payload["source_mode"] == "remote_snapshot"
    assert context_payload["game_region"] == config.game_region
    assert context_payload["remote_version"] == pair.version
    assert REMOTE_CONTEXT_FILE.exists()


def test_real_manifest_diff_should_cache_changed_paths_from_recent_pair() -> None:
    """应基于本地 recent pair 缓存做真实 manifest diff。"""

    _require_real_data_enabled()
    latest_pair = _load_pair_from_cache(LATEST_PAIR_FILE)
    if latest_pair is None:
        pytest.skip("缺少 latest_pair 缓存，请先运行 manifest pair 真实测试。")

    previous_pair = _load_previous_distinct_pair_from_recent_cache()
    if previous_pair is None:
        pytest.skip("缺少 recent_pairs 中的历史版本缓存，请先缓存几个近期版本。")

    report = orchestrator.build_manifest_diff_report(
        _build_real_data_config(),
        previous_pair=previous_pair,
        current_pair=latest_pair,
        include_unchanged=False,
    )
    changed_paths = sorted(
        {
            getattr(entry, "path")
            for entry in getattr(report, "changed", tuple())
            if getattr(entry, "path", None)
        }
    )
    payload = {
        "previous_version": previous_pair.version,
        "current_version": latest_pair.version,
        "baseline_source": "recent_cached_pair",
        "changed_paths": changed_paths,
        "generated_at": datetime.now().astimezone().isoformat(),
    }
    _write_json(MANIFEST_DIFF_FILE, payload)

    assert MANIFEST_DIFF_FILE.exists()
    assert payload["previous_version"] != payload["current_version"]
    assert payload["current_version"] == latest_pair.version


def test_real_build_processing_targets_should_consume_cached_manifest_diff() -> None:
    """应消费真实 diff 缓存并产出 processing targets。"""

    _require_real_data_enabled()
    latest_pair = _load_pair_from_cache(LATEST_PAIR_FILE)
    diff_payload = _load_json_file(MANIFEST_DIFF_FILE)
    if latest_pair is None:
        pytest.skip("缺少 latest_pair 缓存，请先运行 manifest pair 真实测试。")
    if diff_payload is None:
        pytest.skip("缺少 manifest_diff 缓存，请先运行 recent-pair manifest diff 测试。")

    config = _build_real_data_config()
    manifest_report = {
        "changed": [
            {"path": path}
            for path in diff_payload.get("changed_paths", [])
            if isinstance(path, str)
        ]
    }
    targets = orchestrator.build_processing_targets(
        config=config,
        previous_version=diff_payload.get("previous_version"),
        current_pair=latest_pair,
        manifest_report=manifest_report,
    )
    _write_json(
        PROCESSING_TARGETS_FILE,
        {
            "previous_version": diff_payload.get("previous_version"),
            "current_version": latest_pair.version,
            "target_count": len(targets),
            "targets": [
                {
                    "entity_type": target.entity_type,
                    "entity_id": target.entity_id,
                    "alias": target.alias,
                    "name": target.name,
                    "decision_reason": target.decision_reason,
                }
                for target in targets
            ],
            "generated_at": datetime.now().astimezone().isoformat(),
        },
    )

    assert isinstance(targets, tuple)
    assert all(target.entity_type in {"champion", "map"} for target in targets)
    assert PROCESSING_TARGETS_FILE.exists()


def test_real_wad_diff_should_cache_single_target_report() -> None:
    """应针对一个真实 WAD 缓存 header diff 结果。"""

    _require_real_data_enabled()
    latest_pair = _load_pair_from_cache(LATEST_PAIR_FILE)
    if latest_pair is None:
        pytest.skip("缺少 latest_pair 缓存，请先运行 manifest pair 真实测试。")

    manifest_report = orchestrator.build_manifest_diff_report(
        _build_real_data_config(),
        previous_pair=latest_pair,
        current_pair=latest_pair,
        include_unchanged=True,
    )
    target_wad_candidates = orchestrator.select_target_wad_paths(
        manifest_report,
        fallback_to_unchanged=True,
        limit=1,
    )
    target_wad = target_wad_candidates[0] if target_wad_candidates else None
    if target_wad is None:
        pytest.skip("未找到可用于真实 WAD diff 的目标 WAD。")

    targeted_manifest_report = orchestrator.build_manifest_diff_report(
        _build_real_data_config(),
        previous_pair=latest_pair,
        current_pair=latest_pair,
        include_unchanged=True,
    )
    wad_report = orchestrator.build_wad_diff_report(
        targeted_manifest_report,
        target_wad_files=(target_wad,),
        include_unchanged=True,
    )
    payload = {
        "target_wad": target_wad,
        "summary": wad_report.summary.__dict__,
        "files": [
            {
                "wad_path": entry.wad_path,
                "status": entry.status,
                "section_diff_count": len(entry.section_diffs),
                "missing_focused_paths": list(entry.missing_focused_paths),
            }
            for entry in wad_report.files
        ],
        "generated_at": datetime.now().astimezone().isoformat(),
    }
    _write_json(WAD_DIFF_FILE, payload)

    assert WAD_DIFF_FILE.exists()
    assert payload["target_wad"] == target_wad


def test_real_resolve_wad_diff_paths_should_cache_resolved_report() -> None:
    """应基于真实 WAD diff 做一次真实路径回填。"""

    _require_real_data_enabled()
    latest_pair = _load_pair_from_cache(LATEST_PAIR_FILE)
    wad_diff_payload = _load_json_file(WAD_DIFF_FILE)
    if latest_pair is None:
        pytest.skip("缺少 latest_pair 缓存，请先运行 manifest pair 真实测试。")
    if wad_diff_payload is None:
        pytest.skip("缺少 wad_diff 缓存，请先运行真实 WAD diff 测试。")

    target_wad = wad_diff_payload.get("target_wad")
    if not isinstance(target_wad, str):
        pytest.skip("wad_diff 缓存缺少 target_wad。")

    manifest_report = orchestrator.build_manifest_diff_report(
        _build_real_data_config(),
        previous_pair=latest_pair,
        current_pair=latest_pair,
        include_unchanged=True,
    )
    wad_report = orchestrator.build_wad_diff_report(
        manifest_report,
        target_wad_files=(target_wad,),
        include_unchanged=True,
        inner_paths={target_wad: _build_focus_inner_paths(target_wad)},
    )
    focus_inner_paths = _build_focus_inner_paths(target_wad)
    resolved_report = orchestrator.build_resolved_wad_diff_report(
        wad_report,
        focus_inner_paths=focus_inner_paths,
        max_skin_id=0,
        include_champion_root_bins=False,
        include_map_bins=False,
        include_section_statuses=("unchanged",),
    )

    resolved_paths = sorted(
        {
            section.path
            for file_entry in resolved_report.files
            for section in file_entry.section_diffs
            if section.path is not None
        }
    )
    _write_json(
        RESOLVED_WAD_DIFF_FILE,
        {
            "target_wad": target_wad,
            "resolved_path_count": len(resolved_paths),
            "resolved_paths": resolved_paths[:50],
            "generated_at": datetime.now().astimezone().isoformat(),
        },
    )

    assert RESOLVED_WAD_DIFF_FILE.exists()
    assert isinstance(resolved_paths, list)


def _build_real_data_config() -> PipelineRunConfig:
    """构造真实数据测试用配置。"""

    return PipelineRunConfig(
        mode=PipelineMode.REMOTE,
        game_region="zh_CN",
        output_root=CACHE_ROOT / "runtime_output",
        temp_root=CACHE_ROOT / "runtime_temp",
        log_root=CACHE_ROOT / "runtime_output" / "logs",
        baidu_remote_root="/apps/test",
        remote_live_region="EUW",
        include_maps=False,
        run_mapping=False,
    )


def _require_real_data_enabled() -> None:
    """未显式开启真实数据测试时跳过。"""

    if os.getenv(REAL_DATA_ENV) != "1":
        pytest.skip(f"未启用真实数据测试，请设置 {REAL_DATA_ENV}=1 后再运行。")


def _load_pair_from_cache(file_path: Path) -> ManifestPairRef | None:
    """从缓存读取 manifest pair。"""

    payload = _load_json_file(file_path)
    if payload is None:
        return None
    return ManifestPairRef(
        version=str(payload["version"]),
        lcu_manifest_url=str(payload["lcu_manifest_url"]),
        game_manifest_url=str(payload["game_manifest_url"]),
        match_mode=str(payload["match_mode"]),
        match_reason=str(payload["match_reason"]),
    )


def _load_previous_distinct_pair_from_recent_cache() -> ManifestPairRef | None:
    """从 recent cache 中读取上一个不同版本的 manifest pair。"""

    recent_pairs = _load_json_array(RECENT_PAIRS_FILE)
    if not recent_pairs:
        return None
    payload = _find_previous_distinct_pair(recent_pairs)
    if payload is None:
        return None
    return ManifestPairRef(
        version=str(payload["version"]),
        lcu_manifest_url=str(payload["lcu_manifest_url"]),
        game_manifest_url=str(payload["game_manifest_url"]),
        match_mode=str(payload["match_mode"]),
        match_reason=str(payload["match_reason"]),
    )


def _load_json_file(file_path: Path) -> dict[str, object] | None:
    """读取 JSON 文件，不存在时返回 `None`。"""

    if not file_path.exists():
        return None
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"缓存文件格式非法：{file_path}")
    return payload


def _load_json_array(file_path: Path) -> list[dict[str, object]]:
    """读取 JSON 数组文件，不存在时返回空列表。"""

    if not file_path.exists():
        return []
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"缓存文件格式非法：{file_path}")
    return [item for item in payload if isinstance(item, dict)]


def _write_json(file_path: Path, payload: dict[str, object]) -> None:
    """写入 JSON 文件。"""

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_json_array(file_path: Path, payload: list[dict[str, object]]) -> None:
    """写入 JSON 数组文件。"""

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _pair_payload_changed(
    previous_payload: dict[str, object],
    current_payload: dict[str, object],
) -> bool:
    """判断两次 manifest pair 缓存是否真的变化。"""

    keys = ("version", "lcu_manifest_url", "game_manifest_url", "match_mode")
    return any(previous_payload.get(key) != current_payload.get(key) for key in keys)


def _update_recent_pairs_cache(current_payload: dict[str, object]) -> list[dict[str, object]]:
    """更新 recent pair 本地缓存，只保留少量近期版本。"""

    existing_pairs = _load_json_array(RECENT_PAIRS_FILE)
    updated_pairs = [current_payload]
    for payload in existing_pairs:
        if _same_pair_identity(payload, current_payload):
            continue
        updated_pairs.append(payload)
    limited_pairs = updated_pairs[:5]
    _write_json_array(RECENT_PAIRS_FILE, limited_pairs)
    return limited_pairs


def _find_previous_distinct_pair(
    recent_pairs: list[dict[str, object]],
) -> dict[str, object] | None:
    """从 recent pairs 中找到当前 pair 之后第一个不同版本项。"""

    if not recent_pairs:
        return None
    latest_version = recent_pairs[0].get("version")
    for payload in recent_pairs[1:]:
        if payload.get("version") != latest_version:
            return payload
    return None


def _same_pair_identity(
    left_payload: dict[str, object],
    right_payload: dict[str, object],
) -> bool:
    """判断两份 manifest pair 缓存是否代表同一个版本快照。"""

    keys = ("version", "lcu_manifest_url", "game_manifest_url", "match_mode")
    return all(left_payload.get(key) == right_payload.get(key) for key in keys)


def _build_focus_inner_paths(target_wad: str) -> tuple[str, ...]:
    """为真实路径回填构造最小 inner_paths。"""

    normalized = target_wad.replace("\\", "/").lower()
    if "/champions/" in normalized:
        champion_name = target_wad.split("/")[-1].split(".")[0].lower()
        return (
            f"data/characters/{champion_name}/skins/skin0.bin",
            f"data/characters/{champion_name}/skins/root.bin",
        )
    if "/maps/shipping/" in normalized:
        map_name = target_wad.split("/")[-2].lower()
        return (
            f"data/maps/shipping/{map_name}/{map_name}.bin",
            "data/maps/shipping/common/common.bin",
        )
    return tuple()
