"""RAG 检索入口：把自然语言问题编成向量，再从 PostgreSQL 取最相近的知识片段。

本模块只做「问题 → BGE-M3 dense → pgvector 余弦距离排序」，
**不调用**任何用于生成最终答案的 LLM。

前置条件
--------
- 环境变量 ``DATABASE_URL`` 指向 travel 库（含 ``v2.rag_chunks`` / ``v2.attractions``）。
- ``v2.rag_chunks.embedding`` 已用 **同一套 BGE-M3 dense（1024 维）** 写满；
  查询时也必须用同一模型，不能混用 OpenAI 等其它 Embedding。
- 服务器无 GPU 时用 CPU 加载（``use_fp16=False``）；首次运行会从 HuggingFace 拉权重。

典型用法
--------
1. 先开 SSH 隧道（服务器 Postgres 只监听 127.0.0.1）::

       powershell -ExecutionPolicy Bypass -File rag\\client\\open_db_tunnel.ps1

2. 在项目根放置 ``.env``（可从 ``.env.example`` 复制），至少包含::

       DATABASE_URL=postgresql://travel_agent:***@127.0.0.1:5432/travel

3. 再运行（推荐走常驻服务）::

       powershell -ExecutionPolicy Bypass -File rag\\client\\run_on_server.ps1

库内调用（需 ``PYTHONPATH`` 含 ``rag`` 目录）::

    from retrieval.search_chunks import search
    hits = search(\"老君山有哪些寄存设施？\", top_k=3)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import psycopg
from FlagEmbedding import BGEM3FlagModel

# rag/retrieval/ -> rag/ -> 项目根
_RAG_ROOT = Path(__file__).resolve().parents[1]
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_env_files(*extra: Path) -> list[Path]:
    """从常见位置加载 ``.env`` 到 ``os.environ``（不覆盖已有环境变量）。

    查找顺序：显式传入的路径 → ``rag/.env`` → 项目根 ``.env``。
    仅支持简单的 ``KEY=VALUE`` 行；``#`` 注释与空行忽略；值两侧引号会去掉。

    Args:
        *extra: 额外要尝试的 ``.env`` 路径（存在才读取）。

    Returns:
        list[Path]: 实际成功读取过的文件路径列表（可能为空）。
    """
    candidates: list[Path] = []
    candidates.extend(extra)
    candidates.extend((_RAG_ROOT / ".env", _PROJECT_ROOT / ".env"))

    loaded: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        path = path.resolve()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value
        loaded.append(path)
    return loaded


def require_database_url(explicit: str | None = None) -> str:
    """解析可用的数据库连接串；缺失时给出可操作的中文错误说明。

    Args:
        explicit: 调用方直接传入的 URL；非空则优先使用。

    Returns:
        str: 非空的 ``DATABASE_URL``。

    Raises:
        RuntimeError: 环境变量与 ``.env`` 中都找不到 ``DATABASE_URL``。
    """
    load_env_files()
    url = explicit or os.environ.get("DATABASE_URL")
    if url:
        return url
    raise RuntimeError(
        "缺少 DATABASE_URL。\n"
        "1) 复制项目根 .env.example 为 .env，填入连接串；\n"
        "2) 先开隧道: powershell -ExecutionPolicy Bypass -File rag\\client\\open_db_tunnel.ps1\n"
        "3) 连接串主机用 127.0.0.1:5432（经 SSH 转到服务器本机 Postgres）。"
    )

# pgvector 余弦距离运算符为 <=> ；值越小越相似。
# similarity = 1 - distance，仅便于人读，检索排序仍以距离为准。
# 同一查询向量需绑定两次：SELECT 投影一次、ORDER BY 一次。
SEARCH_SQL = """
SELECT
    c.chunk_id,
    c.poi_id,
    a.name,
    c.theme,
    c.theme_label,
    c.text,
    1 - (c.embedding <=> %s::vector) AS similarity
FROM v2.rag_chunks AS c
JOIN v2.attractions AS a ON a.poi_id = c.poi_id
WHERE c.embedding IS NOT NULL
ORDER BY c.embedding <=> %s::vector
LIMIT %s
"""


@lru_cache(maxsize=1)
def load_model() -> BGEM3FlagModel:
    """加载并缓存 BGE-M3 模型（进程内只加载一次）。

    使用 ``functools.lru_cache(maxsize=1)``，避免批评测时每题重新下载/装载权重。
    当前按服务器实况固定为 CPU、关闭半精度；有 CUDA 时可再改构造参数。

    Returns:
        BGEM3FlagModel: 已就绪的 FlagEmbedding BGE-M3 实例，可用于 ``encode``。

    Note:
        无函数参数。模型 ID 固定为 ``BAAI/bge-m3``；权重目录由 ``HF_HOME`` 等环境变量决定。
    """
    print("Loading BAAI/bge-m3 (CPU)...", flush=True)
    return BGEM3FlagModel("BAAI/bge-m3", use_fp16=False)


def encode_query(model: BGEM3FlagModel, question: str) -> np.ndarray:
    """将单条用户问题编码为 BGE-M3 dense 向量。

    只取 dense 向量（``dense_vecs``），不取 sparse / ColBERT 向量，
    以便与库中 ``vector(1024)`` 列一致。

    Args:
        model: 已通过 :func:`load_model` 得到的 BGE-M3 实例。
        question: 用户问题原文（中文即可）。空串虽可能通过模型，但不应用于检索。

    Returns:
        np.ndarray: 形状 ``(1024,)``、dtype ``float32`` 的一维向量。

    Raises:
        ValueError: 输出维度不是 1024，或向量中含 NaN / Inf。
    """
    result = model.encode(
        [question],
        batch_size=1,
        max_length=8192,  # BGE-M3 支持长文本；问题通常远短于此
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False,
    )
    vector = np.asarray(result["dense_vecs"][0], dtype=np.float32)
    if vector.shape != (1024,):
        raise ValueError(f"预期 1024 维，实际 {vector.shape}")
    if not np.isfinite(vector).all():
        raise ValueError("查询向量含 NaN/Inf")
    return vector


def vector_to_pg(vector: np.ndarray) -> str:
    """把 numpy 向量格式化为 pgvector 可接受的文本字面量。

    Args:
        vector: 一维浮点数组，长度应为 1024（调用方需先校验）。

    Returns:
        str: 形如 ``[0.01234567,-0.02345678,...]`` 的字符串，
        供 SQL 中 ``%s::vector`` 绑定使用。

    Note:
        使用 8 位小数是精度与字符串长度的折中；不要截断或补齐维度来凑长度。
    """
    return "[" + ",".join(f"{x:.8f}" for x in vector) + "]"


def search(
    question: str,
    *,
    top_k: int = 3,
    database_url: str | None = None,
    model: BGEM3FlagModel | None = None,
) -> list[dict]:
    """对问题做向量检索，返回相似度最高的若干 chunk。

    流程：编码问题 → 连接数据库 → 按余弦距离排序 → 组装字典列表。
    查询向量**不会**写入 ``rag_chunks``，仅作为 SQL 参数使用。

    Args:
        question: 自然语言问题。
        top_k: 返回条数上限，默认 3。数据量约 347 条时全表排序可接受，暂不建 HNSW。
        database_url: Postgres 连接串。为 ``None`` 时读环境变量 ``DATABASE_URL``。
        model: 可选，传入已加载的模型以便复用（评测脚本会传）。为 ``None`` 时调用
            :func:`load_model`。

    Returns:
        list[dict]: 每条包含至少以下键：

        - ``chunk_id`` (str): 片段主键
        - ``poi_id`` (int): 景点 ID
        - ``name`` (str): 景点中文名（来自 ``v2.attractions``）
        - ``theme`` (str): 主题代号，如 ``visit_tips`` / ``facilities``
        - ``theme_label`` (str | None): 主题中文标签
        - ``text`` (str): 片段正文
        - ``similarity`` (Decimal/float): ``1 - 余弦距离``，越大通常越相关

        列表按距离升序（最相似在前），长度不超过 ``top_k``。

    Raises:
        RuntimeError: 未提供 ``database_url`` 且环境中无 ``DATABASE_URL``。
        ValueError: 见 :func:`encode_query`。
        psycopg.Error: 数据库连接或查询失败时由驱动抛出。
    """
    database_url = require_database_url(database_url)

    model = model or load_model()
    query_vector = encode_query(model, question)
    vector_text = vector_to_pg(query_vector)

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            # 同一向量绑定两次：SELECT 中算 similarity，ORDER BY 中排序
            cur.execute(SEARCH_SQL, (vector_text, vector_text, top_k))
            cols = [d.name for d in cur.description]
            rows = [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
    return rows


def main() -> int:
    """命令行入口：检索并打印结果。

    位置参数与选项由 ``argparse`` 解析，见 ``--help``。

    Returns:
        int: 进程退出码；成功为 ``0``。
    """
    parser = argparse.ArgumentParser(
        description="用 BGE-M3 + pgvector 检索景点知识片段（不调用回答 LLM）"
    )
    parser.add_argument(
        "question",
        nargs="?",
        default="龙门石窟的游览路线是什么？",
        help="用户问题；省略时使用示例问句",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="返回最相似的前 k 条，默认 3",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="每行输出一条完整 JSON（含全文 text），便于下游脚本消费",
    )
    args = parser.parse_args()

    hits = search(args.question, top_k=args.top_k)
    if args.json:
        for h in hits:
            print(json.dumps(h, ensure_ascii=False, default=str))
        return 0

    print(f"Q: {args.question}")
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
