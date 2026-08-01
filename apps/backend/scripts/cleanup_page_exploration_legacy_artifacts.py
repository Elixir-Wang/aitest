from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core import settings
from app.services.page_exploration.cutover_cleanup import (
    apply_legacy_cleanup_manifest,
    build_legacy_cleanup_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="清理页面探索旧产物")
    parser.add_argument("--dry-run", action="store_true", help="只生成 manifest，不删除文件")
    parser.add_argument("--apply", action="store_true", help="按 manifest 删除旧产物")
    parser.add_argument("--manifest", type=Path, help="已审阅的 manifest 文件")
    parser.add_argument("--project-id", help="只处理一个项目")
    args = parser.parse_args()

    if args.apply:
        if not args.manifest:
            parser.error("--apply 必须提供 --manifest")
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = apply_legacy_cleanup_manifest(settings.PROJECT_FILE_STORAGE_ROOT, manifest)
    else:
        manifest = build_legacy_cleanup_manifest(settings.PROJECT_FILE_STORAGE_ROOT, args.project_id)
        result = manifest

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
