# Fix Docx Preview Format Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 docx 文件在"原始文件"和"标准文件"两个 Tab 中的格式错乱问题。

**Architecture:**
- 前端 `DocxPreview` 组件改用 `mammoth.convertToHtml()` 输出 HTML，利用已有的 `.markdown-preview` CSS 样式渲染，保留标题/列表/加粗等格式。
- 后端 `_convert_docx_to_markdown` 修复两个 bug：① 相邻列表项之间不应插入空行（改为 `\n` 连接），② 解析样式名中的缩进级别（`List Bullet 2` → 2 空格缩进）。

**Tech Stack:** Python / python-docx（后端）；TypeScript / React / mammoth.js（前端）；pytest（后端测试）

---

## 文件映射

| 操作 | 文件 |
|------|------|
| Modify | `apps/frontend/src/components/ai-testing/original-file-preview.tsx` |
| Modify | `apps/backend/app/services/requirement_file_converter.py` |
| Modify | `apps/backend/tests/test_requirement_file_converter.py` |

---

## Task 1：前端 DocxPreview — 改用 HTML 渲染保留格式

**Problem:** `mammoth.extractRawText()` 只提取纯文本，丢失所有格式，用 `<pre>` 渲染。

**Fix:** 改用 `mammoth.convertToHtml()`，输出 HTML，套用已有 `.markdown-preview` 样式类渲染。

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/original-file-preview.tsx:238-292`

- [ ] **Step 1: 写失败测试（人工验证）**

  打开浏览器访问任意 docx 文件的"原始文件"Tab，确认当前显示为无格式纯文本（标题、列表均丢失），截图记录 before。

- [ ] **Step 2: 修改 DocxPreview 组件**

  将 `apps/frontend/src/components/ai-testing/original-file-preview.tsx` 中的 `DocxPreview` 函数替换为：

  ```tsx
  function DocxPreview({ objectUrl, title }: { objectUrl: string; title: string }) {
    const [html, setHtml] = useState("");
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
      let cancelled = false;
      setLoading(true);
      setError("");
      setHtml("");

      fetch(objectUrl)
        .then((response) => response.arrayBuffer())
        .then((arrayBuffer) => mammoth.convertToHtml({ arrayBuffer }))
        .then((result) => {
          if (!cancelled) {
            setHtml(result.value);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setError("Word 文件预览加载失败");
          }
        })
        .finally(() => {
          if (!cancelled) {
            setLoading(false);
          }
        });

      return () => {
        cancelled = true;
      };
    }, [objectUrl]);

    return (
      <div className="overflow-hidden rounded-lg border bg-background">
        <div className="border-b bg-muted/20 px-3 py-2 font-medium text-sm">{displayFilename(title)}</div>
        <div className="min-h-[680px] bg-muted/30 p-6">
          <article className="mx-auto min-h-[620px] max-w-4xl bg-white px-12 py-10 shadow-sm ring-1 ring-border">
            {loading ? (
              <div className="flex items-center gap-2 text-muted-foreground text-sm">
                <Loader2 className="size-4 animate-spin" />
                加载中
              </div>
            ) : error ? (
              <div className="text-muted-foreground text-sm">{error}</div>
            ) : (
              <div
                className="markdown-preview border-0 bg-transparent shadow-none"
                dangerouslySetInnerHTML={{ __html: html || "<p>文档暂无可预览内容。</p>" }}
              />
            )}
          </article>
        </div>
      </div>
    );
  }
  ```

  注意：`mammoth` 的导入行不需要变动（`import mammoth from "mammoth"` 已存在）。

- [ ] **Step 3: 验证前端渲染正常**

  启动前端开发服务器（若未启动），访问 docx 文件的"原始文件"Tab：
  - 标题 → 渲染为 h1/h2/h3
  - 列表 → 渲染为 ul/ol
  - 加粗 → 渲染为 bold
  - 表格 → 渲染为 table

- [ ] **Step 4: Commit**

  ```bash
  git add apps/frontend/src/components/ai-testing/original-file-preview.tsx
  git commit -m "fix: use mammoth.convertToHtml for docx preview to preserve formatting"
  ```

---

## Task 2：后端 — 修复相邻列表项被空行切断

**Problem:** `"\n\n".join(blocks)` 在所有块之间插入空行，导致相邻列表项形成"松散列表"（每项间距过大），视觉与原文差异明显。

**Fix:** 提取 `_join_markdown_blocks()` 函数，检测相邻列表项，组内用 `\n` 连接，组间用 `\n\n` 连接。

**Files:**
- Modify: `apps/backend/app/services/requirement_file_converter.py`
- Modify: `apps/backend/tests/test_requirement_file_converter.py`

- [ ] **Step 1: 写失败测试**

  在 `apps/backend/tests/test_requirement_file_converter.py` 的 `RequirementFileConverterTest` 类末尾添加：

  ```python
  def test_docx_adjacent_list_items_are_not_separated_by_blank_lines(self):
      document = Document()
      document.add_paragraph("支持账号登录", style="List Bullet")
      document.add_paragraph("支持手机登录", style="List Bullet")
      document.add_paragraph("支持微信登录", style="List Bullet")
      buffer = BytesIO()
      document.save(buffer)

      markdown, _ = convert_requirement_file_to_markdown("列表.docx", buffer.getvalue())

      # 三个列表项之间不应有空行（紧凑列表）
      self.assertIn("- 支持账号登录\n- 支持手机登录\n- 支持微信登录", markdown)

  def test_docx_numbered_list_items_are_not_separated_by_blank_lines(self):
      document = Document()
      document.add_paragraph("输入账号", style="List Number")
      document.add_paragraph("输入密码", style="List Number")
      document.add_paragraph("点击登录", style="List Number")
      buffer = BytesIO()
      document.save(buffer)

      markdown, _ = convert_requirement_file_to_markdown("编号.docx", buffer.getvalue())

      self.assertIn("1. 输入账号\n1. 输入密码\n1. 点击登录", markdown)
  ```

- [ ] **Step 2: 运行测试确认失败**

  ```bash
  cd apps/backend
  python -m pytest tests/test_requirement_file_converter.py::RequirementFileConverterTest::test_docx_adjacent_list_items_are_not_separated_by_blank_lines -v
  ```

  期望：**FAIL** — `AssertionError`（实际输出中列表项之间有 `\n\n`）

- [ ] **Step 3: 实现 `_join_markdown_blocks` 和 `_is_list_block`**

  在 `apps/backend/app/services/requirement_file_converter.py` 末尾（`_decode_text` 函数之前）添加：

  ```python
  def _is_list_block(block: str) -> bool:
      """Return True if block is a markdown list item (possibly indented)."""
      return bool(re.match(r"^\s*(?:[-*+]|\d+\.)\s", block))


  def _join_markdown_blocks(blocks: list[str]) -> str:
      """Join blocks with double newlines, but keep consecutive list items tight (single newline)."""
      if not blocks:
          return ""
      groups: list[str] = []
      i = 0
      while i < len(blocks):
          block = blocks[i]
          if _is_list_block(block):
              list_items = [block]
              while i + 1 < len(blocks) and _is_list_block(blocks[i + 1]):
                  i += 1
                  list_items.append(blocks[i])
              groups.append("\n".join(list_items))
          else:
              groups.append(block)
          i += 1
      return "\n\n".join(groups)
  ```

- [ ] **Step 4: 替换 `_convert_docx_to_markdown` 中的 join 调用**

  找到 `_convert_docx_to_markdown` 函数中的这一行：

  ```python
      markdown = "\n\n".join(blocks) + "\n"
  ```

  替换为：

  ```python
      markdown = _join_markdown_blocks(blocks) + "\n"
  ```

- [ ] **Step 5: 运行全部 docx 相关测试确认通过**

  ```bash
  cd apps/backend
  python -m pytest tests/test_requirement_file_converter.py -v -k "docx"
  ```

  期望：全部 **PASS**

- [ ] **Step 6: Commit**

  ```bash
  git add apps/backend/app/services/requirement_file_converter.py \
          apps/backend/tests/test_requirement_file_converter.py
  git commit -m "fix: group adjacent list items to avoid loose markdown lists in docx conversion"
  ```

---

## Task 3：后端 — 修复列表嵌套缩进

**Problem:** `_paragraph_to_markdown` 对所有列表层级都输出同一级别（`- content`、`1. content`），不处理 Word 中的"List Bullet 2"/"List Number 2"等多级样式，导致嵌套列表全部扁平化。

**Fix:** 解析样式名末尾数字作为层级，生成对应数量的前置空格（每级 2 个空格）。

**Files:**
- Modify: `apps/backend/app/services/requirement_file_converter.py`
- Modify: `apps/backend/tests/test_requirement_file_converter.py`

- [ ] **Step 1: 写失败测试**

  在测试类末尾添加：

  ```python
  def test_docx_nested_bullet_list_is_indented(self):
      document = Document()
      document.add_paragraph("父级项", style="List Bullet")
      document.add_paragraph("子级项A", style="List Bullet 2")
      document.add_paragraph("子级项B", style="List Bullet 2")
      document.add_paragraph("另一父级", style="List Bullet")
      buffer = BytesIO()
      document.save(buffer)

      markdown, _ = convert_requirement_file_to_markdown("嵌套.docx", buffer.getvalue())

      self.assertIn("- 父级项", markdown)
      self.assertIn("  - 子级项A", markdown)
      self.assertIn("  - 子级项B", markdown)
      self.assertIn("- 另一父级", markdown)

  def test_docx_nested_numbered_list_is_indented(self):
      document = Document()
      document.add_paragraph("步骤一", style="List Number")
      document.add_paragraph("步骤一子步骤", style="List Number 2")
      document.add_paragraph("步骤二", style="List Number")
      buffer = BytesIO()
      document.save(buffer)

      markdown, _ = convert_requirement_file_to_markdown("嵌套编号.docx", buffer.getvalue())

      self.assertIn("1. 步骤一", markdown)
      self.assertIn("  1. 步骤一子步骤", markdown)
      self.assertIn("1. 步骤二", markdown)
  ```

- [ ] **Step 2: 运行测试确认失败**

  ```bash
  cd apps/backend
  python -m pytest tests/test_requirement_file_converter.py::RequirementFileConverterTest::test_docx_nested_bullet_list_is_indented -v
  ```

  期望：**FAIL**（实际输出 `- 子级项A` 而非 `  - 子级项A`）

- [ ] **Step 3: 添加 `_list_indent_level` 辅助函数**

  在 `requirement_file_converter.py` 中，在 `_is_bullet_list` 函数之前添加：

  ```python
  def _list_indent_level(style_name: str) -> int:
      """Return 0-based indentation level from style name.

      'List Bullet' -> 0, 'List Bullet 2' -> 1, 'List Bullet 3' -> 2.
      """
      match = re.search(r"\s+(\d+)$", style_name)
      if match:
          return max(0, int(match.group(1)) - 1)
      return 0
  ```

- [ ] **Step 4: 修改 `_paragraph_to_markdown` 使用缩进级别**

  找到 `_paragraph_to_markdown` 中的这两段：

  ```python
      if _is_numbered_list(style_name):
          return f"1. {content}"
      if _is_bullet_list(style_name):
          return f"- {content}"
  ```

  替换为：

  ```python
      if _is_numbered_list(style_name):
          indent = "  " * _list_indent_level(style_name)
          return f"{indent}1. {content}"
      if _is_bullet_list(style_name):
          indent = "  " * _list_indent_level(style_name)
          return f"{indent}- {content}"
  ```

- [ ] **Step 5: 运行全部测试确认通过**

  ```bash
  cd apps/backend
  python -m pytest tests/test_requirement_file_converter.py -v
  ```

  期望：全部 **PASS**

- [ ] **Step 6: Commit**

  ```bash
  git add apps/backend/app/services/requirement_file_converter.py \
          apps/backend/tests/test_requirement_file_converter.py
  git commit -m "fix: support nested list indentation in docx-to-markdown conversion"
  ```

---

## 自检

### Spec 覆盖
- [x] 前端原始文件 Tab docx 格式丢失 → Task 1 修复
- [x] 后端列表项之间多余空行 → Task 2 修复
- [x] 后端列表嵌套/缩进丢失 → Task 3 修复

### 类型一致性
- `_list_indent_level(style_name: str) -> int` 在 Task 3 中定义并在同一函数中使用，无跨任务引用风险。
- `_join_markdown_blocks(blocks: list[str]) -> str` 在 Task 2 中定义，替换同文件内一处调用。
- `_is_list_block(block: str) -> bool` 在 Task 2 中定义，仅被 `_join_markdown_blocks` 调用。

### 无占位符检查 ✓
所有步骤均包含完整代码，无 TBD/TODO。
