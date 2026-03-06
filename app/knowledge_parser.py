from __future__ import annotations

import json
from pathlib import Path


class KnowledgeParser:
    def __init__(self, metadata_path: Path | None = None) -> None:
        app_dir = Path(__file__).resolve().parent
        self._metadata_path = metadata_path or app_dir / "knowledge_metadata.json"

    def load_documents(self) -> dict[str, str]:
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
