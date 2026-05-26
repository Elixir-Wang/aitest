from __future__ import annotations

import unittest

from app.schemas.requirement_merge import RequirementMergeSourceFile
from app.services.requirement_fragment_service import split_source_file


class RequirementFragmentServiceTest(unittest.TestCase):
    def test_split_source_file_preserves_structured_markdown_blocks(self):
        source_file = RequirementMergeSourceFile(
            mapping_id="docmap-abc123",
            original_filename="接口需求.md",
            markdown_content="""# 接口需求

## 状态查询

- 支持查询产品进入状态。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| product_code | string | 产品编码 |
| action | string | 前端动作 |

```mermaid
flowchart TD
  A["查询"] --> B["判断"]
```

```json
{
  "code": "SUCCESS"
}
```
""",
            conversion_status="success",
            mapping_status="pending_merge",
        )

        fragments = split_source_file(source_file)

        self.assertEqual([fragment.fragment_id for fragment in fragments], [
            "frag-abc123-00001",
            "frag-abc123-00002",
            "frag-abc123-00003",
            "frag-abc123-00004",
        ])
        self.assertEqual(fragments[0].heading_path, ["接口需求", "状态查询"])
        self.assertEqual(fragments[1].fragment_type, "interface")
        self.assertIn("| product_code | string | 产品编码 |", fragments[1].markdown_block)
        self.assertEqual(fragments[2].fragment_type, "state_flow")
        self.assertIn("```mermaid", fragments[2].markdown_block)
        self.assertEqual(fragments[3].fragment_type, "interface")
        self.assertIn('"code": "SUCCESS"', fragments[3].markdown_block)

    def test_split_source_file_keeps_fragment_ids_stable(self):
        source_file = RequirementMergeSourceFile(
            mapping_id="docmap-stable",
            original_filename="登录需求.md",
            markdown_content="# 登录\n\n- 支持账号登录\n- 支持短信登录\n",
            conversion_status="success",
            mapping_status="pending_merge",
        )

        first = split_source_file(source_file)
        second = split_source_file(source_file)

        self.assertEqual([item.fragment_id for item in first], [item.fragment_id for item in second])
        self.assertEqual([item.content_hash for item in first], [item.content_hash for item in second])


if __name__ == "__main__":
    unittest.main()
