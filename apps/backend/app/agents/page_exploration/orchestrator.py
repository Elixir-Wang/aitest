"""Exploration orchestrator

Orchestrates the page exploration process:
- Manages exploration queue
- Coordinates tools execution
- Handles termination conditions
- Generates artifacts
"""

from typing import Optional, Dict, List
from datetime import datetime, UTC
import time

from app.agents.page_exploration.exploration_queue import ExplorationQueue
from app.agents.page_exploration.artifact_service import ArtifactService
from app.agents.page_exploration.services.explored_urls_service import ExploredUrlsService
from app.agents.page_exploration.utils.url_normalizer import normalize_url


class ExplorationOrchestrator:
    """Orchestrates page exploration workflow"""

    def __init__(
        self,
        project_id: str,
        run_id: str,
        start_url: str,
        scope: Optional[str] = None,
        max_depth: int = 3,
        max_pages: int = 50,
        max_duration_seconds: int = 3600,
    ):
        """
        Initialize exploration orchestrator.

        Args:
            project_id: Project identifier
            run_id: Run identifier
            start_url: Starting URL for exploration
            scope: URL scope (only explore URLs within this scope)
            max_depth: Maximum exploration depth (default: 3)
            max_pages: Maximum number of pages to explore (default: 50)
            max_duration_seconds: Maximum exploration duration in seconds (default: 3600)
        """
        self.project_id = project_id
        self.run_id = run_id
        self.start_url = start_url
        self.scope = scope
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.max_duration_seconds = max_duration_seconds

        # Services
        self.queue = ExplorationQueue(start_url, scope, max_depth)
        self.artifact_service = ArtifactService(project_id, run_id)
        self.explored_urls_service = ExploredUrlsService(project_id)

        # State tracking
        self.start_time: Optional[float] = None
        self.discovered_pages: List[Dict] = []
        self.graph_edges: List[Dict] = []
        self.issues: List[str] = []
        self.current_page_id: Optional[str] = None

    def should_continue(self) -> tuple[bool, Optional[str]]:
        """
        Check if exploration should continue.

        Returns:
            Tuple of (should_continue, stop_reason)
        """
        # Check if queue is empty
        if self.queue.is_empty():
            return False, "all_pages_explored"

        # Check max pages limit
        if self.queue.explored_count() >= self.max_pages:
            return False, "max_pages_reached"

        # Check max duration
        if self.start_time:
            elapsed = time.time() - self.start_time
            if elapsed >= self.max_duration_seconds:
                return False, "max_duration_reached"

        # Check consecutive failures (if tracking)
        # TODO: implement consecutive failure tracking

        return True, None

    def start_exploration(self) -> None:
        """Mark exploration start time"""
        self.start_time = time.time()

    def get_next_url(self) -> Optional[tuple[str, int]]:
        """
        Get next URL to explore from queue.

        Returns:
            Tuple of (url, depth) or None if queue is empty
        """
        return self.queue.pop()

    def mark_page_explored(self, url: str) -> None:
        """Mark a page as explored in this run"""
        self.queue.mark_explored(url)

    def is_already_explored(self, url: str) -> bool:
        """Check if URL was already explored in this run"""
        return self.queue.is_explored(url)

    def add_discovered_links(self, current_url: str, links: List[Dict], current_depth: int) -> int:
        """
        Add discovered links to exploration queue.

        Args:
            current_url: Current page URL
            links: List of link dictionaries with 'url', 'text', 'locator'
            current_depth: Current page depth

        Returns:
            Number of links added to queue
        """
        added_count = 0
        next_depth = current_depth + 1

        for link in links:
            link_url = link.get("url")
            if not link_url:
                continue

            # Add to queue (will be filtered by scope, depth, and duplicates)
            if self.queue.add_url(link_url, next_depth):
                added_count += 1

                # Record graph edge
                self.graph_edges.append({
                    "from_page": self.current_page_id or "unknown",
                    "to_page": f"page-{normalize_url(link_url).strip('/').replace('/', '-')}",
                    "link_text": link.get("text", ""),
                    "locator": link.get("locator", ""),
                })

        return added_count

    def add_discovered_page(
        self,
        page_id: str,
        page_file: str,
        normalized_path: str,
        status: str,
        elements_count: int,
        exploration_status: str = "completed",
    ) -> None:
        """
        Add a discovered page record.

        Args:
            page_id: Page identifier
            page_file: Relative path to page artifact file
            normalized_path: Normalized URL path
            status: "new" or "updated"
            elements_count: Number of elements found
            exploration_status: "completed" or "failed"
        """
        self.discovered_pages.append({
            "page_id": page_id,
            "page_file": page_file,
            "normalized_path": normalized_path,
            "status": status,
            "elements_count": elements_count,
            "exploration_status": exploration_status,
        })

        # Update current page ID for graph edges
        self.current_page_id = page_id

    def add_issue(self, issue: str) -> None:
        """Add an issue encountered during exploration"""
        self.issues.append(issue)

    def finalize_exploration(self) -> Dict:
        """
        Finalize exploration and generate artifacts.

        Returns:
            Dictionary with artifact paths and statistics
        """
        if not self.start_time:
            raise RuntimeError("Exploration not started")

        end_time = time.time()
        duration = end_time - self.start_time
        end_timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        # Count successful and failed pages
        successful_pages = sum(
            1 for p in self.discovered_pages if p["exploration_status"] == "completed"
        )
        failed_pages = sum(
            1 for p in self.discovered_pages if p["exploration_status"] == "failed"
        )

        # Write discovered_pages.yaml
        discovered_pages_path = self.artifact_service.write_discovered_pages(
            self.discovered_pages
        )

        # Write run.yaml summary
        run_summary_path = self.artifact_service.write_run_summary(
            start_url=self.start_url,
            total_pages=len(self.discovered_pages),
            successful_pages=successful_pages,
            failed_pages=failed_pages,
            start_time=datetime.fromtimestamp(self.start_time, UTC).isoformat().replace("+00:00", "Z"),
            end_time=end_timestamp,
            duration_seconds=round(duration, 2),
        )

        # Write graph.yaml if we have edges
        graph_path = None
        if self.graph_edges:
            graph_path = self.artifact_service.write_exploration_graph(self.graph_edges)

        # Write report.md
        elements_found = sum(p["elements_count"] for p in self.discovered_pages)
        recommendations = self._generate_recommendations()

        report_path = self.artifact_service.write_exploration_report(
            start_url=self.start_url,
            pages_explored=len(self.discovered_pages),
            elements_found=elements_found,
            issues=self.issues,
            recommendations=recommendations,
        )

        return {
            "run_id": self.run_id,
            "duration_seconds": round(duration, 2),
            "pages_discovered": len(self.discovered_pages),
            "successful_pages": successful_pages,
            "failed_pages": failed_pages,
            "elements_found": elements_found,
            "artifacts": {
                "discovered_pages": str(discovered_pages_path),
                "run_summary": str(run_summary_path),
                "graph": str(graph_path) if graph_path else None,
                "report": str(report_path),
            },
        }

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on exploration results"""
        recommendations = []

        # Check if we hit limits
        if self.queue.explored_count() >= self.max_pages:
            recommendations.append(
                f"Exploration stopped after reaching max_pages limit ({self.max_pages}). "
                "Consider increasing the limit to explore more pages."
            )

        # Check depth
        if self.max_depth < 3:
            recommendations.append(
                f"Current max_depth is {self.max_depth}. "
                "Consider increasing it to explore deeper page hierarchies."
            )

        # Check for failed pages
        failed_count = sum(
            1 for p in self.discovered_pages if p["exploration_status"] == "failed"
        )
        if failed_count > 0:
            recommendations.append(
                f"Found {failed_count} failed page(s). Review logs to understand failures."
            )

        # Check for pages with few elements
        pages_with_few_elements = sum(
            1 for p in self.discovered_pages if p["elements_count"] < 3
        )
        if pages_with_few_elements > len(self.discovered_pages) * 0.3:
            recommendations.append(
                "Many pages have very few elements. This might indicate "
                "authentication issues or pages that require JavaScript."
            )

        if not recommendations:
            recommendations.append("Exploration completed successfully with no issues.")

        return recommendations

    def get_statistics(self) -> Dict:
        """Get current exploration statistics"""
        return {
            "queue_size": self.queue.size(),
            "explored_count": self.queue.explored_count(),
            "discovered_pages": len(self.discovered_pages),
            "issues_count": len(self.issues),
            "elapsed_seconds": round(time.time() - self.start_time, 2) if self.start_time else 0,
        }
