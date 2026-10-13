"""小型检索评测：统计「预期景点 + 主题」是否出现在 top-k 结果中。

本脚本**不调用**回答用 LLM，只验证「问题 → 向量检索」是否找得到合适 chunk。

评测定义
--------
对每条用例检索 ``top_k`` 条；若其中**任意一条**同时满足：

- ``name == expect_name``
- ``theme == expect_theme``

则记为 **HIT**，否则 **MISS**。最终输出 ``hit@k = 命中数 / 总题数``。

用例文件
--------
默认读取 ``eval/cases/eval_questions.jsonl``。每行一个 JSON 对象，字段见
:func:`load_cases`。以 ``#`` 开头的行视为注释，会被忽略。

典型用法
--------
::

    export DATABASE_URL=postgresql://...
    export PYTHONPATH=rag
    python -m eval.runners.run_eval --top-k 3
    # 或: python rag/eval/runners/run_eval.py --top-k 3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from retrieval.search_chunks import load_env_files, load_model, search


def load_cases(path: Path) -> list[dict]:
    """从 JSONL 文件加载评测用例。

    每行应为一个 JSON 对象。空行与以 ``#`` 开头的注释行会被跳过。

    Args:
        path: 用例文件路径。文件须存在且为 UTF-8 编码。

    Returns:
        list[dict]: 用例列表。每个字典至少包含：

        - ``question`` (str): 要检索的用户问题
        - ``expect_name`` (str): 预期景点名，须与 ``v2.attractions.name`` 完全一致
        - ``expect_theme`` (str): 预期主题代号，如 ``visit_tips``、``facilities``、
          ``preferential``、``overview``、``history_culture``、``notice``、
          ``entry_policy``

    Raises:
        FileNotFoundError: ``path`` 不存在。
        json.JSONDecodeError: 某行不是合法 JSON。
        UnicodeDecodeError: 文件不是合法 UTF-8。
    """
    cases: list[dict] = []
    for line_no, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            cases.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise json.JSONDecodeError(
                f"{path}:{line_no}: {exc.msg}",
                exc.doc,
                exc.pos,
            ) from exc
    return cases


def is_hit(
    results: list[dict],
    *,
    expect_name: str,
    expect_theme: str,
) -> bool:
    """判断检索结果是否命中预期的「景点名 + 主题」。

    Args:
        results: :func:`search_chunks.search` 返回的字典列表（通常已截断为 top-k）。
        expect_name: 期望的景点中文名，与库中 ``name`` 字段精确匹配。
        expect_theme: 期望的主题代号，与库中 ``theme`` 字段精确匹配。

    Returns:
        bool: 若 ``results`` 中存在同时匹配名称与主题的条目则为 ``True``，否则 ``False``。
    """
    return any(
        r.get("name") == expect_name and r.get("theme") == expect_theme
        for r in results
    )


def main() -> int:
    """命令行入口：跑完全部用例并打印 hit@k 与未命中明细。

    会先 :func:`load_model` 一次，再对每题调用 :func:`retrieval.search_chunks.search`，
    避免每题重新加载 BGE-M3。

    Returns:
        int: 进程退出码；成功跑完为 ``0``（即使存在 MISS 也不视为进程失败，
        以便脚本持续输出完整报告）。
    """
    parser = argparse.ArgumentParser(
        description="向量检索 hit@k 小评测（不调用回答 LLM）"
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "cases" / "eval_questions.jsonl",
        help="评测用例 JSONL 路径，默认 eval/cases/eval_questions.jsonl",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="每题取前 k 条判断是否命中，默认 3（即 hit@3）",
    )
    args = parser.parse_args()

    load_env_files()
    cases = load_cases(args.questions)
    if not cases:
        print(f"无有效用例: {args.questions}", file=sys.stderr)
        return 2

    # 模型只加载一次，供全部问题复用
    model = load_model()
    hits = 0
    misses: list[dict] = []

    for i, case in enumerate(cases, 1):
        q = case["question"]
        expect_name = case["expect_name"]
        expect_theme = case["expect_theme"]
        results = search(q, top_k=args.top_k, model=model)
        matched = is_hit(
            results, expect_name=expect_name, expect_theme=expect_theme
        )
        status = "HIT" if matched else "MISS"
        if matched:
            hits += 1
        else:
            # 记录未命中，便于事后对照：是切块主题不对，还是同名/近义 POI 干扰
            misses.append(
                {
                    "question": q,
                    "expect": f"{expect_name}/{expect_theme}",
                    "got": [
                        f"{r.get('name')}/{r.get('theme')}@{float(r['similarity']):.3f}"
                        for r in results
                    ],
                }
            )
        print(
            f"[{i}/{len(cases)}] {status}  expect={expect_name}/{expect_theme}  Q={q}",
            flush=True,
        )
        for j, r in enumerate(results, 1):
            print(
                f"    {j}. {r.get('name')}/{r.get('theme')} "
                f"sim={float(r['similarity']):.4f}",
                flush=True,
            )

    rate = hits / len(cases)
    print()
    print(f"hit@{args.top_k}: {hits}/{len(cases)} = {rate:.1%}")
    if misses:
        print("misses:")
        for m in misses:
            print(f"  - {m['question']}")
            print(f"    expect: {m['expect']}")
            print(f"    got:    {', '.join(m['got'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
