# 第三方来源与许可

## SeedVR2兼容网络

`vendor/`选自本机 `ComfyUI-SeedVR2_VideoUpscaler/src`，上游项目：
<https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler>。

网络文件含ByteDance SeedVR2版权标头，已保留。随附 `LICENSE-SeedVR2`（Apache-2.0）为本机源项目的许可证副本。当前保留模块不改数学实现；删减范围见 `docs/cleanup-manifest.json`，逐文件来源与SHA256见 `docs/source-manifest.json`。

## RIFE

`rife_arch.py`选自本机 `comfyui-frame-interpolation_cudafull/vfi_models/rife/rife_arch.py`。
集成项目：<https://github.com/Fannovel16/ComfyUI-Frame-Interpolation>，随附 `LICENSE-RIFE-Integration`（MIT）。原文件标注的网络来源包括：

- <https://github.com/hzwer/Practical-RIFE>
- <https://github.com/HolyWu/vs-rife>

此前本项目将warp中的设备选择改为按输入设备获取，并加中文说明，改动后的文件继续保留来源标头。本次整理不改RIFE网络数学。

## 自有集成与权重

节点、单文件装配和时间线处理属于本项目的集成代码。目前未给这些代码指定对外开源许可，不用第三方许可证替代整个仓库许可。

主权重及RIFE权重来自用户本机已有文件。重命名/转换不改变来源，也不授予额外使用或再分发许可；不将代码许可证延伸到权重。模型与源码分开管理，详见 `docs/MODELS.md`。
