# 项目由来

## 目标和演进

用户希望在本地ComfyUI中完成视频增强，将模型装配和推理流程集成为可直接使用的节点。

2026-10-14，本机实验先研究了原有模型的结构及读取结果，并通过REA辅助分析、结构与张量核对，尝试独立加载。确认可用路径后，将参数装配进本地SeedVR2兼容网络实现，运行编码、单步推理、解码流程。随后将主网络、编码器、三套解码器与文本特征无损封装成单个safetensors文件，再接入ComfyUI。

后续增加了按短边保持比例、三档解码器锐度、独立RIFE插帧、具体目标帧率及音轨保留，最终将所有设置合并成一个节点。本次整理正式命名为 `ComfyUI-1renmanju`，主权重在项目内命名为 `1ren-chaofen-v1`。

这里的名称用于文件与产品管理，不代表自行训练了原模型或改变原模型权利。封装不是量化、压缩或训练，改名不改变模型内容。

## 代码来源

| 部分 | 来源和职责 |
|---|---|
| `nodes.py` / `runtime.py` / `video_controls.py` | 本项目集成代码：ComfyUI参数、单文件装配、尺寸和时间线、任务中断、音轨与内存检查 |
| `vendor/` | 从本机 `ComfyUI-SeedVR2_VideoUpscaler/src` 快照裁剪，网络实现含ByteDance版权标头；上游项目：<https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler> |
| `rife_arch.py` | 从本机 `comfyui-frame-interpolation_cudafull/vfi_models/rife/rife_arch.py` 复制；集成项目：<https://github.com/Fannovel16/ComfyUI-Frame-Interpolation>；原文件还标注Practical-RIFE和vs-rife来源 |
| ComfyUI节点与视频封装 | 依赖宿主的 `VIDEO`、`LoadVideo`、`SaveVideo` 和视频组件接口 |
| REA | 前期研究工具：<https://github.com/morluto/rea>；不是本插件运行依赖，未打包进仓库 |

上述上游插件在本机不是独立Git检出，不能把ComfyUI父仓库的提交号当成上游插件版本。本次使用逐文件SHA256登记来源快照，见 `source-manifest.json`。第三方源码保留原许可证和版权标头。

`vendor/`只保留从当前运行入口可达的47个Python模块，移除了未使用的7B网络、上游节点、下载器、通用模型注册/加载及GGUF加载实现。保留文件不做大范围数学重写，避免清理代码时改变效果。

## 模型来源与验证

主权重来自用户本机已有模型的独立封装结果，不是本仓库下载或训练得到的。封装含1175个张量，前期逐张量名称、形状、精度和内容校验通过，单文件与分片方案5帧测试输出一致。

RIFE权重由本机已有 `rife47.pth` 用 `weights_only=True` 安全读取并转换成safetensors，保留参数精度。

历史实验曾完成720p短片、具体帧率转换和单帧4K检查，并和用户提供的对照样片做过视觉比较；这些证据不构成全素材、全参数、长片或其他实现等价性保证。

运行只需要本插件、配套单文件权重和ComfyUI环境；无需REA、研究目录、外部处理引擎或原分片。研究的原始过程与工具没有加入产品仓库，防止实验路径与正常运行混杂。
