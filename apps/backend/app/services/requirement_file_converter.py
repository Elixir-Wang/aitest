from __future__ import annotations

from dataclasses import dataclass
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


@dataclass(frozen=True)
class ConvertedRequirementFile:
    markdown: str
    summary: str


def convert_requirement_file_to_markdown(filename: str, raw_bytes: bytes) -> tuple[str, str]:
    lowered = filename.lower()
    if lowered.endswith((".md", ".markdown", ".txt")):
        return _normalize_text_markdown(filename, raw_bytes), "文本文件直接保存为 Markdown 转换稿。"
    if lowered.endswith(".pdf"):
        converted = _convert_with_local_skill("pdf_to_markdown", filename, raw_bytes)
        return converted.markdown, converted.summary
    if lowered.endswith((".doc", ".docx")):
        converted = _convert_with_local_skill("docx_to_markdown", filename, raw_bytes)
        return converted.markdown, converted.summary
    preview = _decode_text(raw_bytes)[:4000]
    markdown = f"# {filename}\n\n暂不支持该文件类型的完整结构解析，已保存文本预览。\n\n```\n{preview}\n```\n"
    return markdown, "文件类型暂不支持完整解析，已生成文本预览。"


def _normalize_text_markdown(filename: str, raw_bytes: bytes) -> str:
    text = _decode_text(raw_bytes).strip()
    if filename.lower().endswith((".md", ".markdown")):
        return text + "\n"
    return f"# {filename}\n\n{text}\n"


def _convert_with_local_skill(skill_id: str, filename: str, raw_bytes: bytes) -> ConvertedRequirementFile:
    node = shutil.which("node")
    if not node:
        raise RuntimeError(f"无法转换 {filename}：缺少 Node.js，不能执行 {skill_id} skill。")

    convert_script = _find_skill_convert_script(skill_id)
    if convert_script is None:
        raise RuntimeError(f"无法转换 {filename}：缺少 {skill_id} skill 转换脚本。")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / Path(filename).name
        output_path = temp_path / f"{input_path.stem}.md"
        input_path.write_bytes(raw_bytes)
        completed = subprocess.run(
            [node, str(convert_script), "--input", str(input_path), "--output", str(output_path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(f"无法转换 {filename}：{skill_id} skill 执行失败。{detail}")
        if not output_path.exists():
            raise RuntimeError(f"无法转换 {filename}：{skill_id} skill 未生成 Markdown 输出。")
        markdown = output_path.read_text(encoding="utf-8").strip() + "\n"
        return ConvertedRequirementFile(markdown=markdown, summary=_conversion_summary_from_stdout(completed.stdout, skill_id))


def _find_skill_convert_script(skill_id: str) -> Path | None:
    path = (
        Path(__file__).parents[1]
        / "agents"
        / "raw_requirement_format_converter"
        / "skills"
        / skill_id
        / "scripts"
        / "convert.cjs"
    )
    return path if path.exists() else None


def _decode_text(raw_bytes: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="ignore")


def _conversion_summary_from_stdout(stdout: str, skill_id: str) -> str:
    for line in reversed([item.strip() for item in stdout.splitlines() if item.strip()]):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
        page_count = payload.get("pageCount") or payload.get("pages") or stats.get("pages")
        if page_count:
            return f"已通过 {skill_id} skill 转换，页数 {page_count}。"
        return f"已通过 {skill_id} skill 转换。"
    return f"已通过 {skill_id} skill 转换。"
