-- Switch v2.rag_chunks.embedding to BGE-M3 dense dim (1024).
-- Safe only when no real vectors are stored (or after truncate/re-embed).
-- Do NOT pad/truncate other-dimension vectors into this column.

ALTER TABLE v2.rag_chunks
  ALTER COLUMN embedding TYPE vector(1024)
  USING CASE
    WHEN embedding IS NULL THEN NULL
    ELSE embedding::vector(1024)
  END;

COMMENT ON COLUMN v2.rag_chunks.embedding IS
  'BGE-M3 dense vector (1024). Do not pad/truncate other dims to fit.';
