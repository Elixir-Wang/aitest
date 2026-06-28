"""Exploration queue management

Manages URL queue and tracks explored URLs to avoid infinite loops.
"""

from collections import deque
from typing import Set, Optional, List
from urllib.parse import urlparse

from app.agents.page_exploration.utils.url_normalizer import normalize_url


class ExplorationQueue:
    """Manages exploration queue with loop prevention"""

    def __init__(self, start_url: str, scope: Optional[str] = None, max_depth: int = 3):
        """
        Initialize exploration queue.

        Args:
            start_url: Starting URL for exploration
            scope: URL scope (only explore URLs within this scope)
            max_depth: Maximum exploration depth (default: 3)
        """
        self.queue: deque = deque([(start_url, 0)])  # (url, depth)
        self.explored_in_this_run: Set[str] = set()
        self.scope = scope or self._extract_base_url(start_url)
        self.max_depth = max_depth

    def _extract_base_url(self, url: str) -> str:
        """Extract base URL (scheme + netloc) from full URL"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _in_scope(self, url: str) -> bool:
        """Check if URL is within exploration scope"""
        if not self.scope:
            return True
        return url.startswith(self.scope)

    def add_url(self, url: str, depth: int) -> bool:
        """
        Add URL to exploration queue.

        Args:
            url: URL to add
            depth: Depth level of this URL

        Returns:
            True if URL was added, False if skipped (already explored, out of scope, or max depth)
        """
        # Normalize URL for comparison
        normalized = normalize_url(url)

        # Skip if already explored in this run
        if normalized in self.explored_in_this_run:
            return False

        # Skip if exceeds max depth
        if depth > self.max_depth:
            return False

        # Skip if out of scope
        if not self._in_scope(url):
            return False

        # Skip if already in queue
        if any(normalize_url(queued_url) == normalized for queued_url, _ in self.queue):
            return False

        self.queue.append((url, depth))
        return True

    def pop(self) -> Optional[tuple[str, int]]:
        """
        Pop next URL from queue (FIFO - breadth-first).

        Returns:
            Tuple of (url, depth) or None if queue is empty
        """
        if self.is_empty():
            return None
        return self.queue.popleft()

    def mark_explored(self, url: str) -> None:
        """Mark URL as explored in this run"""
        normalized = normalize_url(url)
        self.explored_in_this_run.add(normalized)

    def is_empty(self) -> bool:
        """Check if queue is empty"""
        return len(self.queue) == 0

    def size(self) -> int:
        """Get current queue size"""
        return len(self.queue)

    def explored_count(self) -> int:
        """Get number of URLs explored in this run"""
        return len(self.explored_in_this_run)

    def is_explored(self, url: str) -> bool:
        """Check if URL was explored in this run"""
        normalized = normalize_url(url)
        return normalized in self.explored_in_this_run

    def get_explored_urls(self) -> List[str]:
        """Get list of all explored normalized URLs"""
        return list(self.explored_in_this_run)
