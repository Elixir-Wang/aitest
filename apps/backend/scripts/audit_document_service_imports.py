"""检测文档子包各 .py 文件的 unused imports / 重复 import / 函数内 shadow import。"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

DOCUMENT_DIR = Path(__file__).resolve().parents[1] / "app" / "services" / "document"
TARGETS = [
    "_common.py",
    "_constants.py",
    "serdes.py",
    "versions.py",
    "documents.py",
    "analysis.py",
    "analysis_runs.py",
    "service.py",
]


def collect_top_level_names(tree: ast.Module) -> set[str]:
    """收集所有顶层定义名（def / class / import alias / assigned name）。"""
    names: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(stmt.name)
        elif isinstance(stmt, ast.ClassDef):
            names.add(stmt.name)
        elif isinstance(stmt, ast.Import):
            for alias in stmt.names:
                names.add((alias.asname or alias.name.split(".")[0]))
        elif isinstance(stmt, ast.ImportFrom):
            for alias in stmt.names:
                names.add((alias.asname or alias.name))
        elif isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name):
                    names.add(tgt.id)
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            names.add(stmt.target.id)
    return names


def collect_function_imports(tree: ast.Module) -> list[tuple[int, str]]:
    """收集所有 def 内部的 import（按行号排序）。"""
    results: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                if sub is node:
                    continue
                if isinstance(sub, ast.ImportFrom):
                    names = ", ".join((a.asname or a.name) for a in sub.names)
                    results.append((sub.lineno, f"{sub.module!r} -> [{names}]"))
                elif isinstance(sub, ast.Import):
                    names = ", ".join((a.asname or a.name.split(".")[0]) for a in sub.names)
                    results.append((sub.lineno, f"import [{names}]"))
    return results


def collect_imports(tree: ast.Module) -> list[tuple[int, str, str]]:
    """返回 (lineno, kind, names-as-str)。"""
    out: list[tuple[int, str, str]] = []
    for stmt in tree.body:
        if isinstance(stmt, ast.Import):
            names = ", ".join((a.asname or a.name.split(".")[0]) for a in stmt.names)
            out.append((stmt.lineno, "import", names))
        elif isinstance(stmt, ast.ImportFrom):
            names = ", ".join((a.asname or a.name) for a in stmt.names)
            out.append((stmt.lineno, f"from {stmt.module}", names))
    return out


def count_name_in_code(source: str, name: str, exclude_linenos: set[int]) -> int:
    """在源码中按行计数 name 出现次数，但排除 import 行（由 caller 提供 linenos）。"""
    n = 0
    for i, line in enumerate(source.splitlines(), start=1):
        if i in exclude_linenos:
            continue
        # 不算注释行
        stripped = line.split("#", 1)[0]
        if name in stripped:
            n += 1
    return n


def main() -> int:
    for fname in TARGETS:
        path = DOCUMENT_DIR / fname
        if not path.exists():
            print(f"\n=== {fname}: NOT FOUND ===")
            continue
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)

        print(f"\n=== {fname} ===")

        # 1) top-level imports
        imports = collect_imports(tree)
        # 把 import 行的 lineno 全部记下供排除
        import_linenos: set[int] = set()
        for lineno, _, _ in imports:
            import_linenos.add(lineno)

        for lineno, kind, names in imports:
            print(f"  L{lineno} {kind}: {names}")

        # 2) function-internal imports (often redundant with module-level)
        print("  -- function-internal imports --")
        func_imports = collect_function_imports(tree)
        if not func_imports:
            print("    (none)")
        else:
            for lineno, desc in func_imports:
                print(f"    L{lineno}: {desc}")

        # 3) unused top-level imports
        print("  -- unused top-level imports --")
        for lineno, kind, names in imports:
            for name in [n.strip() for n in names.split(",")]:
                if not name:
                    continue
                refs = count_name_in_code(src, name, import_linenos)
                if refs == 0:
                    print(f"    UNUSED L{lineno}: {name}  ({kind})")

        # 4) duplicate imports
        print("  -- potential duplicate imports --")
        seen: dict[str, int] = {}
        for lineno, kind, names in imports:
            for name in [n.strip() for n in names.split(",")]:
                if not name:
                    continue
                if name in seen:
                    print(f"    DUP L{lineno}: {name}  (first at L{seen[name]})")
                else:
                    seen[name] = lineno

    return 0


if __name__ == "__main__":
    sys.exit(main())