"""Manifest 更新判定真实联调测试。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request
from urllib.request import urlopen
import base64

from rift_audio_pipeline.manifest_ops import DECISION_REASON_FIRST_RUN
from rift_audio_pipeline.manifest_ops import DECISION_REASON_GAME_VERSION_UNCHANGED
from rift_audio_pipeline.manifest_ops import DECISION_REASON_REGION_MANIFEST_CHANGED
from rift_audio_pipeline.manifest_ops import LatestVersions
from rift_audio_pipeline.manifest_ops import LocalRunState
from rift_audio_pipeline.manifest_ops import UpdateDecision
from rift_audio_pipeline.manifest_ops import evaluate_update_need_with_latest
from rift_audio_pipeline.manifest_ops import filter_wad_changes_by_bin_voice_paths

GITHUB_API_BASE = (
    "https://api.github.com/repos/Morilli/riot-manifests/contents/LoL/EUW1/windows/lol-game-client"
)
TEST_REGION = "zh_CN"
LIVE_OUTPUT_DIR = Path("output/live_manifest_tests")


@dataclass(frozen=True, slots=True)
class LiveCase:
    """真实联调用例定义。"""

    name: str
    latest_version: str
    previous_version: str | None
    expected_should_update: bool | None
    expected_reason: str | None


def _http_get_json(url: str) -> dict[str, Any]:
    """执行 HTTP GET 并解析 JSON。"""

    request = Request(
        url=url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "RiftAudioPipeline-LiveTest",
        },
        method="GET",
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_manifest_url_from_repo(version: str) -> str:
    """从 Morilli 历史仓库读取指定版本的 manifest URL。"""

    file_name = f"{version}.txt"
    payload = _http_get_json(f"{GITHUB_API_BASE}/{quote(file_name)}")
    encoded_content = str(payload.get("content", "")).replace("\n", "")
    if not encoded_content:
        raise RuntimeError(f"读取版本清单失败，缺少 content 字段：{file_name}")
    return base64.b64decode(encoded_content).decode("utf-8").strip()


def _build_latest_versions(version: str, manifest_url: str) -> LatestVersions:
    """构建最新版本对象。"""

    return LatestVersions(
        game_version=version,
        game_manifest_url=manifest_url,
        lcu_version="16.4",
        lcu_manifest_url="https://example.invalid/lcu.manifest",
    )


def _build_previous_state(version: str, manifest_url: str) -> LocalRunState:
    """构建历史状态对象。"""

    return LocalRunState(
        schema_version=1,
        game_version=version,
        game_manifest_url=manifest_url,
        lcu_version="16.3",
        lcu_manifest_url="https://example.invalid/lcu-old.manifest",
        checked_at=datetime.now(tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
    )


def _run_case(case: LiveCase, manifest_urls: dict[str, str]) -> UpdateDecision:
    """执行单个测试用例。"""

    latest = _build_latest_versions(case.latest_version, manifest_urls[case.latest_version])
    previous_state = (
        None
        if case.previous_version is None
        else _build_previous_state(case.previous_version, manifest_urls[case.previous_version])
    )
    return evaluate_update_need_with_latest(
        region=TEST_REGION,
        latest_versions=latest,
        previous_state=previous_state,
    )


def main() -> int:
    """脚本主入口。"""

    versions = ["16.3.7457600", "16.4.7465697", "16.4.7480682"]
    manifest_urls: dict[str, str] = {}
    for version in versions:
        manifest_urls[version] = _fetch_manifest_url_from_repo(version)

    cases = [
        LiveCase(
            name="首次运行",
            latest_version="16.4.7480682",
            previous_version=None,
            expected_should_update=True,
            expected_reason=DECISION_REASON_FIRST_RUN,
        ),
        LiveCase(
            name="同版本跳过",
            latest_version="16.4.7480682",
            previous_version="16.4.7480682",
            expected_should_update=False,
            expected_reason=DECISION_REASON_GAME_VERSION_UNCHANGED,
        ),
        LiveCase(
            name="16.3->16.4（已知有语音变更）",
            latest_version="16.4.7480682",
            previous_version="16.3.7457600",
            expected_should_update=True,
            expected_reason=DECISION_REASON_REGION_MANIFEST_CHANGED,
        ),
        LiveCase(
            name="16.4 小版本构建变更",
            latest_version="16.4.7480682",
            previous_version="16.4.7465697",
            expected_should_update=None,
            expected_reason=None,
        ),
    ]

    results: list[dict[str, Any]] = []
    failed: list[str] = []

    for case in cases:
        decision = _run_case(case, manifest_urls)
        result = {
            "case": case.name,
            "latest_version": case.latest_version,
            "previous_version": case.previous_version,
            "should_update": decision.should_update,
            "reason": decision.reason,
            "champion_count": len(decision.changed_entities.champion_aliases),
            "map_count": len(decision.changed_entities.map_ids),
            "added_wad_count": len(decision.wad_changes.added_paths),
            "changed_wad_count": len(decision.wad_changes.changed_paths),
            "removed_wad_count": len(decision.wad_changes.removed_paths),
            "update_wad_count": len(decision.wad_changes.update_paths),
            "champion_sample": list(decision.changed_entities.champion_aliases[:10]),
            "map_ids": list(decision.changed_entities.map_ids),
        }
        results.append(result)

        if (
            case.expected_should_update is not None
            and decision.should_update != case.expected_should_update
        ):
            failed.append(
                f"{case.name}: should_update 期望 {case.expected_should_update}，实际 {decision.should_update}"
            )
        if case.expected_reason is not None and decision.reason != case.expected_reason:
            failed.append(
                f"{case.name}: reason 期望 {case.expected_reason}，实际 {decision.reason}"
            )

    print("=== 历史 manifest 来源（Morilli）===")
    print(json.dumps(manifest_urls, ensure_ascii=False, indent=2))
    print("=== 真实联调结果 ===")
    print(json.dumps(results, ensure_ascii=False, indent=2))

    detail_case_name = "16.3->16.4（已知有语音变更）"
    detail_decision: UpdateDecision | None = None
    for case in cases:
        if case.name == detail_case_name:
            detail_decision = _run_case(case, manifest_urls)
            break

    if detail_decision is not None:
        secondary_filter = filter_wad_changes_by_bin_voice_paths(
            old_manifest_url=manifest_urls["16.3.7457600"],
            new_manifest_url=manifest_urls["16.4.7480682"],
            region=TEST_REGION,
            update_paths=detail_decision.wad_changes.update_paths,
        )
        detail_payload = {
            "case": detail_case_name,
            "region": TEST_REGION,
            "old_version": "16.3.7457600",
            "new_version": "16.4.7480682",
            "old_manifest_url": manifest_urls["16.3.7457600"],
            "new_manifest_url": manifest_urls["16.4.7480682"],
            "added_paths": list(detail_decision.wad_changes.added_paths),
            "changed_paths": list(detail_decision.wad_changes.changed_paths),
            "removed_paths": list(detail_decision.wad_changes.removed_paths),
            "update_paths": list(detail_decision.wad_changes.update_paths),
            "secondary_filter": {
                "unpack_paths": list(secondary_filter.unpack_paths),
                "skipped_paths": list(secondary_filter.skipped_paths),
                "decisions": [
                    {
                        "region_wad_path": item.region_wad_path,
                        "root_wad_path": item.root_wad_path,
                        "entity_type": item.entity_type,
                        "matched_bin_count": len(item.matched_bin_paths),
                        "audio_path_count": len(item.audio_paths),
                        "event_path_count": len(item.event_paths),
                        "changed_audio_paths": list(item.changed_audio_paths),
                        "changed_event_paths": list(item.changed_event_paths),
                        "should_unpack": item.should_unpack,
                        "skip_reason": item.skip_reason,
                    }
                    for item in secondary_filter.decisions
                ],
            },
        }
        LIVE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        detail_file = LIVE_OUTPUT_DIR / "manifest_diff_16_3_to_16_4_zh_CN.json"
        detail_file.write_text(
            json.dumps(detail_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("=== 16.3 -> 16.4 可更新 WAD 路径（update_paths）===")
        for path in detail_decision.wad_changes.update_paths:
            print(path)
        print("=== 16.3 -> 16.4 需解包 WAD 路径（secondary_filter.unpack_paths）===")
        for path in secondary_filter.unpack_paths:
            print(path)
        print(f"=== 详细结果已写入：{detail_file} ===")

    if failed:
        print("=== 断言失败 ===")
        for item in failed:
            print(f"- {item}")
        return 1

    print("=== 断言通过 ===")
    print("- 首次运行：应更新")
    print("- 同版本：应跳过")
    print("- 16.3 -> 16.4：检测到 zh_CN 语音变更，应更新")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
