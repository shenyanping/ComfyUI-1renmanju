"""只读取单个 safetensors；运行时不读取原分片或调用外部处理程序。"""
import gc
import json
import math
from pathlib import Path

import cv2
import numpy as np
import torch
from omegaconf import OmegaConf
from safetensors import safe_open


def inspect_checkpoint(path):
    with safe_open(str(path), framework="pt", device="cpu") as f:
        meta = f.metadata() or {}
        if meta.get("format") != "starlight26_independent" or meta.get("schema_version") != "1":
            raise ValueError("请选择1ren-chaofen-v1 单文件模型，普通 SD 模型不能用于此节点。")
        expected = json.loads((Path(__file__).parent / "architecture.json").read_text(encoding="utf-8"))
        for name in ("dit_config", "vae_config"):
            if json.loads(meta.get(name, "null")) != expected[name]:
                raise ValueError("模型结构与当前节点不匹配，请使用配套模型文件。")
        if len(f.keys()) != 1175 or not {"text.pos", "text.neg"}.issubset(f.keys()):
            raise ValueError("模型文件组件不完整。")
    return expected


class QuietDebug:
    def log(self, *args, **kwargs):
        pass


def load_runner(path, device, check_cancel=lambda: None, decoder="standard"):
    if decoder not in ("standard", "m05", "m10"):
        raise ValueError("未知锐度解码器。")
    config = inspect_checkpoint(path)
    from .vendor.models.dit_3b.nadit import NaDiT
    from .vendor.models.video_vae_v3.modules.attn_video_vae import VideoAutoencoderKLWrapper
    from .vendor.core.infer import VideoDiffusionInfer
    from rotary_embedding_torch import RotaryEmbedding

    with torch.device("meta"):
        dit = NaDiT(**config["dit_config"])
        vae = VideoAutoencoderKLWrapper(freeze_encoder=False, **config["vae_config"])
    with safe_open(str(path), framework="pt", device="cpu") as f:
        for model, prefixes in ((dit, ("dit.",)), (vae, ("vae_encoder.", f"vae_decoders.{decoder}."))):
            weights = {}
            for key in f.keys():
                for prefix in prefixes:
                    if key.startswith(prefix):
                        check_cancel()
                        weights[key[len(prefix):]] = f.get_tensor(key).to(device=device, dtype=torch.bfloat16)
            model.load_state_dict(weights, strict=True, assign=True)
            model.eval().requires_grad_(False)
            del weights
        pos = f.get_tensor("text.pos").to(device=device, dtype=torch.bfloat16)
        neg = f.get_tensor("text.neg").to(device=device, dtype=torch.bfloat16)
    for module in dit.modules():
        if isinstance(module, RotaryEmbedding):
            for name in ("cached_freqs", "dummy"):
                value = getattr(module, name)
                if value.is_meta:
                    setattr(module, name, torch.zeros(value.shape, dtype=value.dtype, device=device))
    if any(x.is_meta for model in (dit, vae) for x in (*model.parameters(), *model.buffers())):
        raise RuntimeError("模型仍有未加载的参数或缓存。")
    vae.debug = None
    vae.set_causal_slicing(split_size=4, memory_device="same")
    options = OmegaConf.create({
        "vae": {"dtype": "bfloat16", "scaling_factor": 0.9152, "grouping": False,
                "model": {"spatial_downsample_factor": 8, "temporal_downsample_factor": 4}},
        "diffusion": {"schedule": {"type": "lerp", "T": 1000.0},
                      "sampler": {"type": "euler", "prediction_type": "v_lerp"},
                      "timesteps": {"sampling": {"type": "uniform_trailing", "steps": 1}, "transform": True},
                      "cfg": {"scale": 1.0, "rescale": 0}},
    })
    runner = VideoDiffusionInfer(options, QuietDebug(), encode_tiled=True, encode_tile_size=(320, 320),
                                decode_tiled=True, decode_tile_size=(320, 320))
    runner.dit, runner.vae = dit, vae
    runner.configure_diffusion(device=device, dtype=torch.bfloat16)
    return runner, pos, neg


def prepare_frames(images, height, target_width=None):
    """按原比例缩放，补齐网络所需尺寸；只处理当前批。"""
    width = target_width or max(2, round(images.shape[2] * height / images.shape[1] / 2) * 2)
    padded_h, padded_w = math.ceil(height / 16) * 16, math.ceil(width / 16) * 16
    top, left = (padded_h - height) // 2, (padded_w - width) // 2
    frames = []
    for frame in images:
        rgb = frame[..., :3].detach().cpu().clamp(0, 1).mul(255).round().byte().numpy()
        rgb = cv2.resize(rgb, (width, height), interpolation=cv2.INTER_CUBIC)
        frames.append(cv2.copyMakeBorder(rgb, top, padded_h-height-top, left, padded_w-width-left, cv2.BORDER_REPLICATE))
    while (len(frames) - 1) % 4:
        frames.append(frames[-1])
    return np.stack(frames), (top, left, height, width)


@torch.inference_mode()
def infer_batch(runner, pos, neg, frames, crop, valid, seed, check_cancel=lambda: None):
    device = next(runner.dit.parameters()).device
    x = torch.from_numpy(frames).permute(3, 0, 1, 2).to(device=device, dtype=torch.bfloat16) / 127.5 - 1
    latent = runner.vae_encode([x])[0]
    check_cancel()
    # 每批种子与此前验证方案一致，不影响调用方的随机数状态。
    torch.manual_seed(seed)
    noise = torch.randn_like(latent)
    predicted = runner.inference([noise], [runner.get_condition(noise, latent, "sr")], [pos], [neg])
    check_cancel()
    if not torch.isfinite(predicted[0]).all():
        raise RuntimeError("超分产生无效数值，请减小每批帧数后重试。")
    out = runner.vae_decode(predicted)[0]
    check_cancel()
    # 上游解码器对单帧输入返回 C×H×W，补回时间维度以兼容静帧视频。
    if out.ndim == 3 and valid == 1:
        out = out.unsqueeze(1)
    if out.ndim != 4:
        raise RuntimeError(f"视频解码返回了不支持的画面形状：{tuple(out.shape)}")
    if not torch.isfinite(out).all():
        raise RuntimeError("视频解码产生无效数值。")
    top, left, height, width = crop
    # 与已验证的视频方案保持相同的 8 位输出取整方式。
    return out[:, :valid, top:top+height, left:left+width].float().clamp(-1, 1).add(1).mul(127.5).byte().permute(1, 2, 3, 0).cpu().float().div_(255)


def upscale(path, images, target_height, batch_frames, seed, device, progress=lambda n, total: None, check_cancel=lambda: None, decoder="standard", target_width=None):
    if images.ndim != 4 or images.shape[-1] not in (3, 4) or len(images) < 1:
        raise ValueError("需要至少一帧 RGB 视频或图片。")
    if device.type != "cuda" or not torch.cuda.is_bf16_supported():
        raise ValueError("当前独立版本需要支持 BF16 的 NVIDIA 显卡。")
    if target_height < 64 or target_height > 8192 or target_height % 2:
        raise ValueError("目标高度需为 64～8192 之间的偶数。")
    if target_width is not None and (target_width < 64 or target_width > 8192 or target_width % 2):
        raise ValueError("目标宽度需为 64～8192 之间的偶数。")
    if batch_frames not in (5, 9, 17, 33):
        raise ValueError("每批帧数请选择 5、9、17 或 33。")
    runner = pos = neg = None
    try:
        check_cancel()
        count = len(images)
        width = target_width or max(2, round(images.shape[2] * target_height / images.shape[1] / 2) * 2)
        from .video_controls import check_output_memory
        check_output_memory(count, target_height, width)
        runner, pos, neg = load_runner(path, device, check_cancel, decoder)
        output = torch.empty((count, target_height, width, 3), dtype=torch.float32, device="cpu")
        start, written = 0, 0
        with torch.random.fork_rng(devices=[device.index if device.index is not None else torch.cuda.current_device()]):
            while written < count:
                check_cancel()
                end = min(start + batch_frames, count)
                frames, crop = prepare_frames(images[start:end], target_height, width)
                result = infer_batch(runner, pos, neg, frames, crop, end-start, seed, check_cancel)
                skip = 0 if start == 0 else 1
                output[written:written+len(result)-skip].copy_(result[skip:])
                written += len(result)-skip
                progress(written, count)
                print(f"[1ren-chaofen-v1] 已完成 {written}/{count} 帧", flush=True)
                del frames, result
                start = end-1
        return output
    finally:
        runner = pos = neg = None
        gc.collect()
        if device.type == "cuda":
            torch.cuda.empty_cache()
