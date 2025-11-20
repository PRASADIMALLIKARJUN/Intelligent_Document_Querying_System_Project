CREATE SCHEMA IF NOT EXISTS bedrock_integration;

CREATE TABLE IF NOT EXISTS bedrock_integration.documents (
  id serial PRIMARY KEY,
  doc_key text,
  content text,
  embedding float8[],
  metadata jsonb,
  created_at timestamptz default now()
);
