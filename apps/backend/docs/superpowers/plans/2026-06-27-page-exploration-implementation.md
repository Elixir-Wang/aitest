# 页面探索功能实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现基于 Playwright CLI + LangChain 的智能页面探索功能，自动探索网站页面并生成可复用的元素定位器快照

**Architecture:** 
- Frontend (React) → FastAPI Service → LangChain Agent → Playwright CLI Wrapper → playwright-cli (Node.js)
- Agent 使用 Skills 机制加载领域知识（已完成）
- 无缓存机制，重复探索覆盖更新产物
- 项目级 pages 产物，explored_urls.yaml 仅用于循环检测

**Tech Stack:** 
- Backend: Python 3.11+, FastAPI, LangChain, Playwright CLI
- Frontend: React, TypeScript, Ant Design
- Storage: YAML 文件系统
- Real-time: SSE (Server-Sent Events)

## Global Constraints

- Python >= 3.11
- LangChain >= 0.3.0
- playwright-cli 需全局安装或通过 npm 可访问
- 所有定位器必须是语义定位器，禁止使用 ref
- URL 归一化：提取 path，去除 query/fragment，转小写，去尾部斜杠（除根路径）
- explored_urls.yaml 仅记录历史，不阻止重复探索
- 重复探索会覆盖更新 pages 产物
- 所有 YAML 文件使用 UTF-8 编码

---

## 实施概览

### 已完成 ✅
- Skills 加载机制（SkillsLoader + SkillsMiddleware）
- 2个 SKILL.md 文件（locator_best_practices + page_explorer）
- Agent Factory（agent.py）
- 基础 System Prompt

### 待实施（6个阶段）

**阶段 1**: Playwright CLI Wrapper + 基础工具类（3-4天）
**阶段 2**: LangChain Agent Tools（2-3天）
**阶段 3**: 探索编排器 + 产物服务（3-4天）
**阶段 4**: FastAPI Service + SSE（2-3天）
**阶段 5**: 前端页面管理界面（3-4天）
**阶段 6**: 集成测试 + 文档（2-3天）

**总计**: 约 15-21 个工作日

---

## 阶段 1: Playwright CLI Wrapper + 基础工具类

### Task 1.1: URL 归一化工具

**Files:**
- Create: `app/agents/page_exploration/utils/url_normalizer.py`
- Test: `tests/agents/page_exploration/utils/test_url_normalizer.py`

**Interfaces:**
- Produces: `normalize_url(url: str) -> str`

- [ ] **Step 1: 写失败测试**

```python
# tests/agents/page_exploration/utils/test_url_normalizer.py
import pytest
from app.agents.page_exploration.utils.url_normalizer import normalize_url


def test_normalize_url_extracts_path():
    """测试提取域名后的路径"""
    assert normalize_url("https://test.example.com/workspace/agents") == "/workspace/agents"
    assert normalize_url("https://prod.example.com/workspace/agents") == "/workspace/agents"


def test_normalize_url_removes_trailing_slash():
    """测试去除尾部斜杠"""
    assert normalize_url("https://test.com/workspace/agents/") == "/workspace/agents"
    assert normalize_url("https://test.com/workspace/") == "/workspace"
    
    # 保留根路径的斜杠
    assert normalize_url("https://test.com/") == "/"


def test_normalize_url_removes_query_and_fragment():
    """测试去除 query 和 fragment"""
    assert normalize_url("https://test.com/workspace?tab=all") == "/workspace"
    assert normalize_url("https://test.com/workspace#section1") == "/workspace"
    assert normalize_url("https://test.com/workspace?tab=all#section1") == "/workspace"


def test_normalize_url_decodes_percent_encoding():
    """测试 URL 解码"""
    assert normalize_url("https://test.com/workspace%20agents") == "/workspace agents"
    assert normalize_url("https://test.com/%E6%99%BA%E8%83%BD%E4%BD%93") == "/智能体"


def test_normalize_url_converts_to_lowercase():
    """测试转小写"""
    assert normalize_url("https://test.com/Workspace/Agents") == "/workspace/agents"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
pytest tests/agents/page_exploration/utils/test_url_normalizer.py -v
```

预期: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现 URL 归一化**

```python
# app/agents/page_exploration/utils/url_normalizer.py
"""
URL 归一化工具

用于跨环境 URL 归一化，支持缓存复用
"""
from urllib.parse import urlparse, unquote


def normalize_url(url: str) -> str:
    """
    归一化 URL 到统一格式
    
    规则:
    1. 提取 path（域名后面的部分）
    2. 去除 query 参数（?后面的）
    3. 去除 fragment（#后面的）
    4. URL 解码（%20 → 空格）
    5. 去除尾部斜杠（保留根路径的"/"）
    6. 转小写
    
    Args:
        url: 完整 URL
        
    Returns:
        归一化后的路径
        
    Examples:
        >>> normalize_url("https://test.example.com/workspace/agents")
        '/workspace/agents'
        >>> normalize_url("https://prod.example.com/workspace/agents?tab=all")
        '/workspace/agents'
        >>> normalize_url("https://test.com/workspace/")
        '/workspace'
    """
    parsed = urlparse(url)
    path = unquote(parsed.path)
    
    # 去除尾部斜杠（保留根路径的"/"）
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    
    return path.lower()
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/agents/page_exploration/utils/test_url_normalizer.py -v
```

预期: ALL PASS

- [ ] **Step 5: 添加 __init__.py**

```python
# app/agents/page_exploration/utils/__init__.py
from app.agents.page_exploration.utils.url_normalizer import normalize_url

__all__ = ["normalize_url"]
```

- [ ] **Step 6: 提交**

```bash
git add app/agents/page_exploration/utils/ tests/agents/page_exploration/utils/
git commit -m "feat: add URL normalizer for cross-environment support

- Extract path from full URL
- Remove query params and fragments
- URL decode and lowercase
- Remove trailing slashes (preserve root)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1.2: Playwright CLI Wrapper

**Files:**
- Create: `app/agents/page_exploration/playwright/cli_wrapper.py`
- Create: `app/agents/page_exploration/playwright/schemas.py`
- Test: `tests/agents/page_exploration/playwright/test_cli_wrapper.py`

**Interfaces:**
- Produces: 
  - `PlaywrightCLI.snap(url: str) -> SnapshotResult`
  - `PlaywrightCLI.navigate(url: str) -> NavigateResult`
  - `PlaywrightCLI.click(locator: str) -> ClickResult`
  - `PlaywrightCLI.fill(locator: str, value: str) -> FillResult`

- [ ] **Step 1: 定义 Schemas**

```python
# app/agents/page_exploration/playwright/schemas.py
"""
Playwright CLI 输出 Schemas
"""
from typing import List, Optional
from pydantic import BaseModel


class ElementInfo(BaseModel):
    """元素信息"""
    ref: str  # 临时引用（e15, e20 等）
    role: str  # 角色（button, link, textbox 等）
    name: Optional[str] = None  # 名称
    text: Optional[str] = None  # 文本内容
    visible: bool = True  # 是否可见


class SnapshotResult(BaseModel):
    """快照结果"""
    url: str
    title: str
    elements: List[ElementInfo]
    raw_output: str  # playwright-cli 原始输出


class NavigateResult(BaseModel):
    """导航结果"""
    url: str
    success: bool
    error: Optional[str] = None


class ClickResult(BaseModel):
    """点击结果"""
    success: bool
    error: Optional[str] = None


class FillResult(BaseModel):
    """填写结果"""
    success: bool
    error: Optional[str] = None
```

- [ ] **Step 2: 写失败测试（Mock playwright-cli）**

```python
# tests/agents/page_exploration/playwright/test_cli_wrapper.py
import pytest
from unittest.mock import Mock, patch
from app.agents.page_exploration.playwright.cli_wrapper import PlaywrightCLI
from app.agents.page_exploration.playwright.schemas import SnapshotResult


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run"""
    with patch('subprocess.run') as mock:
        yield mock


def test_snap_success(mock_subprocess):
    """测试成功获取快照"""
    # Mock playwright-cli snap 输出
    mock_output = """
    url: https://test.com/workspace
    title: 智能体工作台
    elements:
      - ref: e15
        role: button
        name: 创建智能体
        visible: true
      - ref: e20
        role: link
        name: 返回
        visible: true
    """
    
    mock_subprocess.return_value = Mock(
        returncode=0,
        stdout=mock_output,
        stderr=""
    )
    
    cli = PlaywrightCLI()
    result = cli.snap("https://test.com/workspace")
    
    assert isinstance(result, SnapshotResult)
    assert result.url == "https://test.com/workspace"
    assert result.title == "智能体工作台"
    assert len(result.elements) == 2
    assert result.elements[0].ref == "e15"
    assert result.elements[0].role == "button"


def test_snap_timeout(mock_subprocess):
    """测试快照超时"""
    mock_subprocess.side_effect = TimeoutError("Command timed out")
    
    cli = PlaywrightCLI()
    
    with pytest.raises(TimeoutError):
        cli.snap("https://test.com/slow-page")


def test_navigate_success(mock_subprocess):
    """测试成功导航"""
    mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
    
    cli = PlaywrightCLI()
    result = cli.navigate("https://test.com/workspace")
    
    assert result.success is True
    assert result.url == "https://test.com/workspace"


def test_click_element(mock_subprocess):
    """测试点击元素"""
    mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
    
    cli = PlaywrightCLI()
    result = cli.click("getByRole('button', { name: '创建智能体' })")
    
    assert result.success is True
```

- [ ] **Step 3: 运行测试验证失败**

```bash
pytest tests/agents/page_exploration/playwright/test_cli_wrapper.py -v
```

预期: FAIL - ModuleNotFoundError

- [ ] **Step 4: 实现 PlaywrightCLI Wrapper**

```python
# app/agents/page_exploration/playwright/cli_wrapper.py
"""
Playwright CLI Wrapper

通过 subprocess 调用 playwright-cli 命令
"""
import subprocess
import yaml
from typing import Optional
from app.agents.page_exploration.playwright.schemas import (
    SnapshotResult,
    NavigateResult,
    ClickResult,
    FillResult,
    ElementInfo,
)


class PlaywrightCLI:
    """Playwright CLI 包装器"""
    
    def __init__(self, timeout: int = 30):
        """
        初始化
        
        Args:
            timeout: 命令超时时间（秒）
        """
        self.timeout = timeout
        self.session_id: Optional[str] = None
    
    def snap(self, url: str) -> SnapshotResult:
        """
        获取页面快照
        
        Args:
            url: 目标 URL
            
        Returns:
            快照结果
            
        Raises:
            TimeoutError: 命令超时
            RuntimeError: playwright-cli 执行失败
        """
        cmd = ["playwright-cli", "snap", url]
        
        if self.session_id:
            cmd.extend(["--session", self.session_id])
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"playwright-cli snap failed: {result.stderr}")
        
        # 解析 YAML 输出
        data = yaml.safe_load(result.stdout)
        
        elements = [
            ElementInfo(**elem)
            for elem in data.get("elements", [])
        ]
        
        return SnapshotResult(
            url=data["url"],
            title=data["title"],
            elements=elements,
            raw_output=result.stdout,
        )
    
    def navigate(self, url: str) -> NavigateResult:
        """
        导航到页面
        
        Args:
            url: 目标 URL
            
        Returns:
            导航结果
        """
        cmd = ["playwright-cli", "navigate", url]
        
        if self.session_id:
            cmd.extend(["--session", self.session_id])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            
            if result.returncode == 0:
                return NavigateResult(url=url, success=True)
            else:
                return NavigateResult(
                    url=url,
                    success=False,
                    error=result.stderr,
                )
        except Exception as e:
            return NavigateResult(
                url=url,
                success=False,
                error=str(e),
            )
    
    def click(self, locator: str) -> ClickResult:
        """
        点击元素
        
        Args:
            locator: 定位器（playwright 语法）
            
        Returns:
            点击结果
        """
        cmd = ["playwright-cli", "click", locator]
        
        if self.session_id:
            cmd.extend(["--session", self.session_id])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            
            if result.returncode == 0:
                return ClickResult(success=True)
            else:
                return ClickResult(success=False, error=result.stderr)
        except Exception as e:
            return ClickResult(success=False, error=str(e))
    
    def fill(self, locator: str, value: str) -> FillResult:
        """
        填写表单字段
        
        Args:
            locator: 定位器
            value: 填写值
            
        Returns:
            填写结果
        """
        cmd = ["playwright-cli", "fill", locator, value]
        
        if self.session_id:
            cmd.extend(["--session", self.session_id])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            
            if result.returncode == 0:
                return FillResult(success=True)
            else:
                return FillResult(success=False, error=result.stderr)
        except Exception as e:
            return FillResult(success=False, error=str(e))
```

- [ ] **Step 5: 运行测试验证通过**

```bash
pytest tests/agents/page_exploration/playwright/test_cli_wrapper.py -v
```

预期: ALL PASS

- [ ] **Step 6: 提交**

```bash
git add app/agents/page_exploration/playwright/ tests/agents/page_exploration/playwright/
git commit -m "feat: add Playwright CLI wrapper

- Snap: get page snapshot with elements
- Navigate: navigate to URL
- Click: click element by locator
- Fill: fill form field
- Session management for state preservation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 1.3: explored_urls 管理工具

**Files:**
- Create: `app/agents/page_exploration/services/explored_urls_service.py`
- Test: `tests/agents/page_exploration/services/test_explored_urls_service.py`

**Interfaces:**
- Consumes: `normalize_url(url: str) -> str` from Task 1.1
- Produces:
  - `ExploredUrlsService.check(normalized_path: str) -> dict`
  - `ExploredUrlsService.update(normalized_path: str, page_id: str, run_id: str) -> None`

- [ ] **Step 1: 写失败测试**

```python
# tests/agents/page_exploration/services/test_explored_urls_service.py
import pytest
from pathlib import Path
from app.agents.page_exploration.services.explored_urls_service import ExploredUrlsService


@pytest.fixture
def temp_project_dir(tmp_path):
    """创建临时项目目录"""
    project_dir = tmp_path / "projects" / "proj-123" / "page_exploration"
    project_dir.mkdir(parents=True)
    return project_dir


def test_check_not_explored_yet(temp_project_dir):
    """测试检查未探索的 URL"""
    service = ExploredUrlsService("proj-123", base_dir=temp_project_dir.parent.parent.parent)
    
    result = service.check("/workspace/agents")
    
    assert result["explored"] is False


def test_check_already_explored(temp_project_dir):
    """测试检查已探索的 URL"""
    service = ExploredUrlsService("proj-123", base_dir=temp_project_dir.parent.parent.parent)
    
    # 先更新一条记录
    service.update(
        normalized_path="/workspace/agents",
        page_id="page-001",
        run_id="run-001"
    )
    
    # 检查
    result = service.check("/workspace/agents")
    
    assert result["explored"] is True
    assert result["page_id"] == "page-001"
    assert result["page_file"] == "pages/page-001.yaml"
    assert "last_explored_at" in result


def test_update_new_url(temp_project_dir):
    """测试更新新 URL"""
    service = ExploredUrlsService("proj-123", base_dir=temp_project_dir.parent.parent.parent)
    
    service.update(
        normalized_path="/workspace/agents",
        page_id="page-001",
        run_id="run-001"
    )
    
    # 验证文件已创建
    explored_file = temp_project_dir / "explored_urls.yaml"
    assert explored_file.exists()
    
    # 验证内容
    result = service.check("/workspace/agents")
    assert result["explored"] is True


def test_update_existing_url(temp_project_dir):
    """测试更新已存在的 URL"""
    service = ExploredUrlsService("proj-123", base_dir=temp_project_dir.parent.parent.parent)
    
    # 第一次更新
    service.update(
        normalized_path="/workspace/agents",
        page_id="page-001",
        run_id="run-001"
    )
    
    # 第二次更新（覆盖）
    service.update(
        normalized_path="/workspace/agents",
        page_id="page-001",
        run_id="run-002"  # 新的 run_id
    )
    
    # 验证已更新
    result = service.check("/workspace/agents")
    assert result["last_run_id"] == "run-002"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
pytest tests/agents/page_exploration/services/test_explored_urls_service.py -v
```

预期: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现 explored_urls 服务**

```python
# app/agents/page_exploration/services/explored_urls_service.py
"""
explored_urls.yaml 管理服务

管理项目级已探索 URL 列表
"""
from pathlib import Path
from datetime import datetime
from typing import Optional
import yaml


class ExploredUrlsService:
    """explored_urls 服务"""
    
    def __init__(self, project_id: str, base_dir: Optional[Path] = None):
        """
        初始化
        
        Args:
            project_id: 项目 ID
            base_dir: 基础目录（默认 data/projects）
        """
        if base_dir is None:
            base_dir = Path("data/projects")
        
        self.project_id = project_id
        self.project_dir = base_dir / project_id / "page_exploration"
        self.explored_urls_file = self.project_dir / "explored_urls.yaml"
        
        # 确保目录存在
        self.project_dir.mkdir(parents=True, exist_ok=True)
    
    def check(self, normalized_path: str) -> dict:
        """
        检查 URL 是否已探索
        
        Args:
            normalized_path: 归一化路径（如 "/workspace/agents"）
            
        Returns:
            {
                "explored": bool,
                "page_id": str (if explored),
                "page_file": str (if explored),
                "last_explored_at": str (if explored),
                "last_run_id": str (if explored),
            }
        """
        if not self.explored_urls_file.exists():
            return {"explored": False}
        
        data = yaml.safe_load(self.explored_urls_file.read_text(encoding="utf-8"))
        
        for url_record in data.get("urls", []):
            if url_record["normalized_path"] == normalized_path:
                return {
                    "explored": True,
                    "page_id": url_record["page_id"],
                    "page_file": url_record["page_file"],
                    "last_explored_at": url_record["last_explored_at"],
                    "last_run_id": url_record["last_run_id"],
                }
        
        return {"explored": False}
    
    def update(
        self,
        normalized_path: str,
        page_id: str,
        run_id: str,
    ) -> None:
        """
        更新 explored_urls.yaml
        
        Args:
            normalized_path: 归一化路径
            page_id: 页面 ID
            run_id: 探索 run ID
        """
        # 读取现有数据
        if self.explored_urls_file.exists():
            data = yaml.safe_load(self.explored_urls_file.read_text(encoding="utf-8"))
        else:
            data = {
                "version": "1.0",
                "project_id": self.project_id,
                "urls": [],
            }
        
        # 查找是否已存在
        found = False
        for url_record in data["urls"]:
            if url_record["normalized_path"] == normalized_path:
                # 更新现有记录
                url_record["last_explored_at"] = datetime.utcnow().isoformat() + "Z"
                url_record["last_run_id"] = run_id
                found = True
                break
        
        # 如果不存在，添加新记录
        if not found:
            data["urls"].append({
                "normalized_path": normalized_path,
                "page_id": page_id,
                "page_file": f"pages/{page_id}.yaml",
                "last_explored_at": datetime.utcnow().isoformat() + "Z",
                "last_run_id": run_id,
            })
        
        # 写回文件
        self.explored_urls_file.write_text(
            yaml.dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/agents/page_exploration/services/test_explored_urls_service.py -v
```

预期: ALL PASS

- [ ] **Step 5: 提交**

```bash
git add app/agents/page_exploration/services/ tests/agents/page_exploration/services/
git commit -m "feat: add explored URLs management service

- Check if URL already explored
- Update explored_urls.yaml
- Project-level URL tracking
- Used for loop detection, not blocking re-exploration

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## 阶段 1 完成标准

- [ ] `normalize_url()` 正确归一化各种 URL
- [ ] `PlaywrightCLI` 成功调用 playwright-cli 命令
- [ ] `ExploredUrlsService` 正确管理 explored_urls.yaml
- [ ] 所有单元测试通过
- [ ] 代码已提交到 git

---

## 阶段 2-6 概要

由于篇幅限制，这里提供概要。完整计划请参考规范文档第 8 节。

### 阶段 2: LangChain Agent Tools（2-3天）
- Task 2.1: playwright_tools.py（snap/navigate/click/fill tools）
- Task 2.2: explored_urls_tools.py（check/update tools）
- Task 2.3: artifact_tools.py（write page YAML tools）

### 阶段 3: 探索编排器 + 产物服务（3-4天）
- Task 3.1: ExplorationQueue（URL 队列管理）
- Task 3.2: ArtifactService（页面产物生成）
- Task 3.3: ExplorationOrchestrator（探索编排器）

### 阶段 4: FastAPI Service + SSE（2-3天）
- Task 4.1: ExplorationRun 数据库模型
- Task 4.2: SSE EventEmitter
- Task 4.3: FastAPI routes

### 阶段 5: 前端页面管理界面（3-4天）
- Task 5.1: PageExplorationManager 组件
- Task 5.2: PageTree 组件
- Task 5.3: PageDetail 组件
- Task 5.4: SSE Hook（useExplorationStream）

### 阶段 6: 集成测试 + 文档（2-3天）
- Task 6.1: 端到端测试
- Task 6.2: API 文档
- Task 6.3: 用户文档

