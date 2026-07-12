from app.services.page_exploration.timeline_projection import _coerce_tool_output_dict


def test_snapshot_tool_output_accepts_langchain_content_blocks():
    output = [
        {
            "type": "text",
            "text": '{"url":"https://example.test/agentStore","title":"Agent Store","elements":[]}',
        }
    ]

    parsed = _coerce_tool_output_dict(output)

    assert parsed["url"] == "https://example.test/agentStore"
    assert parsed["title"] == "Agent Store"


def test_snapshot_tool_output_accepts_json_content_block():
    output = [
        {
            "type": "json",
            "json": {
                "url": "https://example.test/workspace",
                "title": "Workspace",
                "elements": [],
            },
        }
    ]

    parsed = _coerce_tool_output_dict(output)

    assert parsed["url"].endswith("/workspace")
