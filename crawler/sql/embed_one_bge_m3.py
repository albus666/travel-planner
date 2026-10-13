"""Embed exactly one pending rag_chunk with BGE-M3 dense (1024) and write to Postgres.

Requires DATABASE_URL in the environment. CPU by default (no CUDA on this host).
"""

from __future__ import annotations

import os
import sys

import numpy as np
import psycopg
from FlagEmbedding import BGEM3FlagModel


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL missing", file=sys.stderr)
        return 2

    # Server has no NVIDIA GPU; keep fp16 off.
    print("Loading BAAI/bge-m3 (CPU, first run downloads weights)...", flush=True)
    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=False)

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT chunk_id, text
                FROM v2.rag_chunks
                WHERE embedding IS NULL
                  AND text IS NOT NULL
                  AND btrim(text) <> ''
                ORDER BY chunk_id
                LIMIT 1
                """
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("没有找到待嵌入的有效 chunk")

            chunk_id, text = row
            result = model.encode(
                [text],
                batch_size=1,
                max_length=8192,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            vector = np.asarray(result["dense_vecs"][0], dtype=np.float32)

            print("chunk_id:", chunk_id, flush=True)
            print("向量形状:", vector.shape, flush=True)

            if vector.shape != (1024,):
                raise ValueError(f"预期 1024 维，实际得到 {vector.shape}")
            if not np.isfinite(vector).all():
                raise ValueError("向量中出现 NaN 或无穷值")

            vector_text = "[" + ",".join(f"{x:.8f}" for x in vector) + "]"

            cur.execute(
                """
                UPDATE v2.rag_chunks
                SET embedding = %s::vector
                WHERE chunk_id = %s
                  AND embedding IS NULL
                """,
                (vector_text, chunk_id),
            )
            if cur.rowcount != 1:
                raise RuntimeError("没有成功更新且仅更新一条记录")

            print("已写入一条向量", flush=True)

        conn.commit()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
