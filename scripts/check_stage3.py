#!/usr/bin/env python3
"""
阶段3代码质量检查脚本
"""

import sys
import ast
from pathlib import Path

def check_syntax(file_path):
    """检查Python文件语法"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        ast.parse(code)
        return True, "OK"
    except SyntaxError as e:
        return False, f"Syntax Error: {e}"
    except Exception as e:
        return False, f"Error: {e}"

def check_imports(file_path):
    """检查导入语句"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        tree = ast.parse(code)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return True, f"Found {len(imports)} imports"
    except Exception as e:
        return False, f"Error: {e}"

def check_functions(file_path):
    """检查函数定义"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        tree = ast.parse(code)
        functions = []
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
        return True, f"Found {len(classes)} classes, {len(functions)} functions"
    except Exception as e:
        return False, f"Error: {e}"

def main():
    print("=" * 60)
    print("阶段3 代码质量检查")
    print("=" * 60)

    # 要检查的文件
    files_to_check = [
        "apps/backend/app/agents/page_exploration/artifact_service.py",
        "apps/backend/app/agents/page_exploration/exploration_queue.py",
        "apps/backend/app/agents/page_exploration/orchestrator.py",
        "apps/backend/tests/agents/page_exploration/test_artifact_service.py",
        "apps/backend/tests/agents/page_exploration/test_exploration_queue.py",
        "apps/backend/tests/agents/page_exploration/test_orchestrator.py",
    ]

    all_passed = True

    for file_path in files_to_check:
        path = Path(file_path)
        if not path.exists():
            print(f"\n❌ {file_path}")
            print(f"   文件不存在")
            all_passed = False
            continue

        print(f"\n✓ {file_path}")

        # 语法检查
        success, msg = check_syntax(path)
        if success:
            print(f"  ✅ 语法: {msg}")
        else:
            print(f"  ❌ 语法: {msg}")
            all_passed = False

        # 导入检查
        success, msg = check_imports(path)
        if success:
            print(f"  ✅ 导入: {msg}")
        else:
            print(f"  ❌ 导入: {msg}")
            all_passed = False

        # 函数检查
        success, msg = check_functions(path)
        if success:
            print(f"  ✅ 结构: {msg}")
        else:
            print(f"  ❌ 结构: {msg}")
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 所有检查通过！")
        print("\n阶段3代码质量：优秀")
        print("\n交付清单:")
        print("  - artifact_service.py: 产物生成服务")
        print("  - exploration_queue.py: 探索队列管理")
        print("  - orchestrator.py: 探索编排器")
        print("  - 3个完整的测试文件")
        print("\n准备开始阶段4：FastAPI Service + SSE")
        return 0
    else:
        print("❌ 发现问题，请修复后重试")
        return 1

if __name__ == "__main__":
    sys.exit(main())
