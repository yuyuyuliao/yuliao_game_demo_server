from __future__ import annotations

import json
from pathlib import Path


class KnowledgeParser:
    """知识元数据解析器：从 JSON 文件中提取可用于检索的文档内容。"""

    def __init__(self, metadata_path: Path | None = None) -> None:
        """初始化解析器，可注入自定义元数据路径用于测试或扩展。"""
        app_dir = Path(__file__).resolve().parent
        self._metadata_path = metadata_path or app_dir / "knowledge_metadata.json"

    def load_documents(self) -> dict[str, str]:
        """读取并校验知识元数据，返回 {id: content} 结构。"""
        try:
            with self._metadata_path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}

        if not isinstance(payload, dict):
            return {}

        items = payload.get("knowledge", [])
        if not isinstance(items, list):
            return {}

        documents: dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            content = item.get("content")
            if isinstance(item_id, str) and isinstance(content, str):
                documents[item_id] = content
        return documents
