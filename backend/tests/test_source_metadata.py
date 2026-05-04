from app.services.legal_engine import LegalEngine


def test_source_metadata_includes_all_non_text_hit_fields():
    engine = object.__new__(LegalEngine)
    metadata = engine._source_metadata(
        {
            "title": "Sample judgment",
            "citation": "2025 INSC 1",
            "text": "Long retrieved body should stay out of metadata rows.",
            "linked_citations": ["Section 303", "Section 173"],
            "chunk_size": 1200,
            "metadata": {"court": "Supreme Court of India"},
            "score": 0.91,
        }
    )

    assert metadata["title"] == "Sample judgment"
    assert metadata["citation"] == "2025 INSC 1"
    assert metadata["court"] == "Supreme Court of India"
    assert metadata["linked_citations"] == '["Section 303", "Section 173"]'
    assert metadata["chunk_size"] == "1200"
    assert metadata["score"] == "0.91"
    assert "text" not in metadata
