"""Execute project exploration operations in any environment belonging to the project."""

from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin

import yaml

from app.core.db import connect
from app.core.environment_auth_state import auth_state_path, auth_state_summary
from app.core.settings import PROJECT_FILE_STORAGE_ROOT
from app.repositories import environment_repo
from app.services.page_exploration.browser_session import PlaywrightBrowserSession

from .models import OperationsArtifact, ReplayOperation, ReplayResult, ReplayStep, ReplayStepResult
from .store import OperationsStore


class ReplayError(ValueError):
    """Raised when a replay artifact or runtime environment is invalid."""


class ReplayService:
    def __init__(
        self,
        *,
        storage_root: Path | None = None,
        session_factory: Callable[..., PlaywrightBrowserSession] = PlaywrightBrowserSession,
    ) -> None:
        self._storage_root = Path(storage_root or PROJECT_FILE_STORAGE_ROOT)
        self._session_factory = session_factory

    def execute(
        self,
        *,
        project_id: str,
        environment_id: str,
        operation_key: str,
        parameters: dict[str, Any] | None = None,
        should_stop: Callable[[], bool] | None = None,
        on_step: Callable[[ReplayStepResult], None] | None = None,
    ) -> ReplayResult:
        environment = self._load_environment(project_id, environment_id)
        artifact = self.load_artifact(project_id)
        operation = next((item for item in artifact.operations if item.key == operation_key), None)
        if operation is None:
            raise ReplayError(f"项目中不存在操作：{operation_key}")
        if operation.status in {"deprecated", "degraded"}:
            raise ReplayError(f"操作当前不可执行：{operation.status}")

        parameters = self._resolve_parameters(operation, parameters or {})

        elements = self._load_elements(project_id)
        page_path = operation.page_path if operation.page_path.startswith("/") else f"/{operation.page_path}"
        start_url = urljoin(str(environment["site_url"]).rstrip("/") + "/", page_path)
        storage_state = self._storage_state(environment)
        results: list[ReplayStepResult] = []
        with self._session_factory(
            start_url=start_url,
            browser_channel="chrome",
            storage_state_path=storage_state,
        ) as session:
            for index, step in enumerate(operation.steps, start=1):
                if should_stop and should_stop():
                    break
                result = self._execute_step(session, step, elements, parameters)
                success = self._action_succeeded(result)
                if success and step.expected:
                    assertion = self._assert_expectations(session, step, elements, parameters)
                    result = {**result, "assertion": assertion}
                    success = assertion["success"]
                step_result = ReplayStepResult(
                    index=index,
                    action=step.action,
                    element_key=step.element_key,
                    success=success,
                    detail=result,
                )
                results.append(step_result)
                if on_step:
                    on_step(step_result)
                if not success:
                    break

        replay_result = ReplayResult(
            project_id=project_id,
            environment_id=environment_id,
            operation_key=operation_key,
            success=len(results) == len(operation.steps) and all(item.success for item in results),
            steps=results,
        )
        error = ""
        if not replay_result.success and results:
            error = str(results[-1].detail.get("failure") or results[-1].detail.get("assertion") or "执行失败")
        OperationsStore(self._storage_root).record_validation(
            project_id,
            operation,
            environment_id=environment_id,
            success=replay_result.success,
            error=error,
        )
        return replay_result

    def validate_operation(self, project_id: str, operation: ReplayOperation) -> None:
        elements = self._load_elements(project_id)
        missing_elements: set[str] = set()
        missing_parameters: set[str] = set()
        for step in operation.steps:
            if step.action in {"click", "fill", "press"} and step.element_key not in elements:
                missing_elements.add(step.element_key)
            if step.value_ref and step.value_ref not in operation.parameters:
                missing_parameters.add(step.value_ref)
            for expected in step.expected:
                if expected.element_key and expected.element_key not in elements:
                    missing_elements.add(expected.element_key)
                if expected.value_ref and expected.value_ref not in operation.parameters:
                    missing_parameters.add(expected.value_ref)
        if missing_elements:
            raise ReplayError(f"操作引用了不存在的项目元素：{', '.join(sorted(missing_elements))}")
        if missing_parameters:
            raise ReplayError(f"操作引用了未声明参数：{', '.join(sorted(missing_parameters))}")
        if operation.status in {"validated", "published"}:
            for key in {step.element_key for step in operation.steps if step.element_key}:
                self._resolve_locators(key, elements)

    def load_artifact(self, project_id: str) -> OperationsArtifact:
        path = self._project_root(project_id) / "operations.yaml"
        if not path.exists():
            raise ReplayError("项目尚未生成可复用 UI 操作产物。")
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return OperationsArtifact.model_validate(payload)
        except Exception as exc:
            raise ReplayError(f"operations.yaml 格式无效：{exc}") from exc

    def _load_environment(self, project_id: str, environment_id: str):
        with connect() as db:
            row = environment_repo.find_by_id(db, environment_id)
            if row is None or str(row["project_id"]) != project_id:
                raise ReplayError("所选环境不属于当前项目。")
            return dict(row)

    def _storage_state(self, environment: dict) -> Path | None:
        environment_id = str(environment["id"])
        summary = auth_state_summary(
            environment_id=environment_id,
            login_strategy=str(environment.get("login_strategy") or ""),
            reuse_auth_state=bool(environment.get("reuse_auth_state")),
        )
        path = auth_state_path(environment_id)
        return path if summary.get("status") == "valid" and path.exists() else None

    def _load_elements(self, project_id: str) -> dict[str, dict]:
        elements: dict[str, dict] = {}
        pages_dir = self._project_root(project_id) / "pages"
        for path in sorted(pages_dir.glob("*.yaml")) if pages_dir.exists() else []:
            if path.name == "pages-index.yaml":
                continue
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if payload.get("schema_version") != "3.0":
                raise ReplayError(f"页面产物版本无效：{path.name}")
            for element in (payload.get("page") or {}).get("elements") or []:
                key = str(element.get("key") or "")
                if key:
                    elements.setdefault(key, element)
            self._collect_state_elements(payload.get("states") or [], elements)
        return elements

    def _collect_state_elements(self, states: list, target: dict[str, dict]) -> None:
        for state in states:
            for element in state.get("elements") or []:
                key = str(element.get("key") or "")
                if key:
                    target.setdefault(key, element)
            self._collect_state_elements(state.get("children") or [], target)

    def _execute_step(self, session, step: ReplayStep, elements: dict[str, dict], parameters: dict[str, Any]) -> dict:
        if step.action == "navigate":
            return session.navigate(step.path)
        if step.action == "wait":
            return session.wait(step.milliseconds)
        if step.action == "go_back":
            return session.go_back()

        locators = self._resolve_locators(step.element_key, elements)
        attempts: list[dict] = []
        for locator in locators:
            if step.action == "click":
                result = session.click(locator)
            elif step.action == "fill":
                value = parameters.get(step.value_ref) if step.value_ref else step.value
                if value is None:
                    raise ReplayError(f"缺少运行参数：{step.value_ref}")
                result = session.fill(locator, str(value))
            elif step.action == "press":
                result = session.press(locator, step.key)
            else:
                raise ReplayError(f"不支持的操作：{step.action}")
            attempts.append({"locator": locator, "result": result})
            if self._action_succeeded(result):
                return {**result, "attempted_locators": attempts}
        return {"success": False, "attempted_locators": attempts}

    def _resolve_locators(
        self,
        element_key: str,
        elements: dict[str, dict],
    ) -> list[str]:
        element = elements.get(element_key)
        if element is None:
            raise ReplayError(f"找不到项目元素：{element_key}")
        locators = element.get("locators") or []
        codes = [str(item["code"]) for item in locators if item.get("code")]
        if not codes:
            raise ReplayError(f"元素没有可执行定位器：{element_key}")
        return list(dict.fromkeys(codes))

    def _resolve_parameters(self, operation: ReplayOperation, supplied: dict[str, Any]) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for name, spec in operation.parameters.items():
            value = supplied.get(name, spec.default)
            if value is None and spec.required:
                raise ReplayError(f"缺少运行参数：{name}")
            resolved[name] = value
        return resolved

    def _assert_expectations(
        self,
        session,
        step: ReplayStep,
        elements: dict[str, dict],
        parameters: dict[str, Any],
    ) -> dict:
        observation = session.observe()
        failures: list[str] = []
        for expected in step.expected:
            value = str(parameters.get(expected.value_ref, "")) if expected.value_ref else expected.value
            if expected.kind == "url_contains" and value not in str(observation.get("url") or ""):
                failures.append(f"URL 不包含 {value}")
            elif expected.kind == "title_contains" and value not in str(observation.get("title") or ""):
                failures.append(f"标题不包含 {value}")
            elif expected.kind == "overlay_visible" and not observation.get("overlay"):
                failures.append("预期浮层未出现")
            elif expected.kind == "element_value":
                locator_codes = set(self._resolve_locators(expected.element_key, elements))
                matched = next((item for item in observation.get("elements") or [] if any(
                    str((item.get(field) or {}).get("code") or "").removeprefix("page.") in locator_codes
                    for field in ("primary_selector", "fallback_selector")
                    if isinstance(item.get(field), dict)
                )), None)
                if matched is None or str(matched.get("value") or "") != value:
                    failures.append(f"元素值不等于预期：{expected.element_key}")
        return {"success": not failures, "failures": failures, "observation": {
            "url": observation.get("url"), "title": observation.get("title"),
            "state_signature": observation.get("state_signature"),
        }}

    def _project_root(self, project_id: str) -> Path:
        return self._storage_root / project_id / "page_exploration"

    @staticmethod
    def _action_succeeded(result: dict) -> bool:
        action = result.get("action_result") if isinstance(result, dict) else None
        if isinstance(action, dict):
            return action.get("success") is True
        if not isinstance(result, dict):
            return False
        if "success" in result:
            return result.get("success") is True
        return result.get("status") == "passed"
