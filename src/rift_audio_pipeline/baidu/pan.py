"""基于官方 openapi_client 的百度网盘 API 封装。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
import hashlib
import importlib
import io
import json
from pathlib import Path
from pathlib import PurePath
from pathlib import PurePosixPath
import posixpath
import re
from typing import Any
from typing import Callable
from typing import Iterable
from typing import Mapping
from urllib.parse import urlparse
import warnings

from rift_audio_pipeline.baidu.oauth import BaiduAppCredentials
from rift_audio_pipeline.baidu.oauth import BaiduOAuthClient
from rift_audio_pipeline.baidu.oauth import BaiduOAuthToken
from rift_audio_pipeline.baidu.oauth import LocalBaiduTokenStore
from rift_audio_pipeline.baidu.sdk import ensure_official_sdk_path
from rift_audio_pipeline.baidu.sdk import load_openapi_client_module

PCS_API_HOST = "https://d.pcs.baidu.com"
UPLOAD_BLOCK_SIZE_BYTES = 4 * 1024 * 1024
TOKEN_EXPIRY_SAFETY_SECONDS = 120
UPLOAD_PRECREATE_TIMEOUT = (30, 180)
UPLOAD_PART_TIMEOUT = (30, 180)
UPLOAD_CREATE_TIMEOUT = (30, 180)
DOWNLOAD_CONNECT_TIMEOUT = 8.0
DOWNLOAD_READ_TIMEOUT = 900.0
DOWNLOAD_MIN_READ_TIMEOUT = 15.0
DOWNLOAD_TIMEOUT_MARGIN_SECONDS = 10.0
DOWNLOAD_MIN_THROUGHPUT_BYTES_PER_SECOND = 20 * 1024
DOWNLOAD_UNKNOWN_SIZE_READ_TIMEOUT = 60.0
DOWNLOAD_METADATA_READ_TIMEOUT = 15.0
DOWNLOAD_MAX_ATTEMPTS = 2


@dataclass(frozen=True, slots=True)
class BaiduCredentials:
    """百度开放平台凭据。"""

    app_key: str | None = None
    secret_key: str | None = None
    refresh_token: str | None = None
    access_token: str | None = None


class BaiduPanApiError(RuntimeError):
    """百度网盘 API 请求异常。"""

    def __init__(
        self,
        message: str,
        errno: int | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        """初始化异常对象。

        Args:
            message: 异常信息。
            errno: 接口返回错误码。
            payload: 原始响应数据。
        """

        super().__init__(message)
        self.errno = errno
        self.payload = payload


class BaiduPanScopeWarning(UserWarning):
    """百度网盘工作目录边界告警。"""


class BaiduPanClient:
    """百度网盘客户端（官方 SDK 适配层）。"""

    def __init__(
        self,
        credentials: BaiduCredentials,
        remote_dir: str,
        token_store: LocalBaiduTokenStore | None = None,
        allow_token_refresh: bool = True,
        download_connect_timeout: float = DOWNLOAD_CONNECT_TIMEOUT,
        download_read_timeout: float = DOWNLOAD_READ_TIMEOUT,
        download_max_attempts: int = DOWNLOAD_MAX_ATTEMPTS,
        download_log: Callable[[str], None] | None = None,
    ) -> None:
        """初始化客户端。

        Args:
            credentials: 百度开放平台凭据。
            remote_dir: 网盘工作目录。
            token_store: 本地 token 存储（可选）。
            allow_token_refresh: 是否允许在 access token 失效时自动刷新。
            download_connect_timeout: 下载阶段连接超时秒数。
            download_read_timeout: 下载阶段读取超时上限秒数。
            download_max_attempts: 下载阶段最大尝试次数。
            download_log: 下载阶段高层日志回调。

        Raises:
            ValueError: 缺少执行当前模式所需的 token。
        """

        self._credentials = credentials
        self._remote_dir = _normalize_remote_path(remote_dir)
        self._token_store = token_store
        self._allow_token_refresh = allow_token_refresh
        self._download_connect_timeout = float(download_connect_timeout)
        self._download_read_timeout = float(download_read_timeout)
        self._download_max_attempts = int(download_max_attempts)
        self._download_log = download_log
        self._oauth_token: BaiduOAuthToken | None = None
        self._access_token = credentials.access_token.strip() if credentials.access_token else None

        if self._download_connect_timeout <= 0:
            raise ValueError("初始化 BaiduPanClient 失败：download_connect_timeout 必须大于 0。")
        if self._download_read_timeout <= 0:
            raise ValueError("初始化 BaiduPanClient 失败：download_read_timeout 必须大于 0。")
        if self._download_max_attempts <= 0:
            raise ValueError("初始化 BaiduPanClient 失败：download_max_attempts 必须大于 0。")

        self._refresh_token = credentials.refresh_token.strip() if credentials.refresh_token else ""
        if token_store is not None and self._allow_token_refresh:
            try:
                local_token = token_store.load_token()
                self._oauth_token = local_token
                if local_token.refresh_token:
                    self._refresh_token = local_token.refresh_token
            except FileNotFoundError:
                self._oauth_token = None

        if not self._allow_token_refresh and not self._access_token:
            raise ValueError("初始化 BaiduPanClient 失败：access token 为空。")
        if self._allow_token_refresh and not self._refresh_token:
            raise ValueError("初始化 BaiduPanClient 失败：refresh token 为空。")

        ensure_official_sdk_path()
        self._openapi_client = load_openapi_client_module()
        configuration = self._openapi_client.Configuration()
        configuration.retries = False
        self._api_client = self._openapi_client.ApiClient(configuration=configuration)

        fileinfo_api_module = importlib.import_module("openapi_client.api.fileinfo_api")
        filemanager_api_module = importlib.import_module("openapi_client.api.filemanager_api")
        fileupload_api_module = importlib.import_module("openapi_client.api.fileupload_api")
        multimedia_api_module = importlib.import_module("openapi_client.api.multimediafile_api")
        userinfo_api_module = importlib.import_module("openapi_client.api.userinfo_api")
        exception_module = importlib.import_module("openapi_client.exceptions")

        self._api_exception_cls = exception_module.ApiException
        self._fileinfo_api = fileinfo_api_module.FileinfoApi(self._api_client)
        self._filemanager_api = filemanager_api_module.FilemanagerApi(self._api_client)
        self._fileupload_api = fileupload_api_module.FileuploadApi(self._api_client)
        self._multimedia_api = multimedia_api_module.MultimediafileApi(self._api_client)
        self._userinfo_api = userinfo_api_module.UserinfoApi(self._api_client)

    @property
    def remote_dir(self) -> str:
        """返回默认网盘工作目录。"""

        return self._remote_dir

    @property
    def current_refresh_token(self) -> str:
        """返回当前 refresh token。"""

        return self._refresh_token

    def close(self) -> None:
        """关闭内部连接池。"""

        self._api_client.close()

    def refresh_access_token(self) -> str:
        """刷新 access token 并返回最新值。"""

        if not self._allow_token_refresh:
            raise BaiduPanApiError("当前执行上下文已禁用 refresh token 刷新。")
        app_credentials = BaiduAppCredentials(
            app_key=str(self._credentials.app_key),
            secret_key=str(self._credentials.secret_key),
        )
        with BaiduOAuthClient(timeout=30.0) as oauth_client:
            token = oauth_client.refresh_access_token(
                refresh_token=self._refresh_token,
                credentials=app_credentials,
            )

        self._oauth_token = token
        self._access_token = token.access_token
        self._refresh_token = token.refresh_token
        if self._token_store is not None:
            self._token_store.save_token(token=token)
        return token.access_token

    def get_quota(self) -> dict[str, Any]:
        """获取网盘容量信息。"""

        access_token = self._ensure_access_token()
        payload = self._invoke_sdk(
            lambda: self._userinfo_api.apiquota(access_token, checkexpire=1, checkfree=1),
            operation="apiquota",
        )
        total = _as_int(payload.get("total")) or 0
        used = _as_int(payload.get("used")) or 0
        payload.setdefault("free", max(total - used, 0))
        return payload

    def list_files(self, dir_path: str, limit: int = 1000, start: int = 0) -> dict[str, Any]:
        """列出目录文件。"""

        access_token = self._ensure_access_token()
        normalized_dir = self._resolve_workdir_path(
            dir_path,
            operation="xpanfilelist",
            path_role="dir",
        )
        return self._invoke_sdk(
            lambda: self._fileinfo_api.xpanfilelist(
                access_token,
                dir=normalized_dir,
                folder="0",
                start=str(start),
                limit=limit,
                order="name",
                desc=0,
                web="1",
                showempty=1,
                _request_timeout=self._build_metadata_timeout(),
            ),
            operation="xpanfilelist",
        )

    def create_directory(self, dir_path: str) -> dict[str, Any]:
        """创建目录。"""

        access_token = self._ensure_access_token()
        normalized_dir = self._resolve_workdir_path(
            dir_path,
            operation="xpanfilecreate(isdir=1)",
            path_role="dir",
        )
        return self._invoke_sdk(
            lambda: self._fileupload_api.xpanfilecreate(
                access_token,
                normalized_dir,
                1,
                0,
                "",
                "[]",
                rtype=3,
            ),
            operation="xpanfilecreate(isdir=1)",
        )

    def ensure_directory(self, dir_path: str) -> str:
        """确保目录存在，不存在时递归创建。"""

        normalized_dir = self._resolve_workdir_path(
            dir_path,
            operation="ensure_directory",
            path_role="dir",
        )
        if normalized_dir == "/":
            return normalized_dir
        if normalized_dir == self._remote_dir:
            try:
                self.list_files("")
            except BaiduPanApiError as error:
                if error.errno != -9:
                    raise
                self.create_directory(normalized_dir)
            return normalized_dir
        try:
            entry = self.get_path_entry(normalized_dir)
        except FileNotFoundError:
            if normalized_dir != self._remote_dir:
                parent_dir = str(PurePosixPath(normalized_dir).parent)
                if parent_dir and parent_dir != normalized_dir:
                    self.ensure_directory(parent_dir)
            self.create_directory(normalized_dir)
            return normalized_dir
        if int(entry.get("isdir", 0)) != 1:
            raise NotADirectoryError(f"网盘路径已存在但不是目录：{normalized_dir}")
        return normalized_dir

    def rename_path(
        self, source_path: str, new_name: str, ondup: str = "newcopy"
    ) -> dict[str, Any]:
        """重命名文件或目录。"""

        payload = [
            {
                "path": self._resolve_workdir_path(
                    source_path,
                    operation="filemanagerrename",
                    path_role="source_path",
                ),
                "newname": new_name,
            }
        ]
        return self._filemanager_operation(opera="rename", filelist=payload, ondup=ondup)

    def copy_path(
        self,
        source_path: str,
        destination_dir: str,
        new_name: str | None = None,
        ondup: str = "newcopy",
    ) -> dict[str, Any]:
        """复制文件或目录。"""

        file_payload: dict[str, Any] = {
            "path": self._resolve_workdir_path(
                source_path,
                operation="filemanagercopy",
                path_role="source_path",
            ),
            "dest": self._resolve_workdir_path(
                destination_dir,
                operation="filemanagercopy",
                path_role="destination_dir",
            ),
        }
        if new_name is not None:
            file_payload["newname"] = new_name
        return self._filemanager_operation(opera="copy", filelist=[file_payload], ondup=ondup)

    def move_path(
        self,
        source_path: str,
        destination_dir: str,
        new_name: str | None = None,
        ondup: str = "newcopy",
    ) -> dict[str, Any]:
        """移动文件或目录。"""

        file_payload: dict[str, Any] = {
            "path": self._resolve_workdir_path(
                source_path,
                operation="filemanagermove",
                path_role="source_path",
            ),
            "dest": self._resolve_workdir_path(
                destination_dir,
                operation="filemanagermove",
                path_role="destination_dir",
                allow_outside=True,
            ),
        }
        if new_name is not None:
            file_payload["newname"] = new_name
        return self._filemanager_operation(opera="move", filelist=[file_payload], ondup=ondup)

    def delete_path(self, target_path: str) -> dict[str, Any]:
        """删除单个路径。"""

        return self.delete_paths(paths=[target_path])

    def delete_paths(self, paths: Iterable[str]) -> dict[str, Any]:
        """批量删除路径。"""

        filelist = [
            {
                "path": self._resolve_workdir_path(
                    path,
                    operation="filemanagerdelete",
                    path_role="path",
                )
            }
            for path in paths
        ]
        return self._filemanager_operation(opera="delete", filelist=filelist, ondup=None)

    def upload_file(
        self,
        local_path: Path,
        remote_path: str,
        rtype: int = 3,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """上传单个文件（precreate -> superfile2 -> create）。"""

        if not local_path.exists():
            raise FileNotFoundError(f"上传失败：本地文件不存在：{local_path}")
        if not local_path.is_file():
            raise ValueError(f"上传失败：本地路径不是文件：{local_path}")

        access_token = self._ensure_access_token()
        normalized_remote_path = self._resolve_workdir_path(
            remote_path,
            operation="xpanfilecreate(isdir=0)",
            path_role="remote_path",
        )
        self.ensure_directory(str(PurePosixPath(normalized_remote_path).parent))
        file_size = local_path.stat().st_size
        block_md5s = _calculate_block_md5s(local_path)
        block_list_json = json.dumps(block_md5s, ensure_ascii=False)

        _emit_upload_progress(
            progress_callback,
            phase="precreate",
            status="started",
            local_path=local_path,
            remote_path=normalized_remote_path,
            file_size=file_size,
            part_count=len(block_md5s),
        )
        precreate_payload = self._invoke_sdk(
            lambda: self._fileupload_api.xpanfileprecreate(
                access_token,
                normalized_remote_path,
                0,
                file_size,
                1,
                block_list_json,
                rtype=rtype,
                _request_timeout=UPLOAD_PRECREATE_TIMEOUT,
            ),
            operation="xpanfileprecreate",
        )
        upload_id = _as_non_empty_str(precreate_payload.get("uploadid"))
        if upload_id is None:
            raise BaiduPanApiError(
                message=f"预上传响应缺少 uploadid，path={normalized_remote_path}",
                payload=precreate_payload,
            )
        _emit_upload_progress(
            progress_callback,
            phase="precreate",
            status="completed",
            local_path=local_path,
            remote_path=normalized_remote_path,
            file_size=file_size,
            part_count=len(block_md5s),
            upload_id=upload_id,
        )

        with local_path.open("rb") as file_obj:
            for part_index, expected_md5 in enumerate(block_md5s):
                chunk = file_obj.read(UPLOAD_BLOCK_SIZE_BYTES)
                if not chunk:
                    raise BaiduPanApiError(
                        message=f"分片读取失败，part_index={part_index}, file={local_path}"
                    )
                chunk_file = io.BytesIO(chunk)
                chunk_file.name = f"{local_path.name}.part{part_index}"
                _emit_upload_progress(
                    progress_callback,
                    phase="part_upload",
                    status="started",
                    local_path=local_path,
                    remote_path=normalized_remote_path,
                    file_size=file_size,
                    part_count=len(block_md5s),
                    part_index=part_index,
                    upload_id=upload_id,
                    chunk_size=len(chunk),
                )
                part_payload = self._invoke_sdk(
                    lambda chunk_file=chunk_file, part_index=part_index: (
                        self._fileupload_api.pcssuperfile2(
                            access_token,
                            str(part_index),
                            normalized_remote_path,
                            upload_id,
                            "tmpfile",
                            file=chunk_file,
                            _request_timeout=UPLOAD_PART_TIMEOUT,
                        )
                    ),
                    operation=f"pcssuperfile2(part={part_index})",
                )
                remote_md5 = _as_non_empty_str(part_payload.get("md5"))
                if remote_md5 is not None and remote_md5.lower() != expected_md5.lower():
                    raise BaiduPanApiError(
                        message=(
                            "分片上传 MD5 不一致，"
                            f"part_index={part_index}, expected={expected_md5}, actual={remote_md5}"
                        ),
                        payload=part_payload,
                    )
                _emit_upload_progress(
                    progress_callback,
                    phase="part_upload",
                    status="completed",
                    local_path=local_path,
                    remote_path=normalized_remote_path,
                    file_size=file_size,
                    part_count=len(block_md5s),
                    part_index=part_index,
                    upload_id=upload_id,
                    chunk_size=len(chunk),
                )

        _emit_upload_progress(
            progress_callback,
            phase="create",
            status="started",
            local_path=local_path,
            remote_path=normalized_remote_path,
            file_size=file_size,
            part_count=len(block_md5s),
            upload_id=upload_id,
        )
        payload = self._invoke_sdk(
            lambda: self._fileupload_api.xpanfilecreate(
                access_token,
                normalized_remote_path,
                0,
                file_size,
                upload_id,
                block_list_json,
                rtype=rtype,
                _request_timeout=UPLOAD_CREATE_TIMEOUT,
            ),
            operation="xpanfilecreate(isdir=0)",
        )
        _emit_upload_progress(
            progress_callback,
            phase="create",
            status="completed",
            local_path=local_path,
            remote_path=normalized_remote_path,
            file_size=file_size,
            part_count=len(block_md5s),
            upload_id=upload_id,
        )
        return payload

    def get_file_version_info(self, remote_path: str) -> dict[str, Any]:
        """获取文件版本信息（含 dlink、md5、mtime 等）。"""

        entry = self.get_path_entry(remote_path=remote_path)
        if _as_int(entry.get("isdir")) == 1:
            raise IsADirectoryError(f"路径是目录，不能获取文件版本信息：{remote_path}")

        fs_id = _as_int(entry.get("fs_id"))
        if fs_id is None:
            raise BaiduPanApiError(
                message=f"文件条目缺少 fs_id，path={remote_path}",
                payload=entry,
            )

        access_token = self._ensure_access_token()
        metas_payload = self._invoke_sdk(
            lambda: self._multimedia_api.xpanmultimediafilemetas(
                access_token,
                json.dumps([fs_id], ensure_ascii=False),
                thumb="0",
                extra="1",
                dlink="1",
                needmedia=1,
                _request_timeout=self._build_metadata_timeout(),
            ),
            operation="xpanmultimediafilemetas",
        )
        meta_list = metas_payload.get("list")
        if not isinstance(meta_list, list) or not meta_list:
            raise BaiduPanApiError(
                message=f"filemetas 响应缺少 list，path={remote_path}",
                payload=metas_payload,
            )
        merged: dict[str, Any] = {}
        merged.update(entry)
        if isinstance(meta_list[0], dict):
            merged.update(meta_list[0])
        return merged

    def download_file(self, remote_path: str, local_path: Path) -> dict[str, Any]:
        """下载单个文件到本地。"""

        normalized_path = self._resolve_workdir_path(
            remote_path,
            operation="download",
            path_role="remote_path",
        )
        self.ensure_directory(str(PurePosixPath(normalized_path).parent))
        self._emit_download_log(
            "prepare_metadata "
            f"path={normalized_path} "
            f"connect_timeout={self._download_connect_timeout}s "
            f"read_timeout={self._download_read_timeout}s "
            f"max_attempts={self._download_max_attempts}"
        )
        version_info = self.get_file_version_info(remote_path=normalized_path)
        file_size = _as_int(version_info.get("size"))
        read_timeout = self._resolve_download_read_timeout(file_size=file_size)
        self._emit_download_log(
            "metadata_ready "
            f"path={normalized_path} "
            f"size={file_size if file_size is not None else 'unknown'} "
            f"read_timeout={read_timeout}s"
        )
        access_token = self._ensure_access_token()
        local_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = local_path.with_suffix(f"{local_path.suffix}.part")

        max_attempts = self._download_max_attempts
        for attempt in range(1, max_attempts + 1):
            raw_response = None
            try:
                self._emit_download_log(f"attempt_start path={normalized_path} attempt={attempt}/{max_attempts}")
                raw_response = self._invoke_sdk_call_api(
                    access_token=access_token,
                    remote_path=normalized_path,
                    read_timeout=read_timeout,
                )
                with temp_path.open("wb") as file_obj:
                    while True:
                        chunk = raw_response.read(UPLOAD_BLOCK_SIZE_BYTES)
                        if not chunk:
                            break
                        file_obj.write(chunk)
                temp_path.replace(local_path)
                self._emit_download_log(f"download_success path={normalized_path} attempt={attempt}/{max_attempts}")
                break
            except Exception as error:
                if temp_path.exists():
                    temp_path.unlink(missing_ok=True)
                self._emit_download_log(
                    "attempt_failed "
                    f"path={normalized_path} "
                    f"attempt={attempt}/{max_attempts} "
                    f"error={_sanitize_sensitive_text(f'{type(error).__name__}: {error}')}"
                )
                if attempt == max_attempts:
                    raise BaiduPanApiError(
                        message=(
                            "文件下载失败：官方 SDK 下载接口重试后仍失败，"
                            f"path={normalized_path}, attempts={max_attempts}"
                        )
                    ) from error
            finally:
                if raw_response is not None:
                    raw_response.release_conn()
        return version_info

    def get_path_entry(self, remote_path: str) -> dict[str, Any]:
        """查询单一路径条目。"""

        normalized_path = self._resolve_workdir_path(
            remote_path,
            operation="get_path_entry",
            path_role="remote_path",
        )
        if normalized_path == "/":
            return {"path": "/", "isdir": 1}
        if normalized_path == self._remote_dir:
            return {"path": self._remote_dir, "isdir": 1}

        path_obj = PurePosixPath(normalized_path)
        parent_dir = str(path_obj.parent) if str(path_obj.parent) else "/"
        try:
            listing = self.list_files(dir_path=parent_dir)
        except BaiduPanApiError as error:
            if error.errno == -9:
                raise FileNotFoundError(f"网盘路径不存在：{normalized_path}") from error
            raise
        for entry in listing.get("list", []):
            if isinstance(entry, dict) and entry.get("path") == normalized_path:
                return entry
        raise FileNotFoundError(f"网盘路径不存在：{normalized_path}")

    def _filemanager_operation(
        self,
        opera: str,
        filelist: list[dict[str, Any]],
        ondup: str | None,
    ) -> dict[str, Any]:
        """执行 filemanager 操作。"""

        access_token = self._ensure_access_token()
        filelist_json = json.dumps(filelist, ensure_ascii=False, separators=(",", ":"))

        if opera == "copy":
            return self._invoke_sdk(
                lambda: self._filemanager_api.filemanagercopy(
                    access_token,
                    0,
                    filelist_json,
                    ondup=ondup or "newcopy",
                ),
                operation="filemanagercopy",
            )
        if opera == "move":
            return self._invoke_sdk(
                lambda: self._filemanager_api.filemanagermove(
                    access_token,
                    0,
                    filelist_json,
                    ondup=ondup or "newcopy",
                ),
                operation="filemanagermove",
            )
        if opera == "rename":
            return self._invoke_sdk(
                lambda: self._filemanager_api.filemanagerrename(
                    access_token,
                    0,
                    filelist_json,
                    ondup=ondup or "newcopy",
                ),
                operation="filemanagerrename",
            )
        if opera == "delete":
            return self._invoke_sdk(
                lambda: self._filemanager_api.filemanagerdelete(
                    access_token,
                    0,
                    filelist_json,
                ),
                operation="filemanagerdelete",
            )
        raise ValueError(f"不支持的 filemanager 操作：{opera}")

    def _invoke_sdk(self, action: Callable[[], Any], operation: str) -> dict[str, Any]:
        """执行官方 SDK 调用并统一转换响应。"""

        try:
            raw_payload = action()
        except self._api_exception_cls as error:  # type: ignore[misc]
            raise BaiduPanApiError(
                message=f"百度 SDK 调用失败：{operation}，{_extract_api_exception_message(error)}"
            ) from None
        payload = _payload_to_dict(raw_payload)
        errno = _as_int(payload.get("errno"))
        if errno not in (None, 0):
            raise BaiduPanApiError(
                message=f"百度接口返回错误：operation={operation}, errno={errno}",
                errno=errno,
                payload=payload,
            )
        return payload

    def _invoke_sdk_call_api(self, access_token: str, remote_path: str, read_timeout: float) -> Any:
        """通过官方 ApiClient.call_api 下载文件流。"""

        try:
            return self._api_client.call_api(
                resource_path="/rest/2.0/pcs/file?method=download",
                method="GET",
                query_params=[
                    ("app_id", "250528"),
                    ("path", remote_path),
                    ("access_token", access_token),
                ],
                _return_http_data_only=True,
                _preload_content=False,
                _request_timeout=(self._download_connect_timeout, read_timeout),
                _host=PCS_API_HOST,
                _check_type=False,
            )
        except self._api_exception_cls as error:  # type: ignore[misc]
            redirect_location = _extract_redirect_location(error)
            if redirect_location:
                parsed_location = urlparse(redirect_location)
                self._emit_download_log(
                    "redirect_follow "
                    f"path={remote_path} "
                    f"host={parsed_location.netloc or 'unknown'}"
                )
                return self._download_from_redirect_location(
                    redirect_location=redirect_location,
                    read_timeout=read_timeout,
                )
            raise BaiduPanApiError(
                message=f"官方 SDK 下载调用失败：{_extract_api_exception_message(error)}"
            ) from None

    def _emit_download_log(self, message: str) -> None:
        """输出下载阶段高层日志。"""

        if self._download_log is None:
            return
        self._download_log(f"[baidu.download] {message}")

    def _download_from_redirect_location(self, *, redirect_location: str, read_timeout: float) -> Any:
        """跟随百度下载接口返回的 302 Location 并继续读取文件流。"""

        try:
            return self._api_client.rest_client.request(
                "GET",
                redirect_location,
                headers={"User-Agent": "pan.baidu.com"},
                _preload_content=False,
                _request_timeout=(self._download_connect_timeout, read_timeout),
            )
        except self._api_exception_cls as error:  # type: ignore[misc]
            raise BaiduPanApiError(
                message=f"302 跳转下载失败：{_extract_api_exception_message(error)}"
            ) from None

    def _resolve_download_read_timeout(self, *, file_size: int | None) -> float:
        """按文件大小动态计算下载读取超时。"""

        if file_size is None:
            return min(self._download_read_timeout, DOWNLOAD_UNKNOWN_SIZE_READ_TIMEOUT)
        estimated_transfer_seconds = (
            float(file_size) / float(DOWNLOAD_MIN_THROUGHPUT_BYTES_PER_SECOND)
        ) + DOWNLOAD_TIMEOUT_MARGIN_SECONDS
        return min(
            self._download_read_timeout,
            max(DOWNLOAD_MIN_READ_TIMEOUT, estimated_transfer_seconds),
        )

    def _build_metadata_timeout(self) -> tuple[float, float]:
        """为列表和 filemetas 阶段构建较短超时。"""

        return (
            self._download_connect_timeout,
            min(self._download_read_timeout, DOWNLOAD_METADATA_READ_TIMEOUT),
        )

    def _ensure_access_token(self) -> str:
        """确保存在可用 access token。"""

        if self._access_token:
            return self._access_token
        if self._oauth_token is not None and _token_not_expired(self._oauth_token):
            return self._oauth_token.access_token
        if not self._allow_token_refresh:
            raise BaiduPanApiError("当前执行上下文缺少可用 access token，且禁止自动刷新。")
        return self.refresh_access_token()

    def _resolve_workdir_path(
        self,
        raw_path: str,
        operation: str,
        path_role: str,
        allow_outside: bool = False,
    ) -> str:
        """解析并校验网盘路径是否在工作目录范围内。

        Args:
            raw_path: 用户输入的路径。
            operation: 当前操作名。
            path_role: 路径语义（如 source_path、destination_dir）。
            allow_outside: 是否允许越界路径（允许时仅告警）。

        Returns:
            标准化后的绝对网盘路径。

        Raises:
            ValueError: 路径越界且不允许越界时抛出。
        """

        normalized_path = self._resolve_remote_path(raw_path)
        if self._is_under_remote_dir(normalized_path):
            return normalized_path

        message = (
            "超限提示：检测到非工作目录操作，"
            f"operation={operation}, role={path_role}, path={normalized_path}, "
            f"work_dir={self._remote_dir}。"
            "请先在工作目录内处理，最终落地目录请通过 move_path 单独搬运。"
        )
        if allow_outside:
            warnings.warn(message, category=BaiduPanScopeWarning, stacklevel=3)
            return normalized_path
        raise ValueError(message)

    def _resolve_remote_path(self, raw_path: str) -> str:
        """将原始路径解析为绝对网盘路径。"""

        stripped = raw_path.strip()
        if not stripped:
            return self._remote_dir
        if stripped.startswith("/"):
            return _normalize_remote_path(stripped)
        if self._remote_dir == "/":
            return _normalize_remote_path(f"/{stripped}")
        return _normalize_remote_path(f"{self._remote_dir}/{stripped}")

    def _is_under_remote_dir(self, path: str) -> bool:
        """判断路径是否落在工作目录内。"""

        if self._remote_dir == "/":
            return True
        work_dir_obj = PurePosixPath(self._remote_dir)
        path_obj = PurePosixPath(path)
        return path_obj == work_dir_obj or work_dir_obj in path_obj.parents


def _payload_to_dict(payload: Any) -> dict[str, Any]:
    """将 SDK 响应统一转换为字典。"""

    if isinstance(payload, dict):
        return payload
    to_dict = getattr(payload, "to_dict", None)
    if callable(to_dict):
        converted = to_dict()
        if isinstance(converted, dict):
            return converted

    attribute_map = getattr(payload, "attribute_map", None)
    if isinstance(attribute_map, dict):
        result: dict[str, Any] = {}
        for field_name in attribute_map:
            result[field_name] = getattr(payload, field_name, None)
        return result

    if isinstance(payload, Mapping):
        return dict(payload)
    raise BaiduPanApiError(message=f"无法解析 SDK 响应类型：{type(payload)!r}")


def _extract_api_exception_message(error: Exception) -> str:
    """提取官方 SDK 异常可读信息。"""

    reason = _sanitize_sensitive_text(str(getattr(error, "reason", None)))
    body = _sanitize_sensitive_text(str(getattr(error, "body", None)))
    status = getattr(error, "status", None)
    return f"status={status}, reason={reason}, body={body}"


def _extract_redirect_location(error: Exception) -> str | None:
    """从 SDK 异常头部中提取 302 Location。"""

    if getattr(error, "status", None) != 302:
        return None
    headers = getattr(error, "headers", None)
    if headers is None:
        return None
    if hasattr(headers, "get"):
        location = headers.get("Location")
        if isinstance(location, str) and location.strip():
            return location.strip()
    if isinstance(headers, Mapping):
        location = headers.get("Location")
        if isinstance(location, str) and location.strip():
            return location.strip()
    return None


def _sanitize_sensitive_text(text: str) -> str:
    """脱敏 access token / refresh token / secret 文本。"""

    sanitized = text
    patterns = (
        (r"(?i)(access_token=)([^&\s)]+)", r"\1<redacted>"),
        (r"(?i)(refresh_token=)([^&\s)]+)", r"\1<redacted>"),
        (r'(?i)("access_token"\s*:\s*")([^"]+)(")', r"\1<redacted>\3"),
        (r'(?i)("refresh_token"\s*:\s*")([^"]+)(")', r"\1<redacted>\3"),
        (r'(?i)("client_secret"\s*:\s*")([^"]+)(")', r"\1<redacted>\3"),
    )
    for pattern, replacement in patterns:
        sanitized = re.sub(pattern, replacement, sanitized)
    return sanitized


def _normalize_remote_path(path: str) -> str:
    """规范化网盘路径。"""

    stripped = path.strip()
    if not stripped:
        return "/"
    if not stripped.startswith("/"):
        stripped = f"/{stripped}"
    normalized = posixpath.normpath(stripped)
    if normalized == ".":
        return "/"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized


def _calculate_block_md5s(local_path: Path) -> list[str]:
    """计算文件分片 MD5 列表。"""

    block_md5s: list[str] = []
    with local_path.open("rb") as file_obj:
        while True:
            chunk = file_obj.read(UPLOAD_BLOCK_SIZE_BYTES)
            if not chunk:
                break
            block_md5s.append(hashlib.md5(chunk).hexdigest())
    if not block_md5s:
        block_md5s.append(hashlib.md5(b"").hexdigest())
    return block_md5s


def _emit_upload_progress(
    progress_callback: Callable[[dict[str, Any]], None] | None,
    **payload: Any,
) -> None:
    """安全触发上传阶段进度回调。"""

    if progress_callback is None:
        return
    progress_callback(_normalize_progress_payload(payload))


def _normalize_progress_payload(value: Any) -> Any:
    """把进度事件中的 Path 等对象转成 JSON 友好值。"""

    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _normalize_progress_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_progress_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_progress_payload(item) for item in value]
    return value


def _token_not_expired(token: BaiduOAuthToken) -> bool:
    """判断 token 在安全窗口内是否仍有效。"""

    expires_at = datetime.fromisoformat(token.expires_at.replace("Z", "+00:00"))
    now = datetime.now(tz=timezone.utc)
    return expires_at.timestamp() - now.timestamp() > TOKEN_EXPIRY_SAFETY_SECONDS


def _as_int(value: object) -> int | None:
    """将对象安全转换为整数。"""

    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            return None
    return None


def _as_non_empty_str(value: object) -> str | None:
    """将对象安全转换为非空字符串。"""

    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None
