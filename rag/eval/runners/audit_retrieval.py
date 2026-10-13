"""Audit the running retriever without changing it; save complete ranked evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import urllib.request


def first_rank(hits, case, strict=True):
    return next((i for i, h in enumerate(hits, 1)
                 if h['name'] == case['expect_name']
                 and (not strict or h['theme'] == case['expect_theme'])), None)


def metrics(rows, key):
    ranks = [first_rank(row[key], row) for row in rows]
    poi_ranks = [first_rank(row[key], row, False) for row in rows]
    n = len(rows)
    return {
        'count': n,
        'strict_hit@1': sum(r == 1 for r in ranks) / n,
        'strict_hit@3': sum(r is not None and r <= 3 for r in ranks) / n,
        'strict_mrr@20': sum(1 / r if r else 0 for r in ranks) / n,
        'poi_hit@3': sum(r is not None and r <= 3 for r in poi_ranks) / n,
    }


def prefer_explicit_poi(question, hits, names):
    # Conservative experiment: longest literal catalog name, plus one explicit alias.
    # No parent/child inference and no theme changes.
    matches = [name for name in names if len(name) >= 2 and name in question]
    if not matches and '龙门' in question:
        matches = ['龙门石窟']
    if not matches:
        return list(hits), None
    longest = max(map(len, matches))
    targets = {name for name in matches if len(name) == longest}
    if len(targets) != 1:
        return list(hits), None
    target = next(iter(targets))
    return sorted(hits, key=lambda h: h['name'] != target), target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--questions', type=Path, default=Path(__file__).resolve().parents[1] / 'cases/eval_questions.jsonl')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--catalog', type=Path, required=True, help='JSON list of real catalog names, independent of evaluation labels')
    parser.add_argument('--url', default='http://127.0.0.1:8100/search')
    args = parser.parse_args()
    names = json.loads(args.catalog.read_text(encoding='utf-8'))
    cases = [json.loads(line) for line in args.questions.read_text(encoding='utf-8').splitlines()
             if line.strip() and not line.lstrip().startswith('#')]
    if not cases:
        parser.error('No evaluation cases')
    rows = []
    for case in cases:
        request = urllib.request.Request(args.url, data=json.dumps({'question': case['question'], 'top_k': 20}).encode(),
                                         headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(request, timeout=120) as response:
            hits = json.load(response)['hits']
        reranked, target = prefer_explicit_poi(case['question'], hits, names)
        rows.append({**case, 'baseline': hits, 'poi_preferred': reranked, 'identified_poi': target,
                     'baseline_rank': first_rank(hits, case), 'experiment_rank': first_rank(reranked, case)})
    summary = {key: metrics(rows, key) for key in ('baseline', 'poi_preferred')}
    summary['regressions_at_3'] = [r['question'] for r in rows if r['baseline_rank'] is not None
                                  and r['baseline_rank'] <= 3 and (r['experiment_rank'] is None or r['experiment_rank'] > 3)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'summary': summary, 'cases': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for row in rows:
        if row['baseline_rank'] is None or row['baseline_rank'] > 3:
            print(json.dumps({k: row[k] for k in ('question', 'expect_name', 'expect_theme', 'baseline_rank', 'experiment_rank', 'identified_poi')}, ensure_ascii=False))
            print(json.dumps([{k: h[k] for k in ('name', 'theme', 'similarity')} for h in row['baseline'][:3]], ensure_ascii=False))


if __name__ == '__main__':
    main()
