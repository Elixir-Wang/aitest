import ast
import hashlib
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

from app.agents.performance_testing.script_generation.schemas import LocustScriptPlan, ScriptValidationResult


ALLOWED_IMPORTS = {"__future__", "json", "locust", "scenario_runtime"}
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
            has_http_user = has_http_user or any(_name(base) in {"HttpUser", "ScenarioUser", "EndpointUser"} for base in node.bases)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "execute_target":
            has_task = any(_name(decorator) == "task" for decorator in node.decorator_list)
        elif isinstance(node, ast.Call):
            call_name = _name(node.func)
            if isinstance(node.func, ast.Name) and call_name in FORBIDDEN_CALLS:
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
    if not has_controlled_request and "scenario_runtime" not in imported_modules:
        errors.append("请求必须使用 catch_response=True")
    if plan.target_type == "endpoint":
        if not plan.request or plan.request.method not in source or plan.request.name not in source:
            errors.append("脚本与结构化 Plan 不一致")
    else:
        expected_names = [step.request.name for step in plan.steps if step.request is not None]
        if plan.scenario_name not in source or any(name not in source for name in expected_names):
            errors.append("脚本与场景结构化 Plan 不一致")
        errors.extend(_required_static_binding_errors(plan))

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


def _required_static_binding_errors(plan: LocustScriptPlan) -> list[str]:
    errors: list[str] = []
    for step in plan.steps:
        for binding in step.bindings:
            if not binding.get("required"):
                continue
            source = binding.get("source") if isinstance(binding.get("source"), dict) else {}
            source_type = source.get("type")
            if source_type not in {"scenario", "environment", "secret", "literal"}:
                continue
            source_name = str(source.get("name") or source.get("key") or source_type or "unknown")
            target = str(binding.get("target") or "")
            if source_type == "literal":
                resolved = source.get("value") is not None
                ambiguous = False
            else:
                resolved, ambiguous = _scenario_variable_status(plan.scenario_variables, source_name)
            if ambiguous:
                errors.append(f"场景变量名称冲突：{step.id} {source_name}")
            elif not resolved:
                errors.append(f"必填场景绑定无法解析：{step.id} {source_name} -> {target}")
    return errors


def _scenario_variable_status(variables: dict[str, object], key: str) -> tuple[bool, bool]:
    if key in variables:
        return variables[key] is not None, False
    normalized = key.lower().replace("_", "-")
    matches = [
        value
        for variable_name, value in variables.items()
        if str(variable_name).lower().replace("_", "-") == normalized
    ]
    if len(matches) > 1:
        return False, True
    return bool(matches) and matches[0] is not None, False


def _isolated_import_error(source: str) -> str:
    from app.services.performance_testing.script_renderer import runtime_module_source

    with tempfile.TemporaryDirectory(prefix="performance-script-") as directory:
        path = Path(directory) / "locustfile.py"
        path.write_text(source, encoding="utf-8")
        (Path(directory) / "scenario_runtime.py").write_text(runtime_module_source(), encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import importlib.util,sys,os; p=sys.argv[1]; sys.path.insert(0, os.path.dirname(p)); s=importlib.util.spec_from_file_location('validated_locustfile',p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)",
                str(path),
            ],
            text=True,
            capture_output=True,
            timeout=15,
        )
        return "" if completed.returncode == 0 else (completed.stderr.strip() or completed.stdout.strip())[-1000:]
