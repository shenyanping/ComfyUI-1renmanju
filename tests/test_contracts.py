"""覆盖用户可见的尺寸、时间线和示例契约，不加载大模型。"""
import importlib.util
import json
import unittest
from fractions import Fraction
from pathlib import Path
import torch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('video_controls_test', ROOT / 'video_controls.py')
controls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controls)


class VideoContractTests(unittest.TestCase):
    def test_portrait_and_landscape(self):
        mode = '720p（短边720）'
        self.assertEqual(controls.resolve_size(1920, 1080, mode), (1280, 720))
        self.assertEqual(controls.resolve_size(1080, 1920, mode), (720, 1280))
        self.assertEqual(controls.resolve_size(372, 496, mode), (720, 960))
        self.assertEqual(controls.resolve_size(372, 496, '自定义短边', 128), (128, 170))

    def test_rate_and_duration(self):
        self.assertEqual(controls.output_frame_count(6, 24, 60), 15)
        self.assertEqual(controls.output_frame_count(6, 24, 30), 8)
        source = Fraction(24000, 1001)
        self.assertEqual(controls.resolve_frame_rate('保持原帧率', source), source)
        self.assertEqual(controls.resolve_frame_rate('自定义帧率', source, 29.97), Fraction(2997, 100))
        self.assertEqual(controls.resolve_frame_rate('高级倍数模式', 24, multiplier=2), 48)
        for count in (1, 6, 10000, 1000000):
            for target in (30, 48, 60, Fraction(2997, 100)):
                frames = controls.output_frame_count(count, source, target)
                self.assertLess(abs(Fraction(frames, target) - Fraction(count, source)), 1 / target)

    def test_invalid_rates_fail(self):
        for value in (0, -1, 'nan', 'inf', '错误'):
            with self.assertRaises(ValueError):
                controls.valid_fps(value)

    def test_keep_and_reduce_without_rife(self):
        images = torch.arange(6, dtype=torch.float32).view(6,1,1,1).expand(6,64,64,3).clone()
        result, cuts = controls.resample_frames(images, 24, 24, torch.device('cpu'))
        self.assertIs(result, images)
        result, cuts = controls.resample_frames(images, 60, 30, torch.device('cpu'))
        self.assertEqual(result[:,0,0,0].tolist(), [0,2,4])
        self.assertEqual(cuts, 0)

    def test_cancellation(self):
        def cancel():
            raise InterruptedError('测试取消')
        with self.assertRaises(InterruptedError):
            controls.resample_frames(torch.zeros(2,64,64,3), 24, 60, torch.device('cpu'), check_cancel=cancel)

    def test_workflow_and_manifest(self):
        workflow = json.loads((ROOT / 'workflows/1renmanju-超分v1.json').read_text(encoding='utf8'))
        node = next(n for n in workflow['nodes'] if n['type'] == 'Starlight26VideoEnhanceUnified')
        self.assertEqual(len(node['widgets_values']), 11)
        self.assertEqual(node['widgets_values'][0], '1ren-chaofen-v1.safetensors')
        self.assertEqual(len(workflow['nodes']), 5)
        prompt = json.loads((ROOT / 'workflows/1renmanju-api.json').read_text(encoding='utf8'))
        self.assertEqual(prompt['3']['inputs']['模型文件'], node['widgets_values'][0])
        manifest = json.loads((ROOT / 'models/manifest.json').read_text(encoding='utf8'))
        self.assertEqual(len(manifest['models']), 2)
        for model in manifest['models']:
            self.assertEqual(len(model['sha256']), 64)
            self.assertFalse(Path(model['path']).is_absolute())


if __name__ == '__main__':
    unittest.main()
