"""Artifact service for generating exploration artifacts

Generates various artifacts during and after exploration:
- discovered_pages.yaml
- graph.yaml (optional)
- report.md (optional)
"""

from pathlib import Path
from datetime import datetime, UTC
from typing import List, Dict, Optional
import yaml


class ArtifactService:
    """Service for generating exploration artifacts"""

    def __init__(self, project_id: str, run_id: str, base_dir: Optional[Path] = None):
        self.project_id = project_id
        self.run_id = run_id
        self.base_dir = Path(base_dir) if base_dir else Path("data/projects")
        self.run_dir = (
            self.base_dir / project_id / "page_exploration" / "runs" / run_id
        )

    def write_discovered_pages(
        self, pages: List[Dict], run_config: Optional[Dict] = None
    ) -> Path:
        """
        Write discovered_pages.yaml artifact.

        Args:
            pages: List of discovered page records
            run_config: Optional run configuration

        Returns:
            Path to the written file

        Page record format:
        {
            "page_id": "page-workspace-agents",
            "page_file": "../../pages/page-workspace-agents.yaml",
            "normalized_path": "/workspace/agents",
            "status": "new",  # or "updated"
            "elements_count": 15,
            "exploration_status": "completed"  # or "failed"
        }
        """
        self.run_dir.mkdir(parents=True, exist_ok=True)

        artifact = {
            "run_id": self.run_id,
            "discovered_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "pages": pages,
        }

        if run_config:
            artifact["config"] = run_config

        file_path = self.run_dir / "discovered_pages.yaml"
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(
                artifact, f, allow_unicode=True, sort_keys=False, default_flow_style=False
            )

        return file_path

    def write_run_summary(
        self,
        start_url: str,
        total_pages: int,
        successful_pages: int,
        failed_pages: int,
        start_time: str,
        end_time: str,
        duration_seconds: float,
        error: Optional[str] = None,
    ) -> Path:
        """
        Write run.yaml with run configuration and statistics.

        Args:
            start_url: Starting URL
            total_pages: Total number of pages discovered
            successful_pages: Number of successfully explored pages
            failed_pages: Number of failed pages
            start_time: ISO timestamp of run start
            end_time: ISO timestamp of run end
            duration_seconds: Total duration in seconds
            error: Error message if run failed

        Returns:
            Path to the written file
        """
        self.run_dir.mkdir(parents=True, exist_ok=True)

        summary = {
            "run_id": self.run_id,
            "project_id": self.project_id,
            "start_url": start_url,
            "start_time": start_time,
            "end_time": end_time,
            "duration_seconds": duration_seconds,
            "statistics": {
                "total_pages_discovered": total_pages,
                "successful_pages": successful_pages,
                "failed_pages": failed_pages,
                "success_rate": (
                    round(successful_pages / total_pages * 100, 2) if total_pages > 0 else 0
                ),
            },
        }

        if error:
            summary["error"] = error
            summary["status"] = "failed"
        else:
            summary["status"] = "completed"

        file_path = self.run_dir / "run.yaml"
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(
                summary, f, allow_unicode=True, sort_keys=False, default_flow_style=False
            )

        return file_path

    def write_exploration_graph(self, edges: List[Dict]) -> Path:
        """
        Write graph.yaml showing page relationships.

        Args:
            edges: List of edge records showing page links

        Returns:
            Path to the written file

        Edge format:
        {
            "from_page": "page-workspace-agents",
            "to_page": "page-agent-detail",
            "link_text": "View Details",
            "locator": "getByRole('link', { name: 'View Details' })"
        }
        """
        self.run_dir.mkdir(parents=True, exist_ok=True)

        graph = {
            "run_id": self.run_id,
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "edges": edges,
        }

        file_path = self.run_dir / "graph.yaml"
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(
                graph, f, allow_unicode=True, sort_keys=False, default_flow_style=False
            )

        return file_path

    def write_exploration_report(
        self,
        start_url: str,
        pages_explored: int,
        elements_found: int,
        issues: List[str],
        recommendations: List[str],
    ) -> Path:
        """
        Write report.md summarizing exploration results.

        Args:
            start_url: Starting URL
            pages_explored: Number of pages explored
            elements_found: Total number of elements found
            issues: List of issues encountered
            recommendations: List of recommendations

        Returns:
            Path to the written file
        """
        self.run_dir.mkdir(parents=True, exist_ok=True)

        report = f"""# Exploration Report

**Run ID**: {self.run_id}
**Project ID**: {self.project_id}
**Generated**: {datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")}

---

## Summary

- **Start URL**: {start_url}
- **Pages Explored**: {pages_explored}
- **Elements Found**: {elements_found}

---

## Issues

"""
        if issues:
            for i, issue in enumerate(issues, 1):
                report += f"{i}. {issue}\n"
        else:
            report += "No issues found.\n"

        report += "\n---\n\n## Recommendations\n\n"

        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                report += f"{i}. {rec}\n"
        else:
            report += "No recommendations.\n"

        report += "\n---\n\n*Generated by Page Exploration Agent*\n"

        file_path = self.run_dir / "report.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report)

        return file_path

    def create_logs_directory(self) -> Path:
        """Create logs directory for this run"""
        logs_dir = self.run_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir

    def create_screenshots_directory(self) -> Path:
        """Create screenshots directory for this run"""
        screenshots_dir = self.run_dir / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        return screenshots_dir
