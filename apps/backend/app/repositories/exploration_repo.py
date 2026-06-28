"""Exploration repository - compatibility wrapper

This module provides backward compatibility for the old exploration_repo naming.
New code should use exploration_run_repo directly.
"""

from app.repositories.exploration_run_repo import *

# Re-export all functions for backward compatibility
__all__ = [
    "find_by_id",
    "list_by_project",
    "list_running",
    "create",
    "update_status",
    "update_artifact_root",
    "delete",
]
