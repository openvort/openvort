"""Knowledge base search tool — kb_search."""

from __future__ import annotations

import json

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.knowledge.tools.search")


class KBSearchTool(BaseTool):
    name = "kb_search"
    description = (
        "搜索知识库中的文档内容。"
        "当用户提问涉及内部文档、规范、流程、产品知识等内容时使用此工具检索相关信息。"
        "返回最相关的文档片段及来源。"
    )

    def __init__(self):
        self._retriever = None

    def _get_retriever(self):
        if self._retriever is None:
            from openvort.db.engine import get_session_factory
            from openvort.plugins.knowledge.retriever import KBRetriever
            from openvort.web.deps import get_embedding_service

            embedding_svc = get_embedding_service()
            self._retriever = KBRetriever(
                session_factory=get_session_factory(),
                embedding_service=embedding_svc,
            )
        return self._retriever

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询（自然语言描述你要查找的内容）",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回最相关的结果数量（默认 5）",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(self, params: dict) -> str:
        query = params.get("query", "")
        top_k = params.get("top_k", 5)

        if not query:
            return json.dumps({"ok": False, "message": "查询内容不能为空"}, ensure_ascii=False)

        try:
            retriever = self._get_retriever()
        except Exception as e:
            log.error(f"获取检索器失败: {e}")
            return json.dumps(
                {"ok": False, "message": "知识库服务未就绪，请确认已配置 Embedding Provider"},
                ensure_ascii=False,
            )

        try:
            results = await retriever.search(query, top_k=top_k)
        except Exception as e:
            log.error(f"知识库搜索失败: {e}")
            return json.dumps({"ok": False, "message": f"搜索失败: {e}"}, ensure_ascii=False)

        if not results:
            return json.dumps(
                {"ok": True, "count": 0, "results": [], "message": "未找到相关内容"},
                ensure_ascii=False,
            )

        items = []
        for r in results:
            items.append({
                "document": r.document_title,
                "score": r.score,
                "content": r.content,
            })

        return json.dumps(
            {"ok": True, "count": len(items), "results": items},
            ensure_ascii=False,
        )
