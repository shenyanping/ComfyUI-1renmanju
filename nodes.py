"""1人漫剧视频增强入口：所有设置集中在一个节点。"""
import os
import folder_paths

folder_paths.add_model_folder_path("starlight26", os.path.join(folder_paths.models_dir, "starlight26"))
folder_paths.folder_names_and_paths["starlight26"][1].add(".safetensors")


class OneRenManjuVideoEnhance:
    @classmethod
    def INPUT_TYPES(cls):
        from .video_controls import RESOLUTIONS, SHARPNESS, FRAME_RATES
        return {"required": {
            "video": ("VIDEO",),
            "模型文件": (folder_paths.get_filename_list("starlight26"),),
            "输出尺寸": (RESOLUTIONS, {"default":RESOLUTIONS[0],"tooltip":"自动保持原比例，按画面短边设置。"}),
            "自定义短边": ("INT", {"default":1080,"min":64,"max":4320,"step":2,"tooltip":"仅在输出尺寸选择自定义短边时生效。"}),
            "锐度": (list(SHARPNESS), {"tooltip":"独立版相对档位，高保持原效果，中和轻更柔和。"}),
            "输出帧率": (FRAME_RATES, {"tooltip":"直接选择30/48/60fps，或选自定义帧率后填写下方数值。"}),
            "自定义帧率": ("FLOAT", {"default":60.0,"min":1.0,"max":240.0,"step":0.001,"tooltip":"仅在输出帧率选择自定义帧率时生效，支持29.97等小数。"}),
            "倍数插帧": ([2,4], {"default":2,"tooltip":"仅在输出帧率选择高级倍数模式时生效。"}),
            "每批帧数": ([5,9,17,33], {"default":17,"tooltip":"显存不足时降低到9或5，不改变视频帧率。"}),
            "固定种子": ("INT", {"default":42,"min":0,"max":0x7fffffff,"tooltip":"相同素材和设置下便于复现效果。"}),
            "切镜保护": ("BOOLEAN", {"default":True,"tooltip":"补帧时跳过识别出的切镜位置，避免生成混合过渡。"}),
            "切镜阈值": ("FLOAT", {"default":0.30,"min":0.05,"max":1.0,"step":0.01,"tooltip":"数值越小越容易判为切镜；仅切镜保护开启且需要补帧时生效。"}),
        }}

    RETURN_TYPES = ("VIDEO", "STRING")
    RETURN_NAMES = ("增强视频", "处理信息")
    FUNCTION = "run"
    CATEGORY = "1人漫剧/视频增强"
    DESCRIPTION = "1ren-chaofen-v1：比例、锐度、目标帧率及高级参数集中配置，保留原音轨。"

    @classmethod
    def IS_CHANGED(cls, **options):
        path = folder_paths.get_full_path_or_raise("starlight26", options["模型文件"])
        stat = os.stat(path)
        return f"{stat.st_mtime_ns}:{stat.st_size}"

    def run(self, video, **options):
        import comfy.model_management as mm
        from comfy.utils import ProgressBar
        from comfy_api.latest import InputImpl, Types
        from .runtime import inspect_checkpoint, upscale
        from .video_controls import resolve_size, SHARPNESS, resolve_frame_rate, output_frame_count, rife_model_path, check_output_memory, resample_frames
        settings = options
        model_path = folder_paths.get_full_path_or_raise("starlight26", options["模型文件"])
        inspect_checkpoint(model_path)
        if video.get_color_space() != "sRGB":
            raise ValueError("当前超分节点仅支持 SDR/sRGB 视频，请先正确转换 HDR 素材，避免颜色失真。")
        original_w, original_h = video.get_dimensions()
        width, height = resolve_size(original_w, original_h, options["输出尺寸"], settings.get("自定义短边",1080))
        mm.throw_exception_if_processing_interrupted()
        components = video.get_components()
        images = components.images
        source_fps = components.frame_rate
        fps = resolve_frame_rate(options["输出帧率"], source_fps,
                                 settings.get("自定义帧率",60), settings.get("倍数插帧",2))
        target_count = output_frame_count(len(images), source_fps, fps)
        if fps > source_fps and len(images) > 1:
            rife_model_path()
        # 插帧期间会同时保留超分结果和插帧结果，提前预估两份缓存。
        check_output_memory(len(images) + (target_count if fps != source_fps else 0), height, width)
        mm.unload_all_models()
        mm.soft_empty_cache()
        bar = ProgressBar(len(images))
        print(f"[1ren-chaofen-v1] {original_w}×{original_h} → {width}×{height}；锐度 {options['锐度']}；帧率 {float(source_fps):g} → {float(fps):g}",flush=True)
        enhanced = upscale(model_path, images, height, settings.get("每批帧数",17), settings.get("固定种子",42),
                           mm.get_torch_device(), lambda n,total:bar.update_absolute(n,total), mm.throw_exception_if_processing_interrupted,
                           decoder=SHARPNESS[options["锐度"]], target_width=width)
        cuts = 0
        if fps != source_fps:
            bar = ProgressBar(target_count)
            enhanced, cuts = resample_frames(enhanced, source_fps, fps, mm.get_torch_device(), settings.get("切镜保护",True),
                                                settings.get("切镜阈值",0.30), lambda n,total:bar.update_absolute(n,total), mm.throw_exception_if_processing_interrupted)
        result = InputImpl.VideoFromComponents(Types.VideoComponents(images=enhanced, audio=components.audio, frame_rate=fps), bit_depth=8, color_space="sRGB")
        original_duration, output_duration = len(images)/float(source_fps), len(enhanced)/float(fps)
        operation = "按目标时间补帧" if fps > source_fps else ("按目标时间抽帧" if fps < source_fps else "保持原帧率")
        audio_message = "保留原音轨，不改变音频速度" if components.audio is not None else "原视频无音轨"
        message = f"{original_w}×{original_h} → {width}×{height}\n{len(images)} → {len(enhanced)} 帧；{float(source_fps):g} → {float(fps):g} fps\n{operation}；锐度：{options['锐度']}\n切镜保护：跳过 {cuts} 处过渡；{audio_message}\n画面时长：{original_duration:.6f} → {output_duration:.6f} 秒\n末尾整帧取整差：{(output_duration-original_duration)*1000:+.3f} 毫秒（不改变播放速度）"
        return (result, message)


# 保持最新单节点工作流的类型ID，界面名称和插件目录使用新名称。
NODE_CLASS_MAPPINGS = {"Starlight26VideoEnhanceUnified": OneRenManjuVideoEnhance}
NODE_DISPLAY_NAME_MAPPINGS = {"Starlight26VideoEnhanceUnified": "1人漫剧 · 超分V1"}
