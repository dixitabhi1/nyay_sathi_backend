CREATE TABLE IF NOT EXISTS corpus_documents (
    document_id VARCHAR PRIMARY KEY,
    source_id VARCHAR,
    title VARCHAR,
    citation VARCHAR,
    source_type VARCHAR,
    document_type VARCHAR,
    jurisdiction VARCHAR,
    language VARCHAR,
    source_url VARCHAR,
    local_path VARCHAR,
    summary VARCHAR,
    text_length BIGINT,
    content_hash VARCHAR
);

CREATE TABLE IF NOT EXISTS corpus_chunks (
    chunk_id VARCHAR PRIMARY KEY,
    document_id VARCHAR,
    vector_position BIGINT,
    title VARCHAR,
    citation VARCHAR,
    source_type VARCHAR,
    language VARCHAR,
    chunk_strategy VARCHAR,
    chunk_size BIGINT,
    summary VARCHAR,
    linked_citations VARCHAR,
    text VARCHAR
);
