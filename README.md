# ComfyUI-1renmanju

1人漫剧的本地 ComfyUI 视频增强插件。一个节点完成模型选择、按比例调整分辨率、锐度设置和目标帧率转换，保留声音及正常播放速度。

当前模型名：**`1ren-topaz-starlight-2.6`**。这是现有星光2.6独立实验方案的项目内名称，不是重新训练的模型，也不是 Topaz 官方发布的插件。运行不调用 Topaz 程序，不读取原来的零散模型文件。

## 安装

1. 将本仓库放到 `ComfyUI/custom_nodes/ComfyUI-1renmanju`。
2. 使用 **ComfyUI 自己的 Python** 安装依赖：`python -m pip install -r requirements.txt`。不要因此替换 ComfyUI 已有的 CUDA/PyTorch。
3. 按下表放好模型。仓库不包含权重，也不自动下载。
4. 完整重启 ComfyUI，在节点菜单的「1人漫剧 / 视频增强」中找到节点。

也可以在 `ComfyUI/custom_nodes` 目录中执行：

```bash
git clone https://github.com/shenyanping/ComfyUI-1renmanju.git
```

**模型下载（百度网盘）**：[ComfyUI-1renmanju](https://pan.baidu.com/s/15_CEVT13DbK5Cimagh5O1A)，提取码：`ugf8`。下载后按下表放置文件。

| 文件 | 放置位置（相对 ComfyUI） | 用途 |
|---|---|---|
| `1ren-topaz-starlight-2.6.safetensors` | `models/starlight26/` | 必需，约7.89 GB |
| `rife47.safetensors` | `models/rife/` | 升帧率时需要，约21.3 MB |

完整大小、SHA256及来源见 [模型清单](models/manifest.json) 和 [模型管理说明](docs/MODELS.md)。保持原帧率或降帧率不需要RIFE权重。

当前仅验收支持 BF16 的 NVIDIA 显卡，本机为 RTX 3090 24GB；软件版本见 [验收环境](docs/environment.json)。不代表其他显卡和长片4K已经测试。

代码不限定Windows，Linux也可按上述目录安装，但尚未完成Linux实机验收；需要支持BF16的NVIDIA显卡和匹配的CUDA版PyTorch环境。

## 使用

拖入 [示例工作流](workflows/1renmanju-星光2.6.json)，上传自己的视频，设置中间节点，点击运行。流程只有「加载视频 → 视频增强 → 保存视频」，另接一个处理信息显示框。

| 参数 | 怎么用 |
|---|---|
| 模型文件 | 选择 `1ren-topaz-starlight-2.6.safetensors` |
| 输出尺寸 | 720p/1080p/1440p/4K均按短边定义，自动保持横竖比例；也支持原尺寸、2倍、自定义 |
| 自定义短边 | 仅「输出尺寸=自定义短边」生效，例如720；宽高会取偶数 |
| 锐度 | 高=原效果，中和轻更柔和；尚未证明与官方锐度档位一一等价 |
| 输出帧率 | 保持原帧率、30、48、60、自定义，或高级倍数模式 |
| 自定义帧率 | 仅自定义模式生效，支持1～240及29.97等小数 |
| 倍数插帧 | 仅高级倍数模式生效，可选2或4 |
| 每批帧数 | 默认17，显存不足可降至9或5 |
| 固定种子 | 默认42，便于对比效果 |
| 切镜保护 / 阈值 | 默认开启、0.30；补帧时跳过检测到的切镜，阈值越低越敏感 |

720p时，16:9输出1280×720，9:16输出720×1280，3:4输出720×960。4K在此表示短边2160，超宽画面长边不一定是3840。

升帧率使用独立RIFE补帧，降帧率按时间抽帧。不会靠加速/慢放改变帧率。因输出帧数必须取整，视频尾部可能与原音轨相差不足一个目标帧，处理信息会列出具体差值。

输出默认位于 `ComfyUI/output/1renmanju/`。API示例见 [workflows/1renmanju-api.json](workflows/1renmanju-api.json)，其中 `file` 必须换成上传后的视频文件名。

## 从实验版迁移

- 本版本只提供一个正式节点，移除了早期V1/V2/V3、独立加载器和独立高级设置入口。旧多节点工作流请改用上述新工作流。
- 最新「单节点配置」工作流的内部类型ID保留为 `Starlight26VideoEnhanceUnified`，加载后只需重新选择新名称的模型；无需重新连线。
- 不要同时安装旧 `ComfyUI-Starlight26-Independent` 和本插件，否则相同类型ID可能互相覆盖。
- 模型只是更名，权重内容和文件内格式版本不变；不要自行修改模型内部结构标记。

## 边界

当前为8位SDR流程；没有官方引擎完整等价性结论。长视频会占用较多内存，建议先截短验证；4K长片和其他硬件尚未验收。切镜识别可能受闪光/高速运动影响。取消会在当前推理步骤结束后响应。音轨可能重新编码，保留声音内容而非字节不变。

## 开发与来源

- [项目由来和技术来源](docs/ORIGIN.md)
- [维护与验证](docs/DEVELOPMENT.md)
- [第三方代码说明](THIRD_PARTY_NOTICES.md)
- [变更记录](CHANGELOG.md)

代码和模型分开管理；仓库中不收录研究凭据、原程序二进制、个人测试视频和大模型权重。自有集成代码尚未指定对外开源许可证，第三方部分保留各自许可，不能用其中某一份许可代表整个仓库或模型权重。
