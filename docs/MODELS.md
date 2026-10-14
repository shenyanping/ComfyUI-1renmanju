# 模型管理

## 下载

通过百度网盘分享的文件：**ComfyUI-1renmanju**。

- 链接：[打开模型网盘](https://pan.baidu.com/s/15_CEVT13DbK5Cimagh5O1A)
- 提取码：`ugf8`

此链接由项目维护者提供。模型不随Git仓库下载，插件也不会自动下载；取得文件后按下方目录放置，再运行校验工具确认文件完整。

如网盘中的主模型尚未更名，请将文件名改为 `1ren-chaofen-v1.safetensors`。文件内容及SHA256没有改变，不需要重新转换；`rife47.safetensors`保持原名。

## 目录

```text
ComfyUI/
  custom_nodes/ComfyUI-1renmanju/   # Git管理的插件源码
  models/
    starlight26/
      1ren-chaofen-v1.safetensors
    rife/
      rife47.safetensors
```

不必把模型复制到插件目录，也不需要原来的零散分片。两份模型的精确字节大小与SHA256在 `models/manifest.json` 中。

在ComfyUI的Python环境中运行：

```powershell
python tools/verify_models.py --models-dir "你的ComfyUI/models"
```

默认检查主模型；加 `--with-rife` 同时检查插帧模型。检查只读，失败返回非零退出码，不下载、不重写文件。

## 文件格式

主模型为safetensors，不是普通Stable Diffusion checkpoint。虽然是单文件，仍需本插件按架构加载。

- `format=starlight26_independent`，`schema_version=1`：这是已有的磁盘格式标识，改产品名时保持不变。
- `dit.*`：主推理网络。
- `vae_encoder.*`：编码器。
- `vae_decoders.standard.*` / `m05.*` / `m10.*`：三档解码器。
- `text.pos` / `text.neg`：固定文本特征。
- `dit_config` / `vae_config`：加载时与仓库 `architecture.json` 核对。

模型重命名不修改这些内容；新旧主文件的SHA256必须相同。不要为改显示名重新保存数GB权重。

## Git与分发

`.gitignore`排除了权重、视频、日志、缓存。Git中只记录清单、代码、示例和验证工具。模型通过上方网盘单独获取，或在机器间单独传输，并用清单核对。

本仓库未确认或授予第三方权重的再分发许可。源码许可证与模型权重是两件事，不能因为源码带Apache/MIT许可证就将权重标为相同许可。
