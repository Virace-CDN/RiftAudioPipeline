"""百度网盘客户端单元测试。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from rift_audio_pipeline.baidu.oauth import BaiduOAuthToken
from rift_audio_pipeline.baidu.pan import BaiduCredentials
from rift_audio_pipeline.baidu.pan import BaiduPanApiError
from rift_audio_pipeline.baidu.pan import BaiduPanClient
from rift_audio_pipeline.baidu.pan import BaiduPanScopeWarning
import rift_audio_pipeline.baidu.pan as pan_module


class _FakeApiException(Exception):
    """模拟官方 SDK 的 ApiException。"""

    def __init__(self, message: str = "api error") -> None:
        """初始化异常对象。"""

        super().__init__(message)
        self.status = 500
        self.reason = "mock-error"
        self.body = message


class _FakeHttpResponse:
    """模拟下载流响应对象。"""

    def __init__(self, chunks: list[bytes]) -> None:
        """初始化下载流。"""

        self._chunks = list(chunks)
        self._index = 0
        self.released = False

    def read(self, _: int) -> bytes:
        """读取下载分片。"""

        if self._index >= len(self._chunks):
            return b""
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk

    def release_conn(self) -> None:
        """释放连接。"""

        self.released = True


@dataclass
class _FakeRuntime:
    """承载测试期运行态。"""

    api_client: Any = None
    fileinfo_api: Any = None
    filemanager_api: Any = None
    fileupload_api: Any = None
    multimedia_api: Any = None
    userinfo_api: Any = None


def _make_token(
    access_token: str = "access_token_value",
    refresh_token: str = "refresh_token_value",
    expires_in: int = 3600,
    obtained_at: datetime | None = None,
) -> BaiduOAuthToken:
    """构建测试用 OAuth token。"""

    now = obtained_at or datetime.now(tz=timezone.utc)
    return BaiduOAuthToken(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        scope="basic,netdisk",
        session_key=None,
        session_secret=None,
        obtained_at=now.isoformat(timespec="seconds").replace("+00:00", "Z"),
    )


def _build_client(
    monkeypatch: pytest.MonkeyPatch,
    remote_dir: str = "/apps/rift-audio-pipeline",
) -> tuple[BaiduPanClient, _FakeRuntime]:
    """构建可离线测试的 BaiduPanClient。"""

    runtime = _FakeRuntime()

    class _FakeApiClient:
        """模拟官方 ApiClient。"""

        def __init__(self) -> None:
            self.closed = False
            self.call_api_calls: list[dict[str, Any]] = []
            self.download_chunks: list[bytes] = [b"mock-download-data"]
            self.call_api_failures = 0
            runtime.api_client = self

        def call_api(self, **kwargs: Any) -> _FakeHttpResponse:
            """模拟 call_api 下载接口。"""

            self.call_api_calls.append(kwargs)
            if self.call_api_failures > 0:
                self.call_api_failures -= 1
                raise _FakeApiException("mock-call-api-error")
            return _FakeHttpResponse(chunks=self.download_chunks)

        def close(self) -> None:
            """模拟关闭连接池。"""

            self.closed = True

    class _FakeFileinfoApi:
        """模拟 fileinfo API。"""

        def __init__(self, _: Any) -> None:
            self.calls: list[dict[str, Any]] = []
            self.listing_by_dir: dict[str, dict[str, Any]] = {}
            runtime.fileinfo_api = self

        def xpanfilelist(self, access_token: str, **kwargs: Any) -> dict[str, Any]:
            """模拟目录列表接口。"""

            self.calls.append({"access_token": access_token, **kwargs})
            dir_value = str(kwargs["dir"])
            return self.listing_by_dir.get(dir_value, {"errno": 0, "list": []})

    class _FakeFilemanagerApi:
        """模拟 filemanager API。"""

        def __init__(self, _: Any) -> None:
            self.rename_calls: list[dict[str, Any]] = []
            self.copy_calls: list[dict[str, Any]] = []
            self.move_calls: list[dict[str, Any]] = []
            self.delete_calls: list[dict[str, Any]] = []
            self.rename_response: dict[str, Any] = {"errno": 0}
            self.copy_response: dict[str, Any] = {"errno": 0}
            self.move_response: dict[str, Any] = {"errno": 0}
            self.delete_response: dict[str, Any] = {"errno": 0}
            runtime.filemanager_api = self

        def filemanagerrename(
            self,
            access_token: str,
            async_id: int,
            filelist: str,
            ondup: str,
        ) -> dict[str, Any]:
            """模拟 rename 操作。"""

            self.rename_calls.append(
                {
                    "access_token": access_token,
                    "async": async_id,
                    "filelist": json.loads(filelist),
                    "ondup": ondup,
                }
            )
            return self.rename_response

        def filemanagercopy(
            self,
            access_token: str,
            async_id: int,
            filelist: str,
            ondup: str,
        ) -> dict[str, Any]:
            """模拟 copy 操作。"""

            self.copy_calls.append(
                {
                    "access_token": access_token,
                    "async": async_id,
                    "filelist": json.loads(filelist),
                    "ondup": ondup,
                }
            )
            return self.copy_response

        def filemanagermove(
            self,
            access_token: str,
            async_id: int,
            filelist: str,
            ondup: str,
        ) -> dict[str, Any]:
            """模拟 move 操作。"""

            self.move_calls.append(
                {
                    "access_token": access_token,
                    "async": async_id,
                    "filelist": json.loads(filelist),
                    "ondup": ondup,
                }
            )
            return self.move_response

        def filemanagerdelete(
            self,
            access_token: str,
            async_id: int,
            filelist: str,
        ) -> dict[str, Any]:
            """模拟 delete 操作。"""

            self.delete_calls.append(
                {
                    "access_token": access_token,
                    "async": async_id,
                    "filelist": json.loads(filelist),
                }
            )
            return self.delete_response

    class _FakeFileuploadApi:
        """模拟 fileupload API。"""

        def __init__(self, _: Any) -> None:
            self.create_calls: list[dict[str, Any]] = []
            self.precreate_calls: list[dict[str, Any]] = []
            self.part_calls: list[dict[str, Any]] = []
            self.precreate_response: dict[str, Any] = {"errno": 0, "uploadid": "upload-id-001"}
            runtime.fileupload_api = self

        def xpanfilecreate(
            self,
            access_token: str,
            path: str,
            isdir: int,
            size: int,
            uploadid: str,
            block_list: str,
            rtype: int,
            **kwargs: Any,
        ) -> dict[str, Any]:
            """模拟 xpanfilecreate。"""

            call_data = {
                "access_token": access_token,
                "path": path,
                "isdir": isdir,
                "size": size,
                "uploadid": uploadid,
                "block_list": block_list,
                "rtype": rtype,
                **kwargs,
            }
            self.create_calls.append(call_data)
            if isdir == 1:
                return {"errno": 0, "path": path}
            return {"errno": 0, "path": path, "fs_id": "10001"}

        def xpanfileprecreate(
            self,
            access_token: str,
            path: str,
            isdir: int,
            size: int,
            autoinit: int,
            block_list: str,
            rtype: int,
            **kwargs: Any,
        ) -> dict[str, Any]:
            """模拟预上传接口。"""

            self.precreate_calls.append(
                {
                    "access_token": access_token,
                    "path": path,
                    "isdir": isdir,
                    "size": size,
                    "autoinit": autoinit,
                    "block_list": block_list,
                    "rtype": rtype,
                    **kwargs,
                }
            )
            return self.precreate_response

        def pcssuperfile2(
            self,
            access_token: str,
            partseq: str,
            path: str,
            uploadid: str,
            file_type: str,
            file: Any,
            **kwargs: Any,
        ) -> dict[str, Any]:
            """模拟分片上传接口。"""

            chunk = file.read()
            md5_value = hashlib.md5(chunk).hexdigest()
            self.part_calls.append(
                {
                    "access_token": access_token,
                    "partseq": partseq,
                    "path": path,
                    "uploadid": uploadid,
                    "type": file_type,
                    "md5": md5_value,
                    **kwargs,
                }
            )
            return {"errno": 0, "md5": md5_value}

    class _FakeMultimediaApi:
        """模拟 multimedia API。"""

        def __init__(self, _: Any) -> None:
            self.calls: list[dict[str, Any]] = []
            self.response: dict[str, Any] = {"errno": 0, "list": [{"size": 1, "md5": "abc"}]}
            runtime.multimedia_api = self

        def xpanmultimediafilemetas(
            self,
            access_token: str,
            fsids: str,
            thumb: str,
            extra: str,
            dlink: str,
            needmedia: int,
        ) -> dict[str, Any]:
            """模拟 filemetas 接口。"""

            self.calls.append(
                {
                    "access_token": access_token,
                    "fsids": fsids,
                    "thumb": thumb,
                    "extra": extra,
                    "dlink": dlink,
                    "needmedia": needmedia,
                }
            )
            return self.response

    class _FakeUserinfoApi:
        """模拟 userinfo API。"""

        def __init__(self, _: Any) -> None:
            self.calls: list[dict[str, Any]] = []
            self.response: dict[str, Any] = {"errno": 0, "total": 1000, "used": 200}
            runtime.userinfo_api = self

        def apiquota(self, access_token: str, checkexpire: int, checkfree: int) -> dict[str, Any]:
            """模拟容量查询接口。"""

            self.calls.append(
                {
                    "access_token": access_token,
                    "checkexpire": checkexpire,
                    "checkfree": checkfree,
                }
            )
            return self.response

    module_mapping = {
        "openapi_client.api.fileinfo_api": SimpleNamespace(FileinfoApi=_FakeFileinfoApi),
        "openapi_client.api.filemanager_api": SimpleNamespace(FilemanagerApi=_FakeFilemanagerApi),
        "openapi_client.api.fileupload_api": SimpleNamespace(FileuploadApi=_FakeFileuploadApi),
        "openapi_client.api.multimediafile_api": SimpleNamespace(
            MultimediafileApi=_FakeMultimediaApi
        ),
        "openapi_client.api.userinfo_api": SimpleNamespace(UserinfoApi=_FakeUserinfoApi),
        "openapi_client.exceptions": SimpleNamespace(ApiException=_FakeApiException),
    }

    def _fake_import_module(module_name: str) -> Any:
        """模拟动态导入 SDK 子模块。"""

        return module_mapping[module_name]

    monkeypatch.setattr(pan_module, "ensure_official_sdk_path", lambda: Path("/tmp/baidu_sdk"))
    monkeypatch.setattr(
        pan_module,
        "load_openapi_client_module",
        lambda: SimpleNamespace(ApiClient=_FakeApiClient),
    )
    monkeypatch.setattr(pan_module.importlib, "import_module", _fake_import_module)

    client = BaiduPanClient(
        credentials=BaiduCredentials(
            app_key="test_app_key",
            secret_key="test_secret_key",
            refresh_token="test_refresh_token",
        ),
        remote_dir=remote_dir,
        token_store=None,
    )
    client._oauth_token = _make_token()
    return client, runtime


def test_list_files_should_resolve_relative_path_under_work_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """相对路径应自动解析到工作目录下。"""

    client, runtime = _build_client(monkeypatch)
    runtime.fileinfo_api.listing_by_dir["/apps/rift-audio-pipeline/subdir"] = {
        "errno": 0,
        "list": [{"path": "/apps/rift-audio-pipeline/subdir/demo.txt", "isdir": 0}],
    }

    payload = client.list_files("subdir")

    assert payload["list"][0]["path"] == "/apps/rift-audio-pipeline/subdir/demo.txt"
    assert runtime.fileinfo_api.calls[-1]["dir"] == "/apps/rift-audio-pipeline/subdir"


def test_create_directory_should_block_outside_work_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """工作目录外建目录应被拦截。"""

    client, _ = _build_client(monkeypatch)

    with pytest.raises(ValueError, match="超限提示"):
        client.create_directory("/outside-dir")


def test_create_directory_should_block_path_traversal(monkeypatch: pytest.MonkeyPatch) -> None:
    """相对路径包含 `..` 时应阻断越界。"""

    client, _ = _build_client(monkeypatch)

    with pytest.raises(ValueError, match="超限提示"):
        client.create_directory("../escape-dir")


def test_ensure_directory_should_create_missing_nested_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """递归确保目录时，应逐级创建缺失的父目录。"""

    client, runtime = _build_client(monkeypatch)

    normalized = client.ensure_directory("history/champions")

    assert normalized == "/apps/rift-audio-pipeline/history/champions"
    assert [call["path"] for call in runtime.fileupload_api.create_calls[-2:]] == [
        "/apps/rift-audio-pipeline/history",
        "/apps/rift-audio-pipeline/history/champions",
    ]


def test_ensure_directory_should_create_missing_work_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """工作目录本身缺失时，也应先创建工作目录。"""

    client, runtime = _build_client(monkeypatch)
    list_calls = {"count": 0}

    def _missing_root(dir_path: str, limit: int = 1000, start: int = 0):
        del limit, start
        assert dir_path == ""
        list_calls["count"] += 1
        raise BaiduPanApiError("missing dir", errno=-9)

    monkeypatch.setattr(client, "list_files", _missing_root)

    normalized = client.ensure_directory("")

    assert normalized == "/apps/rift-audio-pipeline"
    assert list_calls["count"] == 1
    assert runtime.fileupload_api.create_calls[-1]["path"] == "/apps/rift-audio-pipeline"


def test_move_path_should_warn_when_destination_outside_work_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """移动到工作目录外时应发出超限提示告警。"""

    client, runtime = _build_client(monkeypatch)

    with pytest.warns(BaiduPanScopeWarning, match="超限提示"):
        payload = client.move_path(
            source_path="work/result.txt",
            destination_dir="/final-archive",
            new_name="result-final.txt",
        )

    assert payload["errno"] == 0
    move_item = runtime.filemanager_api.move_calls[-1]["filelist"][0]
    assert move_item["path"] == "/apps/rift-audio-pipeline/work/result.txt"
    assert move_item["dest"] == "/final-archive"
    assert move_item["newname"] == "result-final.txt"


def test_copy_path_should_block_outside_destination(monkeypatch: pytest.MonkeyPatch) -> None:
    """复制到工作目录外应被拦截。"""

    client, _ = _build_client(monkeypatch)

    with pytest.raises(ValueError, match="超限提示"):
        client.copy_path(
            source_path="work/input.txt",
            destination_dir="/outside-dir",
            new_name="copied.txt",
        )


def test_delete_paths_should_block_outside_work_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """批量删除包含越界路径时应被拦截。"""

    client, runtime = _build_client(monkeypatch)

    with pytest.raises(ValueError, match="超限提示"):
        client.delete_paths(paths=["work/a.txt", "/outside/b.txt"])

    assert runtime.filemanager_api.delete_calls == []


def test_upload_file_should_complete_precreate_upload_create(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """上传应依次执行 precreate/superfile2/create。"""

    client, runtime = _build_client(monkeypatch)
    local_file = tmp_path / "sample.txt"
    local_file.write_bytes(b"hello-baidu")

    payload = client.upload_file(local_path=local_file, remote_path="upload/sample.txt")

    assert payload["path"] == "/apps/rift-audio-pipeline/upload/sample.txt"
    assert (
        runtime.fileupload_api.precreate_calls[-1]["path"]
        == "/apps/rift-audio-pipeline/upload/sample.txt"
    )
    assert len(runtime.fileupload_api.part_calls) == 1
    assert runtime.fileupload_api.create_calls[-1]["isdir"] == 0


def test_upload_file_should_forward_timeouts_and_emit_progress(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """上传应带显式超时，并输出阶段级进度。"""

    client, runtime = _build_client(monkeypatch)
    local_file = tmp_path / "sample.bin"
    local_file.write_bytes(b"hello-baidu")
    progress_events: list[dict[str, Any]] = []

    client.upload_file(
        local_path=local_file,
        remote_path="upload/sample.bin",
        progress_callback=progress_events.append,
    )

    assert runtime.fileupload_api.precreate_calls[-1]["_request_timeout"] == (30, 180)
    assert runtime.fileupload_api.part_calls[-1]["_request_timeout"] == (30, 180)
    assert runtime.fileupload_api.create_calls[-1]["_request_timeout"] == (30, 180)
    assert [event["phase"] for event in progress_events] == [
        "precreate",
        "precreate",
        "part_upload",
        "part_upload",
        "create",
        "create",
    ]
    assert [event["status"] for event in progress_events] == [
        "started",
        "completed",
        "started",
        "completed",
        "started",
        "completed",
    ]
    assert isinstance(progress_events[0]["local_path"], str)
    assert progress_events[0]["local_path"].endswith("sample.bin")


def test_upload_file_should_block_outside_work_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """上传到工作目录外应被拦截。"""

    client, _ = _build_client(monkeypatch)
    local_file = tmp_path / "sample.txt"
    local_file.write_text("demo", encoding="utf-8")

    with pytest.raises(ValueError, match="超限提示"):
        client.upload_file(local_path=local_file, remote_path="/outside/upload.txt")


def test_get_quota_should_fill_free_when_response_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """容量响应缺少 free 字段时应自动计算。"""

    client, runtime = _build_client(monkeypatch)
    runtime.userinfo_api.response = {"errno": 0, "total": 2000, "used": 350}

    payload = client.get_quota()

    assert payload["free"] == 1650


def test_get_file_version_info_should_merge_entry_and_meta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """文件版本信息应合并目录条目与 filemetas 数据。"""

    client, runtime = _build_client(monkeypatch)
    runtime.fileinfo_api.listing_by_dir["/apps/rift-audio-pipeline/work"] = {
        "errno": 0,
        "list": [
            {
                "path": "/apps/rift-audio-pipeline/work/audio.wav",
                "isdir": 0,
                "fs_id": 12345,
            }
        ],
    }
    runtime.multimedia_api.response = {
        "errno": 0,
        "list": [{"size": 1024, "md5": "abc123", "dlink": "https://example.test"}],
    }

    payload = client.get_file_version_info("work/audio.wav")

    assert payload["path"] == "/apps/rift-audio-pipeline/work/audio.wav"
    assert payload["fs_id"] == 12345
    assert payload["md5"] == "abc123"


def test_download_file_should_retry_and_write_local_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """下载失败后应自动重试并写入本地文件。"""

    client, runtime = _build_client(monkeypatch)
    runtime.fileinfo_api.listing_by_dir["/apps/rift-audio-pipeline/work"] = {
        "errno": 0,
        "list": [
            {
                "path": "/apps/rift-audio-pipeline/work/download.txt",
                "isdir": 0,
                "fs_id": 70001,
            }
        ],
    }
    runtime.multimedia_api.response = {
        "errno": 0,
        "list": [{"size": 6, "md5": "ignored", "dlink": "https://example.test/download"}],
    }
    runtime.api_client.call_api_failures = 1
    runtime.api_client.download_chunks = [b"abc", b"def"]

    local_file = tmp_path / "downloaded.txt"
    payload = client.download_file(remote_path="work/download.txt", local_path=local_file)

    assert payload["path"] == "/apps/rift-audio-pipeline/work/download.txt"
    assert local_file.read_bytes() == b"abcdef"
    assert len(runtime.api_client.call_api_calls) == 2


def test_get_path_entry_should_return_work_dir_dir_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """查询工作目录本身时应直接返回目录条目。"""

    client, runtime = _build_client(monkeypatch)

    payload = client.get_path_entry("/apps/rift-audio-pipeline")

    assert payload == {"path": "/apps/rift-audio-pipeline", "isdir": 1}
    assert runtime.fileinfo_api.calls == []


def test_delete_path_should_raise_baidu_api_error_on_errno(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """当接口返回 errno 非 0 时应抛出 BaiduPanApiError。"""

    client, runtime = _build_client(monkeypatch)
    runtime.filemanager_api.delete_response = {"errno": 2, "info": "failed"}

    with pytest.raises(BaiduPanApiError) as exc_info:
        client.delete_path("work/failed.txt")

    assert exc_info.value.errno == 2


def test_invoke_sdk_call_api_should_translate_sdk_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """下载底层 SDK 异常应转换为 BaiduPanApiError。"""

    client, runtime = _build_client(monkeypatch)
    runtime.api_client.call_api_failures = 1

    with pytest.raises(BaiduPanApiError, match="官方 SDK 下载调用失败"):
        client._invoke_sdk_call_api(
            access_token="access-token",
            remote_path="/apps/rift-audio-pipeline/work/file.txt",
        )


def test_ensure_access_token_should_refresh_when_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    """过期 token 应触发 refresh。"""

    client, _ = _build_client(monkeypatch)
    old_time = datetime.now(tz=timezone.utc) - timedelta(hours=2)
    client._oauth_token = _make_token(
        access_token="expired-token",
        expires_in=1,
        obtained_at=old_time,
    )
    monkeypatch.setattr(client, "refresh_access_token", lambda: "new-token")

    assert client._ensure_access_token() == "new-token"
