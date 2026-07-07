"""service 拆分基线采集脚本。

输出 ``service-baseline.json``，包含：
- ``document.service``: 顶层名称（import * 会拿到的东西）
- ``page_exploration.service``: 顶层名称
- ``document.service.used_by_external``: 列出哪些外部模块用了里面的名字（精确 non-from-import 集合）
- ``page_exploration.service.used_by_external``: 同上

设计要点（仅采集，不改业务）：
- 在 ``app.services`` 已正确初始化的前提下 import，避免触发不可预测的副作用
- 不导入 sub 的发探测，只走静态 AST 扫描，安全可重跑
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


def collect_module_public_names(module_name: str) -> dict[str, list[str]]:
    """Import a module; return sorted (non-private, non-dunder) names."""
    import importlib

    mod = importlib.import_module(module_name)
    public = sorted(n for n in dir(mod) if not n.startswith("_"))
    private = sorted(n for n in dir(mod) if n.startswith("_") and not n.startswith("__"))
    return {"public": public, "private": private, "all": sorted(dir(mod))}


def collect_external_imports(target_module: str, search_root: Path) -> list[dict]:
    """Walk .py files under search_root, collect every ImportFrom / Import statement
    that targets ``target_module`` (as a from-import root or full-path import).

    For from-imports of ``from app.services.document.service import x, y`` we record which
    specific names were imported; for from-imports of
    ``from app.services.document import service as document_service`` we just record
    that the target module is imported.
    """
    hits: list[dict] = []
    for py in search_root.rglob("*.py"):
        if py.name == __file__.split("/")[-1]:
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == target_module or node.module.startswith(target_module + "."):
                    names = []
                    for alias in node.names:
                        names.append(alias.asname or alias.name)
                    hits.append({
                        "file": str(py.relative_to(search_root)),
                        "lineno": node.lineno,
                        "import_module": node.module,
                        "level": node.level,
                        "names": sorted(names),
                        "kind": "from-import",
                    })
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == target_module or alias.name.startswith(target_module + "."):
                        hits.append({
                            "file": str(py.relative_to(search_root)),
                            "lineno": node.lineno,
                            "import_module": alias.name,
                            "level": 0,
                            "names": [alias.asname or alias.name.split(".")[-1]],
                            "kind": "plain-import",
                        })
    return hits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(BACKEND_ROOT / "service-baseline.json"))
    args = parser.parse_args()

    targets = [
        "app.services.document.service",
        "app.services.page_exploration.service",
    ]

    baseline: dict = {}
    for target in targets:
        print(f"[baseline] importing {target} ...", flush=True)
        public_names = collect_module_public_names(target)
        print(f"  public={len(public_names['public'])} private={len(public_names['private'])}", flush=True)
        ext = collect_external_imports(target, BACKEND_ROOT / "app")
        test_ext = collect_external_imports(target, BACKEND_ROOT / "tests")
        baseline[target] = {
            "names": public_names,
            "external_imports_app": ext,
            "external_imports_tests": test_ext,
        }
        print(f"  external hits: app={len(ext)} tests={len(test_ext)}", flush=True)

    out_path = Path(args.out)
    out_path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[baseline] wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
