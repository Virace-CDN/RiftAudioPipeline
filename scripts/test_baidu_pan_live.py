"""百度网盘 API 真实联调脚本。"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from pathlib import Path

from rift_audio_pipeline.baidu.oauth import load_baidu_app_credentials
from rift_audio_pipeline.baidu.oauth import resolve_token_store
from rift_audio_pipeline.baidu.pan import BaiduCredentials
from rift_audio_pipeline.baidu.pan import BaiduPanClient

DEFAULT_DEV_CONFIG = Path(".dev.baidu")
DEFAULT_TOKEN_FILE = Path(".config/baidu/token.json")
DEFAULT_REMOTE_WORK_DIR = "/apps/rift-audio-pipeline"


def main() -> int:
    """执行百度网盘 API 联调流程。"""

    app_credentials = load_baidu_app_credentials(
        app_key=None,
        secret_key=None,
        dev_config_file=DEFAULT_DEV_CONFIG,
    )
    token_store = resolve_token_store(token_file=DEFAULT_TOKEN_FILE)
    oauth_token = token_store.load_token()
    client_credentials = BaiduCredentials(
        app_key=app_credentials.app_key,
        secret_key=app_credentials.secret_key,
        refresh_token=oauth_token.refresh_token,
    )
    client = BaiduPanClient(
        credentials=client_credentials,
        remote_dir=DEFAULT_REMOTE_WORK_DIR,
        token_store=token_store,
    )

    run_id = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    remote_root = f"{DEFAULT_REMOTE_WORK_DIR}/smoke_{run_id}"
    remote_src_dir = f"{remote_root}/src"
    remote_dst_dir = f"{remote_root}/dst"
    remote_origin = f"{remote_src_dir}/origin.txt"
    remote_renamed = f"{remote_src_dir}/renamed.txt"
    remote_copied = f"{remote_src_dir}/copied.txt"
    remote_moved = f"{remote_dst_dir}/moved.txt"
    local_sample = Path("output/baidu_live_sample.txt")
    local_download = Path("output/baidu_live_downloaded.txt")

    print("== 百度网盘 API 真实联调开始 ==")
    try:
        quota = client.get_quota()
        total = int(quota.get("total", 0))
        used = int(quota.get("used", 0))
        free = int(quota.get("free", max(total - used, 0)))
        print(f"[quota] total={total}, used={used}, free={free}")

        client.create_directory(DEFAULT_REMOTE_WORK_DIR)
        client.create_directory(remote_root)
        client.create_directory(remote_src_dir)
        client.create_directory(remote_dst_dir)
        print(f"[mkdir] 已创建目录：{remote_root}")

        local_sample.parent.mkdir(parents=True, exist_ok=True)
        local_sample.write_text(
            f"RiftAudioPipeline live smoke test at {run_id}\n",
            encoding="utf-8",
        )
        upload_resp = client.upload_file(local_path=local_sample, remote_path=remote_origin)
        print(f"[upload] origin -> {remote_origin}, fs_id={upload_resp.get('fs_id')}")

        rename_resp = client.rename_path(source_path=remote_origin, new_name="renamed.txt")
        print(f"[rename] -> {remote_renamed}, errno={rename_resp.get('errno', 0)}")

        copy_resp = client.copy_path(
            source_path=remote_renamed,
            destination_dir=remote_src_dir,
            new_name="copied.txt",
            ondup="overwrite",
        )
        print(f"[copy] -> {remote_copied}, errno={copy_resp.get('errno', 0)}")

        move_resp = client.move_path(
            source_path=remote_copied,
            destination_dir=remote_dst_dir,
            new_name="moved.txt",
            ondup="overwrite",
        )
        print(f"[move] -> {remote_moved}, errno={move_resp.get('errno', 0)}")

        version_info = client.get_file_version_info(remote_path=remote_moved)
        print(
            "[version] "
            f"path={version_info.get('path')}, "
            f"size={version_info.get('size')}, "
            f"md5={version_info.get('md5')}"
        )

        download_info = client.download_file(remote_path=remote_moved, local_path=local_download)
        print(
            "[download] "
            f"remote={download_info.get('path')} -> local={local_download}, "
            f"size={local_download.stat().st_size}"
        )

        src_listing = client.list_files(remote_src_dir)
        dst_listing = client.list_files(remote_dst_dir)
        print(
            f"[list] src_count={len(src_listing.get('list', []))}, dst_count={len(dst_listing.get('list', []))}"
        )

        client.delete_paths(paths=[remote_renamed, remote_moved])
        client.delete_paths(paths=[remote_src_dir, remote_dst_dir, remote_root])
        print(f"[delete] 已清理测试目录：{remote_root}")
        print("== 百度网盘 API 真实联调完成：成功 ==")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
