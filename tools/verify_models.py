"""按仓库清单只读检查模型大小和SHA256，不下载或改写文件。"""
import argparse
import hashlib
import json
from pathlib import Path


def verify(models_dir, with_rife=False):
    root = models_dir.resolve(strict=True)
    manifest = json.loads((Path(__file__).resolve().parents[1] / 'models/manifest.json').read_text(encoding='utf8'))
    results = []
    for model in manifest['models']:
        if not model['required'] and not with_rife:
            continue
        path = (root / model['path']).resolve()
        if not path.is_relative_to(root):
            raise ValueError('清单中的模型路径超出指定目录')
        item = {'name': model['name'], 'path': model['path'], 'ok': False}
        if not path.is_file():
            item['error'] = '文件不存在'
        elif path.stat().st_size != model['size_bytes']:
            item['error'] = '文件大小不匹配'
        else:
            digest = hashlib.sha256()
            with path.open('rb') as file:
                for block in iter(lambda: file.read(8 * 1024 * 1024), b''):
                    digest.update(block)
            item['sha256'] = digest.hexdigest()
            item['ok'] = item['sha256'] == model['sha256']
            if not item['ok']:
                item['error'] = 'SHA256不匹配'
        results.append(item)
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models-dir', required=True, type=Path)
    parser.add_argument('--with-rife', action='store_true')
    args = parser.parse_args()
    results = verify(args.models_dir, args.with_rife)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all(item['ok'] for item in results) else 1)
