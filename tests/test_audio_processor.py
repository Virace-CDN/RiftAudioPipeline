"""语音编排适配层测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import lol_audio_unpack.manager as unpack_manager
import lol_audio_unpack.manager.data_reader as data_reader_module
import lol_audio_unpack.manager.utils as manager_utils
import lol_audio_unpack.unpack as unpack_module
import pytest

import rift_audio_pipeline.audio_processor as audio_processor
from rift_audio_pipeline.audio_processor import resolve_processing_targets
from rift_audio_pipeline.audio_processor import resolve_all_processing_targets
from rift_audio_pipeline.audio_processor import run_bin_updater
from rift_audio_pipeline.audio_processor import run_data_updater
from rift_audio_pipeline.audio_processor import run_unpack
from rift_audio_pipeline.audio_processor import run_unpack_by_entity


def test_run_data_updater_should_invoke_downstream_updater(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """应初始化配置并调用 DataUpdater。"""

    calls: dict[str, Any] = {}

    class _FakeDataUpdater:
        def __init__(self, languages: list[str], force_update: bool) -> None:
            calls["languages"] = languages
            calls["force_update"] = force_update

        def check_and_update(self) -> Path:
            return tmp_path / "manifest" / "16.4" / "data"

    monkeypatch.setattr(
        audio_processor,
        "_initialize_unpack_config",
        lambda game_path, output_path, region: calls.update(
            {"game_path": game_path, "output_path": output_path, "region": region}
        ),
    )
    monkeypatch.setattr(unpack_manager, "DataUpdater", _FakeDataUpdater)

    result = run_data_updater(
        game_path=tmp_path / "game",
        output_path=tmp_path / "output",
        region="zh_CN",
    )

    assert result == tmp_path / "manifest" / "16.4" / "data"
    assert calls["region"] == "zh_CN"
    assert calls["languages"] == ["zh_CN"]
    assert calls["force_update"] is False


def test_resolve_processing_targets_should_map_aliases_and_map_ids(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """应将英雄 alias 和地图 ID 规范化为整型 ID。"""

    monkeypatch.setattr(
        manager_utils,
        "read_data",
        lambda _: {
            "champions": {
                "103": {"alias": "Ahri"},
                "888": {"alias": "Renata"},
            },
        },
    )

    targets = resolve_processing_targets(
        data_file_base=tmp_path / "manifest" / "16.4" / "data",
        champion_aliases=("ahri", "RENATA"),
        map_ids=("11", "bad"),
    )

    assert targets.champion_ids == (103, 888)
    assert targets.map_ids == (11,)


def test_run_bin_updater_should_switch_between_incremental_and_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """有目标时应增量调用，无目标时应走全量调用。"""

    calls: list[dict[str, Any]] = []

    class _FakeBinUpdater:
        def __init__(self, force_update: bool, process_events: bool) -> None:
            calls.append(
                {
                    "kind": "init",
                    "force_update": force_update,
                    "process_events": process_events,
                }
            )

        def update(
            self,
            target: str = "all",
            champion_ids: list[str] | None = None,
            map_ids: list[str] | None = None,
        ) -> None:
            calls.append(
                {
                    "kind": "update",
                    "target": target,
                    "champion_ids": champion_ids,
                    "map_ids": map_ids,
                }
            )

    monkeypatch.setattr(unpack_manager, "BinUpdater", _FakeBinUpdater)

    run_bin_updater(champion_ids=(1, 2), map_ids=(11,), process_events=False)
    run_bin_updater(champion_ids=tuple(), map_ids=tuple(), process_events=False)

    assert calls[1] == {
        "kind": "update",
        "target": "all",
        "champion_ids": ["1", "2"],
        "map_ids": ["11"],
    }
    assert calls[3] == {
        "kind": "update",
        "target": "all",
        "champion_ids": None,
        "map_ids": None,
    }


def test_resolve_all_processing_targets_should_extract_all_ids(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """全量模式应读取 data 中全部英雄/地图 ID。"""

    monkeypatch.setattr(
        manager_utils,
        "read_data",
        lambda _: {
            "champions": {"103": {"alias": "Ahri"}, "bad": {"alias": "x"}, "1": {}},
            "maps": {"11": {}, "0": {}, "x": {}},
        },
    )

    targets = resolve_all_processing_targets(data_file_base=tmp_path / "manifest" / "16.4" / "data")
    assert targets.champion_ids == (1, 103)
    assert targets.map_ids == (0, 11)


def test_run_unpack_should_dispatch_incremental_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    """增量模式应按目标调用英雄/地图解包。"""

    calls: list[dict[str, Any]] = []

    class _FakeDataReader:
        def write_unknown_categories_to_file(self) -> None:
            calls.append({"kind": "write_unknown"})

    monkeypatch.setattr(data_reader_module, "DataReader", _FakeDataReader)
    monkeypatch.setattr(
        unpack_module,
        "unpack_champions",
        lambda reader, champion_ids, max_workers: calls.append(
            {
                "kind": "champions",
                "champion_ids": champion_ids,
                "max_workers": max_workers,
                "reader_type": type(reader).__name__,
            }
        ),
    )
    monkeypatch.setattr(
        unpack_module,
        "unpack_maps",
        lambda reader, map_ids, max_workers: calls.append(
            {
                "kind": "maps",
                "map_ids": map_ids,
                "max_workers": max_workers,
                "reader_type": type(reader).__name__,
            }
        ),
    )
    monkeypatch.setattr(
        unpack_module,
        "unpack_audio_all",
        lambda **_: calls.append({"kind": "all"}),
    )

    run_unpack(champion_ids=(1,), map_ids=(11,), max_workers=3)

    assert calls[0] == {
        "kind": "champions",
        "champion_ids": [1],
        "max_workers": 3,
        "reader_type": "_FakeDataReader",
    }
    assert calls[1] == {
        "kind": "maps",
        "map_ids": [11],
        "max_workers": 3,
        "reader_type": "_FakeDataReader",
    }
    assert calls[2] == {"kind": "write_unknown"}


def test_run_unpack_by_entity_should_split_into_single_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """按实体解包应拆分为多个单目标调用。"""

    calls: list[dict[str, Any]] = []

    monkeypatch.setattr(
        audio_processor,
        "run_unpack",
        lambda champion_ids, map_ids, max_workers: calls.append(
            {
                "champion_ids": champion_ids,
                "map_ids": map_ids,
                "max_workers": max_workers,
            }
        ),
    )

    run_unpack_by_entity(
        champion_ids=(1, 2),
        map_ids=(11,),
        max_workers=2,
    )

    assert calls == [
        {"champion_ids": (1,), "map_ids": tuple(), "max_workers": 2},
        {"champion_ids": (2,), "map_ids": tuple(), "max_workers": 2},
        {"champion_ids": tuple(), "map_ids": (11,), "max_workers": 2},
    ]
