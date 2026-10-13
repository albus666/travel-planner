"""从 UTF-8 文本文件读取问题并检索（供 run_on_server.ps1 调用，避开 shell 中文引号问题）。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from retrieval.search_chunks import search


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "question_file",
        type=Path,
        help="UTF-8 文本文件，内容为用户问题",
    )
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    question = args.question_file.read_text(encoding="utf-8").strip()
    if not question:
        print("question file is empty", file=sys.stderr)
        return 2

    hits = search(question, top_k=args.top_k)
    print(f"Q: {question}")
    print(f"hits={len(hits)}")
    for i, h in enumerate(hits, 1):
        preview = (h["text"] or "").replace("\n", " ")
        if len(preview) > 160:
            preview = preview[:160] + "…"
        print(
            f"{i}. {h['name']} / {h['theme']}  "
            f"sim={float(h['similarity']):.4f}  "
            f"chunk_id={h['chunk_id']}"
        )
        print(f"   {preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
