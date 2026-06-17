"""Mermaid diagram management utility for token optimization."""

from __future__ import annotations

import base64
import urllib.request
import zlib
from pathlib import Path
from typing import Optional


class MermaidManager:
    """
    Mermaid 图管理器：生成 → 保存 → 引用

    核心优化：
    1. Mermaid 代码保存为文件，传递路径引用（不传源码）
    2. 自动调用 Kroki API 生成 PNG
    3. 全链路复用，避免重复生成

    Token 节省效果：
    - Mermaid 源码：3-5K tokens
    - 路径引用：0.05K tokens
    - 节省 99%
    """

    def __init__(self, output_dir: str | Path):
        """
        初始化 Mermaid 管理器

        Args:
            output_dir: 输出目录路径（例如：release_version/V1.0.0/用户登录/diagrams/）
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_state_machine(
        self,
        state_object_name: str,
        mermaid_code: str,
        *,
        render_png: bool = True,
    ) -> dict[str, str]:
        """
        保存状态机图

        Args:
            state_object_name: 状态对象名称（例如：Order, User）
            mermaid_code: Mermaid 源码
            render_png: 是否渲染为 PNG

        Returns:
            文件路径字典：{mmd: "相对路径", png: "相对路径或空"}
        """
        # 保存 .mmd 源码
        filename = f"{state_object_name}_state_machine.mmd"
        mmd_path = self.output_dir / filename
        mmd_path.write_text(mermaid_code, encoding="utf-8")

        relative_mmd_path = str(mmd_path.relative_to(self.output_dir.parent.parent))

        # 生成 PNG
        png_relative_path = ""
        if render_png:
            png_relative_path = self._render_to_png_sync(mermaid_code, mmd_path)

        return {
            "mmd": relative_mmd_path,
            "png": png_relative_path,
        }

    def save_domain_model(
        self,
        mermaid_code: str,
        *,
        render_png: bool = True,
    ) -> dict[str, str]:
        """
        保存领域模型图

        Args:
            mermaid_code: Mermaid 源码
            render_png: 是否渲染为 PNG

        Returns:
            文件路径字典：{mmd: "相对路径", png: "相对路径或空"}
        """
        filename = "domain_model.mmd"
        mmd_path = self.output_dir / filename
        mmd_path.write_text(mermaid_code, encoding="utf-8")

        relative_mmd_path = str(mmd_path.relative_to(self.output_dir.parent.parent))

        png_relative_path = ""
        if render_png:
            png_relative_path = self._render_to_png_sync(mermaid_code, mmd_path)

        return {
            "mmd": relative_mmd_path,
            "png": png_relative_path,
        }

    def save_custom_diagram(
        self,
        diagram_name: str,
        mermaid_code: str,
        *,
        render_png: bool = True,
    ) -> dict[str, str]:
        """
        保存自定义图表

        Args:
            diagram_name: 图表名称（例如：architecture, flow）
            mermaid_code: Mermaid 源码
            render_png: 是否渲染为 PNG

        Returns:
            文件路径字典：{mmd: "相对路径", png: "相对路径或空"}
        """
        filename = f"{diagram_name}.mmd"
        mmd_path = self.output_dir / filename
        mmd_path.write_text(mermaid_code, encoding="utf-8")

        relative_mmd_path = str(mmd_path.relative_to(self.output_dir.parent.parent))

        png_relative_path = ""
        if render_png:
            png_relative_path = self._render_to_png_sync(mermaid_code, mmd_path)

        return {
            "mmd": relative_mmd_path,
            "png": png_relative_path,
        }

    def load_mermaid(self, relative_path: str) -> str:
        """
        按需加载 Mermaid 源码

        Args:
            relative_path: 相对路径（从 save_* 方法返回的路径）

        Returns:
            Mermaid 源码
        """
        full_path = self.output_dir.parent.parent / relative_path
        if not full_path.exists():
            raise FileNotFoundError(f"Mermaid 文件不存在: {full_path}")

        return full_path.read_text(encoding="utf-8")

    def _render_to_png_sync(self, mermaid_code: str, mmd_path: Path) -> str:
        """
        调用 Kroki API 渲染为 PNG（同步版本）

        Args:
            mermaid_code: Mermaid 源码
            mmd_path: .mmd 文件路径

        Returns:
            PNG 相对路径（失败时返回空字符串）
        """
        try:
            # 压缩和编码
            compressed = zlib.compress(mermaid_code.encode("utf-8"))
            encoded = base64.urlsafe_b64encode(compressed).decode("ascii")

            # 调用 Kroki API
            png_url = f"https://kroki.io/mermaid/png/{encoded}"
            png_path = mmd_path.with_suffix(".png")

            req = urllib.request.Request(
                png_url,
                headers={"User-Agent": "Mozilla/5.0 (requirement-analysis-agent)"}
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                png_data = response.read()
                png_path.write_bytes(png_data)

            # 返回相对路径
            return str(png_path.relative_to(self.output_dir.parent.parent))

        except Exception as e:
            print(f"[MermaidManager] PNG 生成失败: {e}")
            print(f"[MermaidManager] .mmd 文件已保存，可稍后手动渲染")
            return ""

    async def render_to_png_async(
        self,
        mermaid_code: str,
        mmd_path: Path
    ) -> str:
        """
        调用 Kroki API 渲染为 PNG（异步版本）

        Args:
            mermaid_code: Mermaid 源码
            mmd_path: .mmd 文件路径

        Returns:
            PNG 相对路径（失败时返回空字符串）
        """
        import asyncio

        # 使用 asyncio 包装同步方法
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._render_to_png_sync,
            mermaid_code,
            mmd_path
        )

    def get_mermaid_edit_url(self, mermaid_code: str) -> str:
        """
        生成 Mermaid Live Editor 在线编辑链接

        Args:
            mermaid_code: Mermaid 源码

        Returns:
            在线编辑链接
        """
        try:
            compressed = zlib.compress(mermaid_code.encode("utf-8"))
            encoded = base64.urlsafe_b64encode(compressed).decode("ascii")
            return f"https://mermaid.live/edit#pako:{encoded}"
        except Exception:
            return ""


__all__ = ["MermaidManager"]
