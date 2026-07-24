import re


CATEGORIES = {"功能", "异常", "边界", "权限", "数据", "状态", "性能", "安全", "兼容性"}
PRIORITIES = {"P0", "P1", "P2", "P3"}
SECTION_NAMES = ("描述", "前置条件", "验证点", "来源引用", "备注")
POINT_HEADING = re.compile(r"^### \[([^\]]+)]\s+(.+)$", re.MULTILINE)


def serialize_test_points(points: list[dict]) -> str:
    blocks = ["# 测试点"]
    for point in points:
        blocks.append(_serialize_point(point))
    return "\n\n".join(blocks).rstrip() + "\n"


def parse_test_points(markdown_content: str) -> list[dict]:
    content = markdown_content.replace("\r\n", "\n").replace("\r", "\n").strip()
    matches = list(POINT_HEADING.finditer(content))
    if not matches:
        if content in {"", "# 测试点"}:
            return []
        raise ValueError("测试点 Markdown 中未找到测试点标题。")

    points: list[dict] = []
    point_keys: set[str] = set()
    titles: set[str] = set()
    for index, match in enumerate(matches):
        point_key = match.group(1).strip()
        title = match.group(2).strip()
        if not point_key:
            raise ValueError("测试点 point_key 不能为空。")
        if point_key in point_keys:
            raise ValueError(f"point_key 重复: {point_key}")
        point_keys.add(point_key)
        if not title:
            raise ValueError(f"{point_key} 缺少标题")
        title_identity = _title_identity(title)
        if title_identity in titles:
            raise ValueError(f"测试点标题重复: {title}")
        titles.add(title_identity)

        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        body = content[match.end() : body_end].strip()
        body = re.sub(r"\n---\s*$", "", body).strip()
        fields, sections = _parse_body(point_key, body)
        category = fields.get("类型", "")
        priority = fields.get("优先级", "")
        if category not in CATEGORIES:
            raise ValueError(f"{point_key} 的类型无效: {category}")
        if priority not in PRIORITIES:
            raise ValueError(f"{point_key} 的优先级无效: {priority}")

        description = _plain_section(sections.get("描述", ""))
        verification_points = _list_section(sections.get("验证点", ""))
        if not description:
            raise ValueError(f"{point_key} 缺少描述")
        if not verification_points:
            raise ValueError(f"{point_key} 缺少验证点")

        # 来源引用可以从表格字段 "来源" 或独立的 "来源引用" 章节获取
        source_refs = [r for r in _list_section(sections.get("来源引用", "")) if r != "无"]
        source_table = fields.get("来源", "")
        if source_table and source_table != "无":
            # 将表格中的来源字段转为 source_refs 条目
            table_refs = [r.strip() for r in source_table.split(",") if r.strip() and r.strip() != "无"]
            # 合并去重
            seen = set(source_refs)
            for ref in table_refs:
                if ref not in seen:
                    source_refs.append(ref)
                    seen.add(ref)

        points.append(
            {
                "point_key": point_key,
                "title": title,
                "module": fields.get("模块", ""),
                "category": category,
                "priority": priority,
                "description": description,
                "preconditions": _list_section(sections.get("前置条件", "")),
                "verification_points": verification_points,
                "source_refs": source_refs,
                "notes": _plain_section(sections.get("备注", "")),
            }
        )
    return points


def _serialize_point(point: dict) -> str:
    # 构建来源引用字符串
    source_refs = point.get("source_refs", [])
    source_refs_str = ", ".join(str(r).strip() for r in source_refs if str(r).strip())

    return "\n".join(
        [
            f"### [{str(point['point_key']).strip()}] {str(point['title']).strip()}",
            "",
            "| 字段 | 内容 |",
            "| --- | --- |",
            f"| 模块 | {_table_value(point.get('module', ''))} |",
            f"| 类型 | {_table_value(point.get('category', ''))} |",
            f"| 优先级 | {_table_value(point.get('priority', ''))} |",
            f"| 来源 | {_table_value(source_refs_str) if source_refs_str else '无'} |",
            "",
            "**描述**",
            "",
            _plain_value(point.get("description", "")),
            "",
            "**前置条件**",
            "",
            _list_value(point.get("preconditions", [])),
            "",
            "**验证点**",
            "",
            _list_value(point.get("verification_points", [])),
            "",
            "**来源引用**",
            "",
            _list_value(source_refs),
            "",
            "**备注**",
            "",
            _plain_value(point.get("notes", "")),
            "",
            "---",
        ]
    )


def _parse_body(point_key: str, body: str) -> tuple[dict[str, str], dict[str, str]]:
    fields: dict[str, str] = {}
    sections: dict[str, str] = {}
    current_section = ""
    section_lines: list[str] = []

    def flush_section() -> None:
        if current_section:
            sections[current_section] = "\n".join(section_lines).strip()

    for line in body.splitlines():
        stripped = line.strip()
        if stripped in {f"**{name}**" for name in SECTION_NAMES}:
            flush_section()
            current_section = stripped[2:-2]
            section_lines = []
            continue
        if current_section:
            section_lines.append(line)
            continue
        table_match = re.match(r"^\|\s*(模块|类型|优先级|来源)\s*\|\s*(.*?)\s*\|$", stripped)
        if table_match:
            fields[table_match.group(1)] = _unescape_table_value(table_match.group(2).strip())
    flush_section()

    missing_fields = [name for name in ("模块", "类型", "优先级") if name not in fields]
    if missing_fields:
        raise ValueError(f"{point_key} 缺少字段: {', '.join(missing_fields)}")
    missing_sections = [name for name in SECTION_NAMES if name not in sections]
    if missing_sections:
        raise ValueError(f"{point_key} 缺少章节: {', '.join(missing_sections)}")
    return fields, sections


def _table_value(value: object) -> str:
    text = str(value or "").strip().replace("\n", " ")
    return text.replace("|", "\\|")


def _unescape_table_value(value: str) -> str:
    return value.replace("\\|", "|").strip()


def _plain_value(value: object) -> str:
    text = str(value or "").strip()
    return text or "无"


def _plain_section(value: str) -> str:
    text = value.strip()
    return "" if text == "无" else text


def _list_value(values: object) -> str:
    items = [str(item).strip().replace("\n", " ") for item in values or [] if str(item).strip()]
    return "\n".join(f"- {item}" for item in items) if items else "无"


def _list_section(value: str) -> list[str]:
    text = value.strip()
    if not text or text == "无":
        return []
    items = [line.strip()[2:].strip() for line in text.splitlines() if line.strip().startswith("- ")]
    return [item for item in items if item]


def _title_identity(title: str) -> str:
    return " ".join(title.split()).casefold()


__all__ = ["parse_test_points", "serialize_test_points"]
