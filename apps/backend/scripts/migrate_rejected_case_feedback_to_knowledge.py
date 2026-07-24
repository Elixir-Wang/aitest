import argparse
import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.db import connect
from app.repositories import document_repo, test_case_repo
from app.services import rejected_case_knowledge


ACTOR = {"id": "system-migration", "role": "admin"}


def migrate(*, apply: bool) -> dict:
    with connect() as db:
        rows = db.execute(
            """
            SELECT tc.*, tcs.requirement_doc_id, p.name AS project_name
            FROM test_cases tc
            JOIN test_case_sets tcs ON tcs.id = tc.test_case_set_id
            JOIN projects p ON p.id = tc.project_id
            WHERE tc.status = 'rejected' AND TRIM(tc.review_feedback) != ''
            ORDER BY tc.project_id, tcs.requirement_doc_id, tc.id
            """
        ).fetchall()

    report = {"mode": "apply" if apply else "dry-run", "total": len(rows), "migrated": 0, "failed": []}
    migrated_case_ids = []
    for row in rows:
        try:
            with connect() as db:
                requirement = document_repo.find_by_project_and_id(db, row["project_id"], row["requirement_doc_id"])
                generation_run = test_case_repo.latest_completed_generation_run(db, row["test_case_set_id"])
                version = document_repo.find_version(db, requirement["current_version_id"]) if requirement else None
            if not requirement or not generation_run or not version:
                raise ValueError("缺少需求版本或已完成生成运行")
            if apply:
                rejected_case_knowledge.upsert_rejected_case(
                    project={"id": row["project_id"], "name": row["project_name"]},
                    requirement=dict(requirement),
                    requirement_version=dict(version),
                    generation_run_id=generation_run["id"],
                    test_case_set_id=row["test_case_set_id"],
                    test_case={
                        "id": row["id"],
                        "title": row["title"],
                        "module": row["module"],
                        "priority": row["priority"],
                        "preconditions": row["preconditions"],
                        "steps": json.loads(row["steps_json"] or "[]"),
                        "expected_result": row["expected_result"],
                    },
                    reason=row["review_feedback"].strip(),
                    actor=ACTOR,
                )
                migrated_case_ids.append(row["id"])
            report["migrated"] += 1
        except Exception as exc:  # noqa: BLE001 - migration report must retain all failures
            report["failed"].append({"case_id": row["id"], "error": str(exc)})

    if apply and not report["failed"] and migrated_case_ids:
        placeholders = ",".join("?" for _ in migrated_case_ids)
        with connect() as db:
            db.execute(
                f"UPDATE test_cases SET review_feedback = '' WHERE id IN ({placeholders})",
                migrated_case_ids,
            )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="将历史不采纳反馈迁移到公司知识库 Markdown。")
    parser.add_argument("--apply", action="store_true", help="实际写入；默认只输出 dry-run 报告。")
    args = parser.parse_args()
    print(json.dumps(migrate(apply=args.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
