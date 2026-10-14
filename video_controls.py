"""分辨率、内存预检和独立 RIFE 插帧。"""
import gc
import math
from pathlib import Path
from fractions import Fraction

import psutil
import torch
import torch.nn.functional as F

RESOLUTIONS = ["720p（短边720）", "1080p（短边1080）", "1440p（短边1440）", "4K（短边2160）", "原尺寸", "放大2倍", "自定义短边"]
SHARPNESS = {"高（原效果）": "standard", "中（较柔和）": "m05", "轻（更柔和）": "m10"}
FRAME_RATES = ["保持原帧率", "30fps", "48fps", "60fps", "自定义帧率", "高级倍数模式"]


def valid_fps(value):
    try:
        fps = value if isinstance(value, Fraction) else Fraction(str(value))
    except (ValueError, TypeError, ZeroDivisionError, OverflowError):
        raise ValueError("帧率必须是有效的正数。") from None
    if fps <= 0:
        raise ValueError("帧率必须大于0。")
    return fps


def resolve_frame_rate(mode, source_fps, custom_fps=60, multiplier=2):
    source = valid_fps(source_fps)
    if mode == "保持原帧率":
        return source
    if mode == "高级倍数模式":
        if multiplier not in (2, 4):
            raise ValueError("高级倍数仅支持2倍或4倍。")
        return source * multiplier
    if mode in ("30fps", "48fps", "60fps"):
        return Fraction(int(mode[:-3]))
    if mode == "自定义帧率":
        target = valid_fps(custom_fps)
        if not 1 <= target <= 240:
            raise ValueError("自定义帧率范围为1～240fps，支持小数。")
        return target
    raise ValueError("未知输出帧率选项。")


def output_frame_count(count, source_fps, target_fps):
    if not isinstance(count, int) or count < 1:
        raise ValueError("没有可处理的视频帧。")
    # 采用有理数计算整条时间线，避免长视频因浮点累积而漂移。
    exact = count * valid_fps(target_fps) / valid_fps(source_fps)
    return max(1, (2 * exact.numerator + exact.denominator) // (2 * exact.denominator))


def resolve_size(width, height, resolution, custom_short=1080):
    if min(width, height) < 1 or resolution not in RESOLUTIONS:
        raise ValueError("视频尺寸或输出档位无效。")
    if resolution == "原尺寸":
        scale = 1.0
    elif resolution == "放大2倍":
        scale = 2.0
    else:
        short = {RESOLUTIONS[0]: 720, RESOLUTIONS[1]: 1080, RESOLUTIONS[2]: 1440, RESOLUTIONS[3]: 2160}.get(resolution, custom_short)
        if not isinstance(short, int) or short < 64 or short > 4320 or short % 2:
            raise ValueError("自定义短边需为 64～4320 之间的偶数。")
        scale = short / min(width, height)
    w, h = max(2, round(width * scale / 2) * 2), max(2, round(height * scale / 2) * 2)
    if min(w, h) < 64 or max(w, h) > 8192:
        raise ValueError(f"目标尺寸 {w}×{h} 超出当前范围（每边64～8192），请降低档位。")
    return w, h


def check_output_memory(count, height, width, reserve=1.25):
    required = count * height * width * 3 * 4 * reserve
    available = psutil.virtual_memory().available
    if required > available * 0.75:
        raise ValueError(f"本次画面缓存预计至少需要 {required/1024**3:.1f} GB 内存，当前可用 {available/1024**3:.1f} GB。请先截取较短视频，或降低分辨率/输出帧率；程序不会自动降低输出档位。")


def rife_model_path():
    import folder_paths
    path = Path(folder_paths.models_dir) / "rife" / "rife47.safetensors"
    if not path.is_file():
        raise ValueError("缺少插帧模型 models/rife/rife47.safetensors，请安装配套插帧模型，或选择保持原帧率。")
    return path


def is_scene_cut(a, b, threshold=0.30):
    # 缩略图亮度/颜色差异启发式检测；高速运动或闪光仍可能被当成切镜。
    small = F.interpolate(torch.stack((a[..., :3], b[..., :3])).permute(0, 3, 1, 2).float(), size=(48,48), mode="area")
    return bool((small[0] - small[1]).abs().mean().item() > threshold)


@torch.inference_mode()
def resample_frames(images, source_fps, target_fps, device, protect_cuts=True, threshold=0.30, progress=lambda n,total: None, check_cancel=lambda: None):
    if images.ndim != 4 or len(images) < 1:
        raise ValueError("没有可插帧的画面。")
    source, target = valid_fps(source_fps), valid_fps(target_fps)
    check_cancel()
    if target == source:
        return images, 0
    count, height, width, _ = images.shape
    total = output_frame_count(count, source, target)
    check_output_memory(total, height, width)
    rife_arch = None
    model = output = left = right = middle = None
    try:
        output = torch.empty((total, height, width, 3), dtype=torch.float32, device="cpu")
        cuts = 0
        previous_pair = -1
        cut = False
        for k in range(total):
            check_cancel()
            position = k * source / target
            i = min(position.numerator // position.denominator, count-1)
            fraction = position - i
            if target < source:
                # 降帧率只选择最接近目标时间的原画面，无需加载插帧模型。
                nearest = min((2*position.numerator+position.denominator)//(2*position.denominator), count-1)
                output[k].copy_(images[nearest, ..., :3])
            elif fraction == 0 or i == count-1:
                output[k].copy_(images[i, ..., :3])
            else:
                if i != previous_pair:
                    previous_pair = i
                    cut = protect_cuts and is_scene_cut(images[i], images[i+1], threshold)
                    cuts += int(cut)
                    left = right = None
                if cut:
                    output[k].copy_(images[i, ..., :3])
                else:
                    if model is None:
                        from safetensors.torch import load_file
                        from . import rife_arch
                        model = rife_arch.IFNet(arch_ver="4.7")
                        model.load_state_dict(load_file(str(rife_model_path())), strict=True)
                        model.eval().requires_grad_(False).to(device)
                    if left is None:
                        left = images[i:i+1, ..., :3].permute(0,3,1,2).to(device=device, dtype=torch.float32)
                        right = images[i+1:i+2, ..., :3].permute(0,3,1,2).to(device=device, dtype=torch.float32)
                    middle = model(left, right, timestep=float(fraction), scale_list=[8,4,2,1], training=False, fastmode=True, ensemble=False)
                    if not torch.isfinite(middle).all():
                        raise RuntimeError("插帧产生无效画面，请关闭插帧后重试。")
                    output[k].copy_(middle[0].permute(1,2,0).clamp(0,1).cpu())
                    middle = None
            progress(k+1,total)
        return output, cuts
    finally:
        model = left = right = middle = None
        if rife_arch is not None:
            rife_arch.backwarp_tenGrid.clear()
        gc.collect()
        if device.type == "cuda":
            torch.cuda.empty_cache()
