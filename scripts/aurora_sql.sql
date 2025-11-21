
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS bedrock_integration;

CREATE TABLE IF NOT EXISTS bedrock_integration.documents (
  id serial PRIMARY KEY,
  doc_key text,
  content text,
  embedding vector(1536),
  metadata jsonb,
  created_at timestamptz default now()
);

SELECT * FROM pg_extension;
