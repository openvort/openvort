"""
浏览器控制插件

基于 Playwright 提供浏览器自动化能力，支持导航、截图、点击、输入等操作。
适用于研发场景：测试验证、文档爬取、页面截图等。

需要安装: pip install playwright && playwright install chromium
"""

from __future__ import annotations

import asyncio
import base64
from typing import Any

from openvort.plugin.base import BasePlugin, BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.browser")

# 全局浏览器实例（延迟初始化）
_browser = None
_page = None


async def _get_page():
    """获取或创建浏览器页面（单例）"""
    global _browser, _page
    if _page and not _page.is_closed():
        return _page
    try:
        from playwright.async_api import async_playwright
        pw = await async_playwright().start()
        _browser = await pw.chromium.launch(headless=True)
        _page = await _browser.new_page()
        return _page
    except ImportError:
        raise RuntimeError("请安装 playwright: pip install playwright && playwright install chromium")
    except Exception as e:
        raise RuntimeError(f"启动浏览器失败: {e}")


async def _close_browser():
    global _browser, _page
    if _page:
        try:
            await _page.close()
        except Exception:
            pass
        _page = None
    if _browser:
        try:
            await _browser.close()
        except Exception:
            pass
        _browser = None


class BrowserNavigateTool(BaseTool):
    name = "browser_navigate"
    description = "导航到指定 URL，返回页面标题和状态码。用于打开网页、测试页面可访问性。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "要访问的 URL"},
                "wait_until": {
                    "type": "string",
                    "description": "等待条件: load|domcontentloaded|networkidle",
                    "default": "domcontentloaded",
                },
            },
            "required": ["url"],
        }

    async def execute(self, params: dict) -> str:
        url = params.get("url", "")
        wait_until = params.get("wait_until", "domcontentloaded")
        if not url:
            return "请提供 URL"
        try:
            page = await _get_page()
            resp = await page.goto(url, wait_until=wait_until, timeout=30000)
            title = await page.title()
            status = resp.status if resp else "unknown"
            return f"已导航到: {url}\n标题: {title}\n状态码: {status}"
        except Exception as e:
            return f"导航失败: {e}"


class BrowserSnapshotTool(BaseTool):
    name = "browser_snapshot"
    description = "获取当前页面的文本内容摘要（提取可见文本），用于了解页面内容。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS 选择器，只提取该元素内的文本（可选，默认 body）",
                },
                "max_length": {
                    "type": "integer",
                    "description": "最大返回字符数（默认 3000）",
                },
            },
            "required": [],
        }

    async def execute(self, params: dict) -> str:
        selector = params.get("selector", "body")
        max_length = params.get("max_length", 3000)
        try:
            page = await _get_page()
            text = await page.inner_text(selector, timeout=10000)
            text = text.strip()
            if len(text) > max_length:
                text = text[:max_length] + "...(已截断)"
            url = page.url
            title = await page.title()
            return f"页面: {title} ({url})\n\n{text}"
        except Exception as e:
            return f"获取页面内容失败: {e}"


class BrowserScreenshotTool(BaseTool):
    name = "browser_screenshot"
    description = "对当前页面截图，返回截图文件路径。用于视觉验证、Bug 截图等。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "full_page": {
                    "type": "boolean",
                    "description": "是否截取整个页面（默认 false，只截可视区域）",
                },
                "selector": {
                    "type": "string",
                    "description": "CSS 选择器，只截取该元素（可选）",
                },
            },
            "required": [],
        }

    async def execute(self, params: dict) -> str:
        full_page = params.get("full_page", False)
        selector = params.get("selector", "")
        try:
            page = await _get_page()
            import tempfile
            import os
            path = os.path.join(tempfile.gettempdir(), f"openvort_screenshot_{id(page)}.png")
            if selector:
                element = await page.query_selector(selector)
                if element:
                    await element.screenshot(path=path)
                else:
                    return f"未找到元素: {selector}"
            else:
                await page.screenshot(path=path, full_page=full_page)
            size = os.path.getsize(path)
            return f"截图已保存: {path} ({size} bytes)"
        except Exception as e:
            return f"截图失败: {e}"


class BrowserClickTool(BaseTool):
    name = "browser_click"
    description = "点击页面上的元素。通过 CSS 选择器或文本内容定位元素。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS 选择器（如 'button.submit', '#login-btn'）",
                },
                "text": {
                    "type": "string",
                    "description": "按文本内容匹配元素（如 '登录'、'提交'），与 selector 二选一",
                },
            },
            "required": [],
        }

    async def execute(self, params: dict) -> str:
        selector = params.get("selector", "")
        text = params.get("text", "")
        try:
            page = await _get_page()
            if text:
                await page.get_by_text(text).click(timeout=10000)
                return f"已点击文本: {text}"
            elif selector:
                await page.click(selector, timeout=10000)
                return f"已点击: {selector}"
            else:
                return "请提供 selector 或 text"
        except Exception as e:
            return f"点击失败: {e}"


class BrowserTypeTool(BaseTool):
    name = "browser_type"
    description = "在输入框中输入文本。先清空再输入。"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "输入框的 CSS 选择器",
                },
                "text": {
                    "type": "string",
                    "description": "要输入的文本",
                },
            },
            "required": ["selector", "text"],
        }

    async def execute(self, params: dict) -> str:
        selector = params.get("selector", "")
        text = params.get("text", "")
        if not selector or not text:
            return "请提供 selector 和 text"
        try:
            page = await _get_page()
            await page.fill(selector, text, timeout=10000)
            return f"已输入: {selector} = '{text}'"
        except Exception as e:
            return f"输入失败: {e}"


class BrowserPlugin(BasePlugin):
    """浏览器控制插件"""

    name = "browser"
    display_name = "浏览器控制"
    description = "提供浏览器自动化能力：导航、截图、点击、输入等"
    version = "0.1.0"
    source = "builtin"

    def get_tools(self) -> list[BaseTool]:
        return [
            BrowserNavigateTool(),
            BrowserSnapshotTool(),
            BrowserScreenshotTool(),
            BrowserClickTool(),
            BrowserTypeTool(),
        ]

    def get_prompts(self) -> list[str]:
        return [
            "## 浏览器控制\n\n"
            "你可以使用浏览器工具来：\n"
            "- 打开网页查看内容 (browser_navigate + browser_snapshot)\n"
            "- 截取页面截图 (browser_screenshot)\n"
            "- 与页面交互：点击按钮、填写表单 (browser_click + browser_type)\n"
            "- 适用场景：测试验证、文档查阅、页面截图\n"
        ]

    def validate_credentials(self) -> bool:
        try:
            import playwright
            return True
        except ImportError:
            log.warning("playwright 未安装，浏览器插件不可用。运行: pip install playwright && playwright install chromium")
            return False
