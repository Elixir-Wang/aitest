import json
import secrets
from pathlib import Path

from app.agents.test_point_generation import extract_requirement_obligations, generate_test_points
from app.agents.test_point_generation.coverage import evaluate_test_point_coverage
from app.agents.test_point_generation.schemas import RequirementObligation, TestPointGenerationInput
from app.core.db import connect
from app.core.exceptions import api_error
from app.core.logging import logger
from app.core.storage import resolve_stored_path
from app.repositories import document_repo, project_repo, test_point_repo
from app.schemas.test_point import TestPointMarkdownUpdateIn, TestPointUpdateIn
from app.services.test_point_markdown import parse_test_points, serialize_test_points


STATUS_LABELS = {"queued": "排队中", "running": "生成中", "completed": "已完成", "failed": "生成失败"}


def recover_interrupted_generation_runs() -> None:
    with connect() as db:
        rows = db.execute(
            "SELECT id FROM test_point_generation_runs WHERE status IN ('queued', 'running')"
        ).fetchall()
        for row in rows:
            test_point_repo.update_run(db, row["id"], status="failed", error_message="服务重启导致测试点生成任务中断，请重新生成。")


def get_overview(project_id: str, document_id: str, actor) -> dict:
    with connect() as db:
        project = _require_project(db, project_id, actor)
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        version = document_repo.find_version(db, document["current_version_id"]) if document["current_version_id"] else None
        if not version or version["source_action"] not in {"requirement_analysis", "requirement_analysis_finalize", "edit"}:
            return {
                "requirement_version_id": None,
                "requirement_version_no": None,
                "run": None,
                "points": [],
                "markdown_content": "",
                "coverage_summary": {
                    "status": "pending",
                    "obligation_count": 0,
                    "covered_obligation_count": 0,
                    "missing_obligations": [],
                    "unsupported_assumptions": [],
                    "supplement_round": 0,
                },
            }
        run = test_point_repo.find_run_by_version(db, document_id, version["id"])
        rows = test_point_repo.list_points(db, document_id, version["id"])
        point_links = test_point_repo.list_point_obligation_links(db, version["id"]) if rows else {}
        obligations = test_point_repo.list_obligations(db, document_id, version["id"]) if run else []
        return {
            "requirement_version_id": version["id"],
            "requirement_version_no": version["version_no"],
            "run": _serialize_run(run),
            "points": [_serialize_point(row, point_links) for row in rows],
            "markdown_content": serialize_test_points([_serialize_internal_point(row) for row in rows]),
            "coverage_summary": _compute_coverage_summary(
                run,
                point_links,
                obligations,
            ) if run else {
                "status": "pending",
                "obligation_count": 0,
                "covered_obligation_count": 0,
                "missing_obligations": [],
                "unsupported_assumptions": [],
                "supplement_round": 0,
            },
        }


def update_point(project_id: str, document_id: str, point_id: str, payload: TestPointUpdateIn, actor) -> dict:
    _require_admin(actor)
    with connect() as db:
        _require_project(db, project_id, actor)
        point = test_point_repo.find_point(db, point_id)
        if not point or point["project_id"] != project_id or point["document_id"] != document_id:
            raise api_error(404, "TEST_POINT_NOT_FOUND", "测试点不存在。")
        values = payload.model_dump(exclude_unset=True)
        if "title" in values:
            title_identity = _title_identity(str(values["title"]))
            duplicate = next(
                (
                    row
                    for row in test_point_repo.list_points(
                        db,
                        point["document_id"],
                        point["requirement_version_id"],
                    )
                    if row["id"] != point_id and _title_identity(row["title"]) == title_identity
                ),
                None,
            )
            if duplicate is not None:
                raise api_error(
                    409,
                    "TEST_POINT_TITLE_DUPLICATE",
                    "测试点标题已存在，请使用能够区分测试目标的唯一标题。",
                )
        test_point_repo.update_point(db, point_id, values)
        return _serialize_point(test_point_repo.find_point(db, point_id), {})


def delete_point(project_id: str, document_id: str, point_id: str, actor) -> None:
    _require_admin(actor)
    with connect() as db:
        _require_project(db, project_id, actor)
        point = test_point_repo.find_point(db, point_id)
        if not point or point["project_id"] != project_id or point["document_id"] != document_id:
            raise api_error(404, "TEST_POINT_NOT_FOUND", "测试点不存在。")
        test_point_repo.delete_point(db, point_id)


def save_markdown(
    project_id: str,
    document_id: str,
    payload: TestPointMarkdownUpdateIn,
    actor,
) -> dict:
    _require_admin(actor)
    parsed_points = parse_test_points(payload.markdown_content)
    with connect() as db:
        _require_project(db, project_id, actor)
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        version = document_repo.find_version(db, document["current_version_id"]) if document["current_version_id"] else None
        if not version or version["source_action"] not in {"requirement_analysis", "requirement_analysis_finalize", "edit"}:
            raise api_error(409, "NO_FINAL_REQUIREMENT", "请先生成最终需求。")
        run = test_point_repo.find_run_by_version(db, document_id, version["id"])
        if not run:
            raise api_error(409, "TEST_POINTS_NOT_GENERATED", "当前最终需求尚未生成测试点。")
        existing_by_key = {
            row["point_key"]: row for row in test_point_repo.list_points(db, document_id, version["id"])
        }
        points = [
            point
            | {
                "id": existing_by_key[point["point_key"]]["id"]
                if point["point_key"] in existing_by_key
                else f"tp-{secrets.token_hex(8)}"
            }
            for point in parsed_points
        ]
        test_point_repo.replace_points(
            db,
            run_id=run["id"],
            project_id=project_id,
            document_id=document_id,
            version_id=version["id"],
            points=points,
        )
    return get_overview(project_id, document_id, actor)


def enqueue_generation(project_id: str, document_id: str, actor, *, require_admin: bool = False) -> dict:
    logger.info("enqueue_generation: start | project={}, document={}, actor={}", project_id, document_id, actor["id"])
    if require_admin:
        _require_admin(actor)
    with connect() as db:
        project = _require_project(db, project_id, actor)
        document = document_repo.find_by_project_and_id(db, project_id, document_id)
        if not document:
            raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")
        version = document_repo.find_version(db, document["current_version_id"]) if document["current_version_id"] else None
        logger.info("enqueue_generation: document={}, current_version_id={}, version={}", document_id, document["current_version_id"], version["id"] if version else None)
        if not version or version["source_action"] not in {"requirement_analysis", "requirement_analysis_finalize", "edit"}:
            logger.warning("enqueue_generation: no valid version | source_action={}", version["source_action"] if version else "None")
            raise api_error(409, "NO_FINAL_REQUIREMENT", "请先生成最终需求。")
        existing = test_point_repo.find_run_by_version(db, document_id, version["id"])
        if existing is not None:
            logger.info("enqueue_generation: existing run found | run_id={}, status={}", existing["id"], existing["status"])
            if existing["status"] in {"queued", "running"}:
                return _serialize_run(existing)
            if existing["status"] in {"completed", "failed"}:
                test_point_repo.requeue_run(db, existing["id"])
                run = test_point_repo.find_run(db, existing["id"])
                logger.info("enqueue_generation: requeued run | run_id={}, previous_status={}", existing["id"], existing["status"])
                return _serialize_run(run)
        run_id = f"tpgr-{secrets.token_hex(8)}"
        task_id = f"test_point_generation:{run_id}"
        input_snapshot = {
            "project_id": project_id,
            "document_id": document_id,
            "requirement_version_id": version["id"],
            "requirement_version_no": version["version_no"],
        }
        logger.info("enqueue_generation: creating new run | run_id={}, task_id={}", run_id, task_id)
        test_point_repo.create_run(
            db, run_id=run_id, project_id=project_id, document_id=document_id,
            version_id=version["id"], task_id=task_id,
            input_json=json.dumps(input_snapshot, ensure_ascii=False), created_by=actor["id"],
        )
        run = test_point_repo.find_run(db, run_id)
        logger.info("enqueue_generation: created | run_id={}", run_id)
        return _serialize_run(run)


async def execute_generation_run(run_id: str) -> None:
    logger.info("execute_generation_run: start | run_id={}", run_id)
    with connect() as db:
        run = test_point_repo.find_run(db, run_id)
        if not run or run["status"] != "queued":
            logger.warning("execute_generation_run: skip | run_id={}, status={}", run_id, run["status"] if run else "not_found")
            return
        test_point_repo.update_run(db, run_id, status="running")
        run = test_point_repo.find_run(db, run_id)
    try:
        with connect() as db:
            document = document_repo.find_by_project_and_id(db, run["project_id"], run["document_id"])
            version = document_repo.find_version(db, run["requirement_version_id"])
        if not document or not version:
            raise ValueError("最终需求版本不存在，无法生成测试点。")
        content = _read_version(version)
        logger.info("execute_generation_run: extracting obligations | run_id={}", run_id)
        obligation_result = await extract_requirement_obligations(
            TestPointGenerationInput(
                requirement_name=document["name"],
                requirement_content=content,
                requirement_version_id=version["id"],
            )
        )
        obligations = _atomize_module_obligations(
            [RequirementObligation(**ob.model_dump()) for ob in obligation_result.obligations]
        )
        if not obligations:
            raise ValueError("最终需求未提取出可验证的测试义务。")
        unsupported_from_extraction = list(obligation_result.unverifiable_items)
        logger.info("execute_generation_run: calling generate_test_points | run_id={}, requirement={}, obligations_count={}", run_id, document["name"], len(obligations))
        generation_input = TestPointGenerationInput(
            requirement_name=document["name"],
            requirement_content=content,
            requirement_version_id=version["id"],
        )
        with connect() as db:
            had_existing_points = bool(test_point_repo.list_points(db, run["document_id"], run["requirement_version_id"]))
        existing_points: list = []
        merged_points: dict[str, object] = {}
        unsupported_assumptions = list(unsupported_from_extraction)
        missing_keys: list[str] | None = None
        final_coverage = None
        completed_supplement_round = 0
        previous_missing_keys: set[str] | None = None
        for supplement_round in range(4):
            result = await generate_test_points(
                generation_input,
                obligations=obligations,
                existing_points=existing_points or None,
                missing_obligation_keys=missing_keys,
            )
            unsupported_assumptions.extend(result.unsupported_assumptions)
            for point in result.points:
                previous_point = merged_points.get(point.point_key)
                if previous_point is not None:
                    point = point.model_copy(
                        update={
                            "requirement_obligation_keys": list(dict.fromkeys(
                                previous_point.requirement_obligation_keys + point.requirement_obligation_keys
                            ))
                        }
                    )
                merged_points[point.point_key] = point
            existing_points = list(merged_points.values())
            final_coverage = evaluate_test_point_coverage(
                obligations,
                existing_points,
                unsupported_assumptions,
            )
            if final_coverage.status == "complete":
                completed_supplement_round = supplement_round
                break
            current_missing_keys = set(final_coverage.missing_obligation_keys)
            completed_supplement_round = supplement_round
            if previous_missing_keys is not None and not current_missing_keys < previous_missing_keys:
                logger.warning(
                    "execute_generation_run: coverage made no progress | run_id={}, missing={}, round={}",
                    run_id,
                    final_coverage.missing_obligation_keys,
                    supplement_round,
                )
                break
            previous_missing_keys = current_missing_keys
            missing_keys = final_coverage.missing_obligation_keys
            if supplement_round == 3:
                break
            logger.warning(
                "execute_generation_run: incomplete coverage | run_id={}, missing={}, round={}",
                run_id,
                final_coverage.missing_obligation_keys,
                supplement_round + 1,
            )

        if final_coverage is None:
            raise ValueError("测试点生成未返回结果。")
        points = [point.model_dump() | {"id": f"tp-{secrets.token_hex(8)}"} for point in existing_points]
        obligation_snapshots = [item.model_dump() for item in obligations]
        if final_coverage.status == "complete":
            logger.info("execute_generation_run: generated {} points | run_id={}", len(points), run_id)
            with connect() as db:
                test_point_repo.replace_obligations(
                    db,
                    project_id=run["project_id"],
                    document_id=run["document_id"],
                    version_id=run["requirement_version_id"],
                    obligations=obligation_snapshots,
                )
                test_point_repo.replace_points(
                    db, run_id=run_id, project_id=run["project_id"], document_id=run["document_id"],
                    version_id=run["requirement_version_id"], points=points,
                )
                test_point_repo.replace_point_obligation_links(
                    db,
                    version_id=run["requirement_version_id"],
                    links={point["id"]: point["requirement_obligation_keys"] for point in points},
                )
                test_point_repo.update_run(
                    db,
                    run_id,
                    status="completed",
                    coverage_status="complete",
                    obligation_count=final_coverage.obligation_count,
                    covered_obligation_count=final_coverage.covered_obligation_count,
                    missing_obligations_json=json.dumps([], ensure_ascii=False),
                    obligations_json=json.dumps(obligation_snapshots, ensure_ascii=False),
                    unsupported_assumptions_json=json.dumps(final_coverage.unsupported_assumptions, ensure_ascii=False),
                    supplement_round=completed_supplement_round,
                )
            logger.info("execute_generation_run: completed | run_id={}", run_id)
        else:
            with connect() as db:
                if not had_existing_points and points:
                    test_point_repo.replace_obligations(
                        db,
                        project_id=run["project_id"],
                        document_id=run["document_id"],
                        version_id=run["requirement_version_id"],
                        obligations=obligation_snapshots,
                    )
                    test_point_repo.replace_points(
                        db, run_id=run_id, project_id=run["project_id"], document_id=run["document_id"],
                        version_id=run["requirement_version_id"], points=points,
                    )
                    test_point_repo.replace_point_obligation_links(
                        db,
                        version_id=run["requirement_version_id"],
                        links={point["id"]: point["requirement_obligation_keys"] for point in points},
                    )
                test_point_repo.update_run(
                    db,
                    run_id,
                    status="failed",
                    error_message="测试点覆盖不完整，未达到完成门槛。",
                    coverage_status=final_coverage.status,
                    obligation_count=final_coverage.obligation_count,
                    covered_obligation_count=final_coverage.covered_obligation_count,
                    missing_obligations_json=json.dumps(final_coverage.missing_obligation_keys, ensure_ascii=False),
                    obligations_json=json.dumps(obligation_snapshots, ensure_ascii=False),
                    unsupported_assumptions_json=json.dumps(final_coverage.unsupported_assumptions, ensure_ascii=False),
                    supplement_round=completed_supplement_round,
                )
    except Exception as exc:
        logger.exception("execute_generation_run: failed | run_id={}, error={}", run_id, str(exc))
        with connect() as db:
            test_point_repo.update_run(db, run_id, status="failed", error_message=str(exc) or exc.__class__.__name__)


def _read_version(version) -> str:
    path = resolve_stored_path(version["file_path"]) or Path(version["file_path"])
    return path.read_text(encoding="utf-8") if path.is_file() else version["markdown_content"] or ""


def _atomize_module_obligations(obligations: list[RequirementObligation]) -> list[RequirementObligation]:
    """Make every explicitly listed module independently coverable."""
    atomized: list[RequirementObligation] = []
    for obligation in obligations:
        modules = [module.strip() for module in obligation.modules if module.strip()]
        if len(modules) <= 1:
            atomized.append(obligation)
            continue
        for index, module in enumerate(modules, start=1):
            atomized.append(
                obligation.model_copy(
                    update={
                        "obligation_key": f"{obligation.obligation_key}.M{index:02d}",
                        "modules": [module],
                        "statement": f"{obligation.statement}（模块：{module}）",
                    }
                )
            )
    return atomized


def _require_project(db, project_id: str, actor):
    project = project_repo.find_by_id(db, project_id)
    if not project:
        raise api_error(404, "PROJECT_NOT_FOUND", "项目不存在。")
    if actor["role"] not in {"admin", "guest"} and actor["project_scope"] not in {"全部项目", project["name"]}:
        raise api_error(403, "FORBIDDEN", "无权访问该项目。")
    return project


def _require_admin(actor) -> None:
    if actor["role"] != "admin":
        raise api_error(403, "FORBIDDEN", "仅管理员可以修改测试点。")


def _serialize_run(row):
    if not row:
        return None
    try:
        snapshot = json.loads(row["input_json"] or "{}")
    except json.JSONDecodeError:
        snapshot = {}
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "requirement_version_id": row["requirement_version_id"],
        "status": row["status"],
        "status_label": STATUS_LABELS.get(row["status"], row["status"]),
        "input_snapshot": snapshot,
        "error_message": row["error_message"],
        "coverage_status": row["coverage_status"],
        "obligation_count": row["obligation_count"],
        "covered_obligation_count": row["covered_obligation_count"],
        "missing_obligations": json.loads(row["missing_obligations_json"] or "[]"),
        "unsupported_assumptions": json.loads(row["unsupported_assumptions_json"] or "[]"),
        "supplement_round": row["supplement_round"],
        "created_at": row["created_at"],
        "finished_at": row["finished_at"],
    }


def _serialize_point(row, point_links: dict[str, list[str]] | None = None):
    if not row:
        return None
    serialized = {"id": row["id"], "project_id": row["project_id"], "document_id": row["document_id"], "requirement_version_id": row["requirement_version_id"], "generation_run_id": row["generation_run_id"], "title": row["title"], "module": row["module"], "category": row["category"], "priority": row["priority"], "description": row["description"], "preconditions": json.loads(row["preconditions_json"] or "[]"), "verification_points": json.loads(row["verification_points_json"] or "[]"), "source_refs": json.loads(row["source_refs_json"] or "[]"), "notes": row["notes"], "created_at": row["created_at"], "updated_at": row["updated_at"]}
    if point_links is not None:
        linked_keys = point_links.get(row["id"], [])
        serialized["requirement_obligations"] = [{"obligation_key": k, "source_section": "", "statement": ""} for k in linked_keys]
    else:
        serialized["requirement_obligations"] = []
    return serialized


def _serialize_internal_point(row):
    serialized = _serialize_point(row, None)
    serialized["point_key"] = row["point_key"]
    return serialized


def _compute_coverage_summary(
    run,
    point_links: dict[str, list[str]],
    obligations: list[dict],
) -> dict:
    run = dict(run) if run is not None else None
    coverage_status = run.get("coverage_status") if run else "pending"
    supplement_round = run.get("supplement_round") if run else 0
    unsupported_assumptions = _load_json_list(run.get("unsupported_assumptions_json")) if run else []
    if run and coverage_status in {"incomplete", "invalid"}:
        snapshot_obligations = _load_json_list(run.get("obligations_json")) or obligations
        obligation_map = {ob["obligation_key"]: ob for ob in snapshot_obligations}
        missing_keys = list(dict.fromkeys(
            str(key).split(":", 1)[0]
            for key in _load_json_list(run.get("missing_obligations_json"))
        ))
        missing = []
        for key in missing_keys:
            obligation = obligation_map.get(key)
            if obligation:
                missing.append({
                    "obligation_key": key,
                    "source_section": obligation["source_section"],
                    "statement": obligation["statement"],
                })
            else:
                missing.append({
                    "obligation_key": key,
                    "source_section": "最终需求",
                    "statement": key,
                })
        return {
            "status": coverage_status,
            "obligation_count": run.get("obligation_count") or len(snapshot_obligations),
            "covered_obligation_count": run.get("covered_obligation_count") or 0,
            "missing_obligations": missing,
            "unsupported_assumptions": unsupported_assumptions,
            "supplement_round": supplement_round or 0,
        }

    covered_keys: set[str] = set()
    for linked_keys in point_links.values():
        covered_keys.update(linked_keys)
    missing = [
        {"obligation_key": ob["obligation_key"], "source_section": ob["source_section"], "statement": ob["statement"]}
        for ob in obligations
        if ob["obligation_key"] not in covered_keys and ob.get("test_required", True)
    ]
    return {
        "status": coverage_status or "pending",
        "obligation_count": len(obligations),
        "covered_obligation_count": len([ob for ob in obligations if ob["obligation_key"] in covered_keys]),
        "missing_obligations": missing,
        "unsupported_assumptions": unsupported_assumptions,
        "supplement_round": supplement_round or 0,
    }


def _load_json_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    return value if isinstance(value, list) else []


def _title_identity(title: str) -> str:
    return " ".join(title.split()).casefold()
