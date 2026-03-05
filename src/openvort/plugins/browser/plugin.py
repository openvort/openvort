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


async def _take_screenshots(count: int = 1) -> list[str]:
    """连续截取多张页面截图，返回 base64 编码的图片列表"""
    screenshots = []
    for _ in range(count):
        try:
            page = await _get_page()
            screenshot_bytes = await page.screenshot(full_page=False)
            b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            if b64:
                screenshots.append(b64)
        except Exception as e:
            log.warning(f"截图失败: {e}")
            break
    return screenshots


async def _take_screenshot() -> str:
    """截取当前页面，返回 base64 编码的图片"""
    screenshots = await _take_screenshots(1)
    return screenshots[0] if screenshots else ""


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
                "screenshot_count": {
                    "type": "integer",
                    "description": "截图数量（默认 0，不截图；>0 时截图，上限 5）",
                    "default": 0,
                },
            },
            "required": ["url"],
        }

    async def execute(self, params: dict) -> str:
        url = params.get("url", "")
        wait_until = params.get("wait_until", "domcontentloaded")
        screenshot_count = min(max(params.get("screenshot_count", 0), 0), 5)
        output_queue = params.pop("_output_queue", None)

        def _output(msg: str):
            if output_queue:
                try:
                    asyncio.get_event_loop().call_soon_threadsafe(output_queue.put_nowait, msg)
                except Exception:
                    pass

        if not url:
            return "请提供 URL"
        try:
            page = await _get_page()
            _output("正在打开页面...")
            resp = await page.goto(url, wait_until=wait_until, timeout=30000)
            title = await page.title()
            status = resp.status if resp else "unknown"
            result = f"已导航到: {url}\n标题: {title}\n状态码: {status}"
            # 仅在需要时截图
            if screenshot_count > 0:
                if screenshot_count > 1:
                    _output(f"正在截取 {screenshot_count} 张截图...")
                screenshots = await _take_screenshots(screenshot_count)
                for b64 in screenshots:
                    result += f"\n[screenshot]{b64}"
                _output("截图完成")
            return result
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
                "screenshot_count": {
                    "type": "integer",
                    "description": "截图数量（默认 0，不截图；>0 时截图，上限 5）",
                    "default": 0,
                },
            },
            "required": [],
        }

    async def execute(self, params: dict) -> str:
        selector = params.get("selector", "body")
        max_length = params.get("max_length", 3000)
        screenshot_count = min(max(params.get("screenshot_count", 0), 0), 5)
        output_queue = params.pop("_output_queue", None)

        def _output(msg: str):
            if output_queue:
                try:
                    asyncio.get_event_loop().call_soon_threadsafe(output_queue.put_nowait, msg)
                except Exception:
                    pass

        try:
            page = await _get_page()
            _output("正在提取页面文本...")
            text = await page.inner_text(selector, timeout=10000)
            text = text.strip()
            if len(text) > max_length:
                text = text[:max_length] + "...(已截断)"
            url = page.url
            title = await page.title()
            result = f"页面: {title} ({url})\n\n{text}"
            # 仅在需要时截图
            if screenshot_count > 0:
                if screenshot_count > 1:
                    _output(f"正在截取 {screenshot_count} 张截图...")
                screenshots = await _take_screenshots(screenshot_count)
                for b64 in screenshots:
                    result += f"\n[screenshot]{b64}"
                _output("完成")
            return result
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
                "count": {
                    "type": "integer",
                    "description": "连续截图数量（默认 1，上限 5）",
                    "default": 1,
                },
            },
            "required": [],
        }

    async def execute(self, params: dict) -> str:
        full_page = params.get("full_page", False)
        selector = params.get("selector", "")
        count = min(max(params.get("count", 1), 1), 5)  # 限制 1-5 张
        output_queue = params.pop("_output_queue", None)

        def _output(msg: str):
            if output_queue:
                try:
                    asyncio.get_event_loop().call_soon_threadsafe(output_queue.put_nowait, msg)
                except Exception:
                    pass

        try:
            page = await _get_page()
            screenshots = []
            for i in range(count):
                _output(f"正在截取第 {i+1}/{count} 张...")
                if selector:
                    # 截取指定元素
                    element = await page.query_selector(selector)
                    if element:
                        screenshot_bytes = await element.screenshot()
                    else:
                        continue
                else:
                    screenshot_bytes = await page.screenshot(full_page=full_page)
                b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                if b64:
                    screenshots.append(b64)
            if not screenshots:
                return "截图失败: 未找到指定元素"
            # 拼接多段 [screenshot]base64
            _output(f"截图完成，共 {len(screenshots)} 张")
            return "\n".join(f"[screenshot]{b64}" for b64 in screenshots)
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
                "screenshot_count": {
                    "type": "integer",
                    "description": "截图数量（默认 0，不截图；>0 时截图，上限 5）",
                    "default": 0,
                },
            },
            "required": [],
        }

    async def execute(self, params: dict) -> str:
        selector = params.get("selector", "")
        text = params.get("text", "")
        screenshot_count = min(max(params.get("screenshot_count", 0), 0), 5)
        output_queue = params.pop("_output_queue", None)

        def _output(msg: str):
            if output_queue:
                try:
                    asyncio.get_event_loop().call_soon_threadsafe(output_queue.put_nowait, msg)
                except Exception:
                    pass

        try:
            page = await _get_page()
            if text:
                _output(f"正在点击文本: {text}")
                await page.get_by_text(text).click(timeout=10000)
                result = f"已点击文本: {text}"
            elif selector:
                _output(f"正在点击: {selector}")
                await page.click(selector, timeout=10000)
                result = f"已点击: {selector}"
            else:
                return "请提供 selector 或 text"
            # 仅在需要时截图
            if screenshot_count > 0:
                if screenshot_count > 1:
                    _output(f"正在截取 {screenshot_count} 张截图...")
                screenshots = await _take_screenshots(screenshot_count)
                for b64 in screenshots:
                    result += f"\n[screenshot]{b64}"
                _output("完成")
            return result
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
                "screenshot_count": {
                    "type": "integer",
                    "description": "截图数量（默认 0，不截图；>0 时截图，上限 5）",
                    "default": 0,
                },
            },
            "required": ["selector", "text"],
        }

    async def execute(self, params: dict) -> str:
        selector = params.get("selector", "")
        text = params.get("text", "")
        screenshot_count = min(max(params.get("screenshot_count", 0), 0), 5)
        output_queue = params.pop("_output_queue", None)

        def _output(msg: str):
            if output_queue:
                try:
                    asyncio.get_event_loop().call_soon_threadsafe(output_queue.put_nowait, msg)
                except Exception:
                    pass

        if not selector or not text:
            return "请提供 selector 和 text"
        try:
            page = await _get_page()
            _output(f"正在输入: {text}")
            await page.fill(selector, text, timeout=10000)
            result = f"已输入: {selector} = '{text}'"
            # 仅在需要时截图
            if screenshot_count > 0:
                if screenshot_count > 1:
                    _output(f"正在截取 {screenshot_count} 张截图...")
                screenshots = await _take_screenshots(screenshot_count)
                for b64 in screenshots:
                    result += f"\n[screenshot]{b64}"
                _output("完成")
            return result
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

    def get_permissions(self) -> list[dict]:
        return [
            {"code": "browser.use", "display_name": "使用浏览器"},
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
