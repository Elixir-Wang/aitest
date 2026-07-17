import hashlib
from pathlib import Path


def pytest_requests_skill_fingerprint() -> str:
    digest = hashlib.sha256()
    skill_root = Path(__file__).parent / "skills" / "pytest-requests-code-generation"
    for path in sorted(skill_root.rglob("*.md")):
        digest.update(path.relative_to(skill_root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


__all__ = ["pytest_requests_skill_fingerprint"]
