import ast
import hashlib
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

from app.services.performance_testing.models import LocustScriptPlan, ScriptValidationResult


ALLOWED_IMPORTS = {"json", "math", "random", "time", "uuid", "locust"}
FORBIDDEN_CALLS = {"eval", "exec", "compile", "open", "__import__", "input"}


def validate_locust_script(plan: LocustScriptPlan, source: str) -> ScriptValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        tree = ast.parse(source, filename="locustfile.py")
        compile(tree, "locustfile.py", "exec")
    except (SyntaxError, ValueError) as exc:
        return ScriptValidationResult(valid=False, errors=[f"脚本语法无效：{exc}"])

    imported_modules: set[str] = set()
    has_http_user = False
    has_task = False
    has_controlled_request = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module.split(".")[0])
        elif isinstance(node, ast.ClassDef):
            has_http_user = has_http_user or any(_name(base) == "HttpUser" for base in node.bases)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "execute_target":
            has_task = any(_name(decorator) == "task" for decorator in node.decorator_list)
        elif isinstance(node, ast.Call):
            call_name = _name(node.func)
            if call_name in FORBIDDEN_CALLS:
                errors.append(f"禁止调用：{call_name}")
            if call_name == "request":
                catch_response = next((keyword.value for keyword in node.keywords if keyword.arg == "catch_response"), None)
                has_controlled_request = isinstance(catch_response, ast.Constant) and catch_response.value is True

    forbidden_imports = sorted(imported_modules - ALLOWED_IMPORTS)
    errors.extend(f"禁止导入模块：{module}" for module in forbidden_imports)
    if not has_http_user:
        errors.append("脚本必须定义 HttpUser 子类")
    if not has_task:
        errors.append("脚本必须定义受 @task 管理的 execute_target")
    if not has_controlled_request:
        errors.append("请求必须使用 catch_response=True")
    if plan.request.method not in source or plan.request.name not in source:
        errors.append("脚本与结构化 Plan 不一致")

    if not errors:
        if importlib.util.find_spec("locust") is None:
            warnings.append("当前进程未安装 Locust，已跳过隔离导入校验。")
        else:
            import_error = _isolated_import_error(source)
            if import_error:
                errors.append(f"脚本隔离导入失败：{import_error}")

    return ScriptValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        code_hash=hashlib.sha256(source.encode("utf-8")).hexdigest(),
    )


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _isolated_import_error(source: str) -> str:
    with tempfile.TemporaryDirectory(prefix="performance-script-") as directory:
        path = Path(directory) / "locustfile.py"
        path.write_text(source, encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import importlib.util,sys; p=sys.argv[1]; s=importlib.util.spec_from_file_location('validated_locustfile',p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)",
                str(path),
            ],
            text=True,
            capture_output=True,
            timeout=15,
        )
        return "" if completed.returncode == 0 else (completed.stderr.strip() or completed.stdout.strip())[-1000:]
