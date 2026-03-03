"""兼容旧入口文件。"""

from rift_audio_pipeline.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
