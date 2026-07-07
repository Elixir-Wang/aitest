import io
import re
import uuid
import zipfile
from collections import defaultdict
from xml.etree import ElementTree as ET


CONTENT_NS = "urn:xmind:xmap:xmlns:content:2.0"
MANIFEST_NS = "urn:xmind:xmap:xmlns:manifest:1.0"

ET.register_namespace("", CONTENT_NS)


def build_test_case_set_xmind(test_case_set: dict, cases: list[dict]) -> bytes:
    root_title = str(test_case_set.get("name") or "").strip() or "测试用例集"
    content_xml = _build_content_xml(root_title, cases)
    manifest_xml = _build_manifest_xml()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("content.xml", content_xml)
        archive.writestr("META-INF/manifest.xml", manifest_xml)
    return buffer.getvalue()


def safe_xmind_filename(value: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', "_", value.strip()) or "test-cases"
    return f"{name}.xmind"


def _build_content_xml(root_title: str, cases: list[dict]) -> bytes:
    xmap_content = ET.Element(_content_tag("xmap-content"), {"version": "2.0"})
    sheet = ET.SubElement(xmap_content, _content_tag("sheet"), {"id": _topic_id()})
    ET.SubElement(sheet, _content_tag("title")).text = f"{root_title}测试用例"
    root_topic = _topic(root_title)
    sheet.append(root_topic)

    if cases:
        module_topics = [_module_topic(module_name, module_cases) for module_name, module_cases in _cases_by_module(cases)]
        _append_attached_topics(root_topic, module_topics)
    else:
        _append_attached_topics(root_topic, [_topic("暂无测试用例")])

    return ET.tostring(xmap_content, encoding="utf-8", xml_declaration=True)


def _build_manifest_xml() -> bytes:
    manifest = ET.Element(f"{{{MANIFEST_NS}}}manifest")
    ET.SubElement(manifest, f"{{{MANIFEST_NS}}}file-entry", {"full-path": "content.xml", "media-type": "text/xml"})
    return ET.tostring(manifest, encoding="utf-8", xml_declaration=True)


def _cases_by_module(cases: list[dict]) -> list[tuple[str, list[dict]]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    order = []
    for test_case in cases:
        module_name = str(test_case.get("module") or "").strip() or "未分组"
        if module_name not in grouped:
            order.append(module_name)
        grouped[module_name].append(test_case)
    return [(module_name, grouped[module_name]) for module_name in order]


def _module_topic(module_name: str, cases: list[dict]) -> ET.Element:
    module_topic = _topic(module_name)
    _append_attached_topics(module_topic, [_case_topic(test_case) for test_case in cases])
    return module_topic


def _case_topic(test_case: dict) -> ET.Element:
    priority = _priority_label(str(test_case.get("priority") or ""))
    title = str(test_case.get("title") or "").strip() or "未命名用例"
    case_topic = _topic(f"tc-{priority}: {title}")
    children = [_topic(f"pc: {str(test_case.get('preconditions') or '').strip() or '无'}")]
    steps = test_case.get("steps")
    if isinstance(steps, list) and steps:
        for index, step in enumerate(steps, start=1):
            action = _step_value(step, "action") or "未提供测试步骤"
            expected = _step_value(step, "expected_result") or str(test_case.get("expected_result") or "").strip() or "未提供预期结果"
            step_topic = _topic(f"步骤{index}: {action}")
            _append_attached_topics(step_topic, [_topic(f"结果{index}: {expected}")])
            children.append(step_topic)
    else:
        expected = str(test_case.get("expected_result") or "").strip() or "未提供预期结果"
        step_topic = _topic("步骤1: 未提供测试步骤")
        _append_attached_topics(step_topic, [_topic(f"结果1: {expected}")])
        children.append(step_topic)
    _append_attached_topics(case_topic, children)
    return case_topic


def _priority_label(value: str) -> str:
    normalized = value.strip().lower()
    return normalized or "p2"


def _step_value(step: object, key: str) -> str:
    if not isinstance(step, dict):
        return ""
    fallback_key = "step" if key == "action" else key
    return str(step.get(key) or step.get(fallback_key) or "").strip()


def _append_attached_topics(parent: ET.Element, topics: list[ET.Element]) -> None:
    children = ET.SubElement(parent, _content_tag("children"))
    attached = ET.SubElement(children, _content_tag("topics"), {"type": "attached"})
    for topic in topics:
        attached.append(topic)


def _topic(title: str) -> ET.Element:
    topic = ET.Element(_content_tag("topic"), {"id": _topic_id()})
    ET.SubElement(topic, _content_tag("title")).text = title
    return topic


def _topic_id() -> str:
    return f"t-{uuid.uuid4().hex}"


def _content_tag(name: str) -> str:
    return f"{{{CONTENT_NS}}}{name}"
