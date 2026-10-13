"""Batch-embed pending v2.rag_chunks with BGE-M3 dense (1024).

- Load model once
- Fetch batches WHERE embedding IS NULL (resumable)
- Commit per batch; rollback a failed batch and record chunk_ids
- Requires DATABASE_URL in the environment
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import psycopg
from FlagEmbedding import BGEM3FlagModel


def fetch_batch(cur: psycopg.Cursor, batch_size: int) -> list[tuple[str, str]]:
    cur.execute(
        """
        SELECT chunk_id, text
        FROM v2.rag_chunks
        WHERE embedding IS NULL
          AND text IS NOT NULL
          AND btrim(text) <> ''
        ORDER BY chunk_id
        LIMIT %s
        """,
        (batch_size,),
    )
    return list(cur.fetchall())


def embed_batch(
    model: BGEM3FlagModel,
    texts: list[str],
    *,
    max_length: int,
) -> np.ndarray:
    result = model.encode(
        texts,
        batch_size=len(texts),
        max_length=max_length,
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False,
    )
    vectors = np.asarray(result["dense_vecs"], dtype=np.float32)
    expected = (len(texts), 1024)
    if vectors.shape != expected:
        raise ValueError(f"预期形状 {expected}，实际 {vectors.shape}")
    if not np.isfinite(vectors).all():
        raise ValueError("向量中出现 NaN 或无穷值")
    return vectors


def write_batch(
    cur: psycopg.Cursor,
    rows: list[tuple[str, str]],
    vectors: np.ndarray,
) -> None:
    for (chunk_id, _text), vector in zip(rows, vectors, strict=True):
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
            raise RuntimeError(f"更新失败或不唯一: {chunk_id} rowcount={cur.rowcount}")


def count_progress(cur: psycopg.Cursor) -> tuple[int, int, int]:
    cur.execute(
        """
        SELECT COUNT(*), COUNT(embedding), COUNT(*) FILTER (WHERE embedding IS NULL)
        FROM v2.rag_chunks
        """
    )
    total, embedded, pending = cur.fetchone()
    return int(total), int(embedded), int(pending)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-length", type=int, default=8192)
    parser.add_argument(
        "--max-batches",
        type=int,
        default=0,
        help="0 = process until no pending rows",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL missing", file=sys.stderr)
        return 2

    print(
        f"Loading BAAI/bge-m3 (CPU, batch_size={args.batch_size})...",
        flush=True,
    )
    model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=False)

    failed_ids: list[str] = []
    batches_done = 0
    t0 = time.time()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            total, embedded, pending = count_progress(cur)
            print(
                f"start: total={total} embedded={embedded} pending={pending}",
                flush=True,
            )

        while True:
            if args.max_batches and batches_done >= args.max_batches:
                print("reached --max-batches", flush=True)
                break

            with conn.cursor() as cur:
                rows = fetch_batch(cur, args.batch_size)
            if not rows:
                print("no more pending chunks", flush=True)
                break

            chunk_ids = [r[0] for r in rows]
            texts = [r[1] for r in rows]
            batch_t0 = time.time()
            try:
                vectors = embed_batch(model, texts, max_length=args.max_length)
                with conn.transaction():
                    with conn.cursor() as cur:
                        write_batch(cur, rows, vectors)
            except Exception as exc:  # noqa: BLE001 — log and stop batch cleanly
                conn.rollback()
                failed_ids.extend(chunk_ids)
                print(
                    f"BATCH FAILED ids={chunk_ids} error={exc!r}",
                    file=sys.stderr,
                    flush=True,
                )
                return 1

            batches_done += 1
            with conn.cursor() as cur:
                total, embedded, pending = count_progress(cur)
            print(
                f"batch#{batches_done} n={len(rows)} "
                f"{time.time() - batch_t0:.1f}s | "
                f"embedded={embedded}/{total} pending={pending}",
                flush=True,
            )

    print(
        f"done batches={batches_done} elapsed={time.time() - t0:.1f}s "
        f"failed={failed_ids}",
        flush=True,
    )
    return 0 if not failed_ids else 1


if __name__ == "__main__":
    raise SystemExit(main())
