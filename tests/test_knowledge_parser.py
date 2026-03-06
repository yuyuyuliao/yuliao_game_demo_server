from pathlib import Path

from app.knowledge_parser import KnowledgeParser


def test_knowledge_parser_load_documents():
    metadata_path = Path(__file__).resolve().parents[1] / "app" / "knowledge_metadata.json"
    documents = KnowledgeParser(metadata_path=metadata_path).load_documents()

    assert "minesweeper-1" in documents
    assert "chess-1" in documents
    assert documents["chess-1"].startswith("国际象棋开局建议")
