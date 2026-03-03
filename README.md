# RiftAudioPipeline

《英雄联盟》语音资源自动化流水线项目，目标是实现版本检测、资源差异处理、语音解包、打包与百度网盘上传的端到端自动化。

## 当前阶段

- 已完成项目目录骨架初始化。
- 已将百度官方 SDK 归档到 `third_party/baidu_sdk/`。
- 已建立百度 SDK 适配层入口：`src/rift_audio_pipeline/baidu_pan.py`。

## 启动命令

```bash
python -m rift_audio_pipeline --output-path ./output
```
