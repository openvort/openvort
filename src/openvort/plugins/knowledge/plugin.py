"""Knowledge Base plugin — document RAG for AI conversations."""

from pathlib import Path

from openvort.plugin.base import BasePlugin, BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.knowledge")


class KnowledgePlugin(BasePlugin):
    """知识库插件 — 文档上传、向量化、AI 对话中语义检索"""

    name = "knowledge"
    display_name = "知识库"
    description = "上传文档到知识库，AI 对话时自动检索相关内容作为上下文，支持 PDF/Word/Markdown/TXT"
    version = "0.1.0"
    core = True

    def get_tools(self) -> list[BaseTool]:
        from openvort.plugins.knowledge.tools.search import KBSearchTool
        return [KBSearchTool()]

    def get_prompts(self) -> list[str]:
        prompts_dir = Path(__file__).parent / "prompts"
        prompts = []
        for f in sorted(prompts_dir.glob("*.md")):
            try:
                prompts.append(f.read_text(encoding="utf-8"))
            except Exception as e:
                log.warning(f"读取 prompt 文件 {f.name} 失败: {e}")
        return prompts

    def validate_credentials(self) -> bool:
        return True

    def get_api_router(self):
        from openvort.web.routers.knowledge import router
        return router
