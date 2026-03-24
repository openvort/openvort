"""VortSketch plugin — AI-driven UI prototype generator."""

from pathlib import Path

from openvort.plugin.base import BasePlugin, BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortsketch")


class VortSketchPlugin(BasePlugin):
    """VortSketch — AI 驱动的 UI 原型生成器"""

    name = "vortsketch"
    display_name = "VortSketch"
    description = "AI 驱动的 UI 原型生成器，从需求出发生成可交互的 HTML 原型，支持对话式迭代修改"
    version = "0.1.0"

    def get_tools(self) -> list[BaseTool]:
        return []

    def get_prompts(self) -> list[str]:
        prompts_dir = Path(__file__).parent / "prompts"
        if not prompts_dir.exists():
            return []
        prompts = []
        for f in sorted(prompts_dir.glob("*.md")):
            try:
                prompts.append(f.read_text(encoding="utf-8"))
            except Exception as e:
                log.warning(f"读取 prompt 文件 {f.name} 失败: {e}")
        return prompts

    def validate_credentials(self) -> bool:
        return True

    def get_ui_extensions(self) -> dict | None:
        return {
            "menus": [{
                "label": "VortSketch",
                "icon": "pencil-ruler",
                "path": "/vortsketch",
                "position": "sidebar",
            }],
        }

    def get_api_router(self):
        from openvort.web.routers.vortsketch import router
        return router
