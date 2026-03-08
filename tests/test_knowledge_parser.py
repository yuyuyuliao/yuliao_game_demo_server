from pathlib import Path

from app.knowledge_parser import KnowledgeParser


def test_knowledge_parser_load_documents():
    metadata_path = Path(__file__).resolve().parents[1] / "app" / "knowledge_metadata.json"
    documents = KnowledgeParser(metadata_path=metadata_path).load_documents()

    assert len(documents) == 6
    assert "minesweeper-1" in documents
    assert "minesweeper-2" in documents
    assert "chess-1" in documents
    assert "chess-2" in documents
    assert "farm-1" in documents
    assert "farm-2" in documents
    assert documents["minesweeper-1"].startswith("扫雷技巧")
    assert documents["minesweeper-2"].startswith("扫雷技巧")
    assert documents["chess-1"].startswith("国际象棋开局建议")
    assert documents["chess-2"].startswith("国际象棋建议")
    assert documents["farm-1"].startswith("胡萝卜种植攻略")
    assert documents["farm-2"].startswith("农田管理技巧")


def test_knowledge_parser_skips_malformed_items(tmp_path):
    malformed_metadata = tmp_path / "knowledge_metadata.json"
    malformed_metadata.write_text(
        """
{
  "version": "1.0",
  "knowledge": [
    {"id": "valid-1", "content": "保留"},
    {"id": "missing-content"},
    {"content": "missing-id"},
    "not-an-object"
  ]
}
""",
        encoding="utf-8",
    )

    documents = KnowledgeParser(metadata_path=malformed_metadata).load_documents()
    assert documents == {"valid-1": "保留"}
