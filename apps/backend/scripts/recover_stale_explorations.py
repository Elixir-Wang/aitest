#!/usr/bin/env python3
"""
恢复卡死的探索任务脚本

用法：
    python scripts/recover_stale_explorations.py [--dry-run]
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.db import connect
from app.repositories import exploration_repo
from loguru import logger


def recover_stale_explorations(dry_run: bool = False) -> dict:
    """
    恢复所有卡死的探索任务

    Args:
        dry_run: 如果为 True，只输出将要恢复的任务，不实际修改数据库

    Returns:
        恢复结果统计
    """
    stats = {
        "total_checked": 0,
        "stale_found": 0,
        "recovered": 0,
        "failed": 0,
        "tasks": []
    }

    with connect() as db:
        # 查找所有处于 running/queued/stopping 状态的任务
        query = """
            SELECT
                id,
                title,
                status,
                started_at,
                created_at,
                result_summary,
                CAST((julianday('now') - julianday(COALESCE(started_at, created_at))) * 24 * 60 AS INTEGER) as minutes_running
            FROM exploration_runs
            WHERE status IN ('running', 'queued', 'stopping')
            ORDER BY created_at DESC
        """

        rows = [dict(row) for row in db.execute(query).fetchall()]
        stats["total_checked"] = len(rows)

        logger.info(f"检查到 {len(rows)} 个正在运行的任务")

        for row in rows:
            run_id = row["id"]
            title = row["title"]
            status = row["status"]
            minutes_running = row["minutes_running"] or 0

            # 判断是否卡死：运行超过 60 分钟
            is_stale = minutes_running > 60

            if is_stale:
                stats["stale_found"] += 1
                stats["tasks"].append({
                    "id": run_id,
                    "title": title,
                    "status": status,
                    "minutes_running": minutes_running
                })

                logger.warning(
                    f"发现卡死任务: {run_id} ({title}) - "
                    f"状态: {status}, 已运行: {minutes_running} 分钟"
                )

                if not dry_run:
                    try:
                        # 更新任务状态为 interrupted
                        exploration_repo.update_run_state(
                            db,
                            run_id,
                            status="interrupted",
                            result_summary=f"任务执行超时（运行时间: {minutes_running} 分钟），已自动中断。请检查日志并重新启动。",
                            finished=True
                        )
                        stats["recovered"] += 1
                        logger.success(f"✓ 已恢复任务: {run_id}")
                    except Exception as e:
                        stats["failed"] += 1
                        logger.error(f"✗ 恢复任务失败: {run_id} - {e}")
                else:
                    logger.info(f"[DRY RUN] 将恢复任务: {run_id}")

    return stats


def main():
    parser = argparse.ArgumentParser(description="恢复卡死的探索任务")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只显示将要恢复的任务，不实际修改数据库"
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("探索任务恢复脚本")
    logger.info(f"运行时间: {datetime.now(timezone.utc).isoformat()}")
    logger.info(f"模式: {'DRY RUN (仅预览)' if args.dry_run else '实际执行'}")
    logger.info("=" * 60)

    stats = recover_stale_explorations(dry_run=args.dry_run)

    logger.info("\n" + "=" * 60)
    logger.info("执行结果:")
    logger.info(f"  检查任务数: {stats['total_checked']}")
    logger.info(f"  发现卡死: {stats['stale_found']}")

    if not args.dry_run:
        logger.info(f"  成功恢复: {stats['recovered']}")
        logger.info(f"  恢复失败: {stats['failed']}")
    else:
        logger.info(f"  将要恢复: {stats['stale_found']}")

    if stats["tasks"]:
        logger.info("\n卡死任务列表:")
        for task in stats["tasks"]:
            logger.info(
                f"  - {task['id']}: {task['title']} "
                f"({task['status']}, {task['minutes_running']}分钟)"
            )

    logger.info("=" * 60)

    if args.dry_run and stats["stale_found"] > 0:
        logger.info("\n提示: 使用以下命令实际执行恢复:")
        logger.info("  python scripts/recover_stale_explorations.py")

    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
