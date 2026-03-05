"""多 Workflow 数据契约定义。"""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
import json
from os import PathLike
from pathlib import Path
from typing import Any
from typing import Literal

DiffSectionStatus = Literal["added", "removed", "changed", "unchanged"]
DiffWadStatus = Literal["added", "removed", "changed", "unchanged", "error"]

DIFF_REPORT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class DiffSectionChange:
    """WAD 内部 section 级别变更条目。"""

    status: DiffSectionStatus
    path: str
    real_path: str | None
    path_hash: str


@dataclass(frozen=True, slots=True)
class DiffWadEntry:
    """单个 WAD 文件的差异条目。"""

    wad_path: str
    status: DiffWadStatus
    changed_count: int
    changes: tuple[DiffSectionChange, ...]
    warning: str | None = None


@dataclass(frozen=True, slots=True)
class DiffReportStats:
    """差异报告统计信息。"""

    total_wad_count: int
    update_wad_count: int
    changed_section_count: int
    resolved_section_count: int
    unresolved_section_count: int


@dataclass(frozen=True, slots=True)
class DiffReport:
    """`workflow_diff_collect` 的结构化输出。"""

    schema_version: int
    region: str
    from_manifest_url: str
    to_manifest_url: str
    from_game_version: str | None
    to_game_version: str | None
    has_changes: bool
    wads: tuple[DiffWadEntry, ...]
    stats: DiffReportStats

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 兼容字典。"""

        return dict(asdict(self))

    def to_pretty_json(self, *, indent: int = 2, ensure_ascii: bool = False) -> str:
        """输出格式化 JSON 文本。"""

        return json.dumps(
            self.to_dict(),
            ensure_ascii=ensure_ascii,
            indent=indent,
            sort_keys=False,
        )

    def dump_pretty_json(
        self,
        output_path: str | PathLike[str],
        *,
        indent: int = 2,
        ensure_ascii: bool = False,
    ) -> str:
        """写入 JSON 文件并返回规范化路径。"""

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            self.to_pretty_json(indent=indent, ensure_ascii=ensure_ascii),
            encoding="utf-8",
        )
        return str(output)
