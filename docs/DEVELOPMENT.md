# 开发维护

## 文件职责

| 文件 | 职责 |
|---|---|
| `__init__.py` | 仅导出节点映射 |
| `nodes.py` | 唯一UI节点、文件解析、进度和音轨封装 |
| `runtime.py` | 校验模型、装配固定网络、按批编码/推理/解码 |
| `video_controls.py` | 比例计算、目标时间线、内存检查和RIFE调度 |
| `rife_arch.py` | RIFE网络实现 |
| `vendor/` | 裁剪后的上游网络依赖，修改需保留来源和许可 |
| `architecture.json` | 主模型允许的固定架构 |
| `models/manifest.json` | 文件名、大小、SHA256、用途 |
| `workflows/` | 一份界面工作流和一份API示例 |
| `tools/verify_models.py` | 只读校验本机模型 |
| `tests/` | 尺寸、帧率与工作流契约测试 |

## 执行顺序

1. 通过ComfyUI的模型目录解析文件路径，校验单文件格式和架构。
2. 读取视频尺寸、帧率、画面与声音；计算目标尺寸和帧数，检查内存预算。
3. 按批进行超分，批间保留一帧衔接，返回原始帧数的增强画面。
4. 需要升帧率时按目标时间点用RIFE生成中间画面；降帧率时按时间抽帧。
5. 用原音轨与目标帧率封装VIDEO，再交给ComfyUI保存节点编码。

不增加Topaz进程调用、网络上传、自动下载、研究目录引用或原始分片依赖。暂不以“清理”为理由改动推理数学、dtype或权重名称。

## 兼容约定

- UI可以改中文标题，但内部类型ID `Starlight26VideoEnhanceUnified` 保持稳定。
- 模型文件名可改，磁盘schema不能跟着改。要变更schema必须提供显式迁移和测试。
- 工作流的 `widgets_values` 有顺序，增删UI参数必须同步界面示例和实际浏览器导入检查。
- 只保留一个正式节点，不重新引入V1/V2/V3并行入口。
- 只读测试不得触发付费API；GPU测试使用独立服务、短素材，不中断用户队列。

## 验证

在ComfyUI的Python环境中，切到本插件目录：

```powershell
python -m unittest discover -s tests -v
python tools/verify_models.py --models-dir "你的ComfyUI/models" --with-rife
```

改变运行链路或裁剪依赖后，还要启动仅加载本插件的ComfyUI验收服务，完成以下检查：

1. `/object_info`能找到本插件且只注册一个节点；新模型出现在下拉列表。
2. 浏览器导入示例工作流；上传视频后可生成正确的API请求，全部参数顺序无错位。
3. 通过`/prompt`运行含音轨的小片，轮询`/history/{id}`直到成功，并用视频解码器检查尺寸、帧数、帧率和声音。
4. 测试保持原帧率以及升/降帧率；改动锐度映射时三档分别验收。
5. 验证源模型文件SHA256不变；取消响应、失败显存清理和旧文件不被覆盖。

本轮具体结果见 `VALIDATION.md`；历史实验见 `历史验收记录.md`。未经测试的4K长片、其他GPU或HDR不得标为已支持验证。

## Git管理

仓库地址：<https://github.com/shenyanping/ComfyUI-1renmanju>。提交前运行 `git status --short` 和 `git diff --check`，确认没有权重、凭据、个人视频和运行日志。模型通过 `MODELS.md` 中的网盘单独提供，不推送到源码仓库。

后续更新vendor时，登记新的来源快照，复核 `docs/source-manifest.json` 的逐文件校验和差异，再做同一素材、同一参数回归。不要把宿主ComfyUI的Git提交号误记成插件上游版本。
