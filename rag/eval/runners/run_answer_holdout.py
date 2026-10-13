"""Capture held-out answers, frozen versions and unfilled human rating fields."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request

import psycopg

ROOT = Path(__file__).resolve().parents[3]
DIMENSIONS = ('factual_support', 'citation_support', 'poi_isolation', 'refusal_correct',
              'freshness_correct', 'point_coverage')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configuration():
    import os
    for line in (ROOT / '.env').read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    # Only return non-secret metadata.
    return os.environ.get('DATABASE_URL'), {'model': os.environ.get('LLM_MODEL'),
                                            'base_url': os.environ.get('LLM_BASE_URL')}


def versions(dataset):
    paths = ('rag/retrieval/search_chunks.py', 'rag/service/retrieval_server.py', 'rag/service/answer_service.py')
    result = {p: digest(ROOT / p) for p in paths}
    ticket_module = ROOT / 'rag/service/ticket_service.py'
    if ticket_module.exists():
        result['rag/service/ticket_service.py'] = digest(ticket_module)
    tree = ast.parse((ROOT / paths[-1]).read_text(encoding='utf-8'))
    prompt = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'PROMPT' for t in n.targets))
    result['prompt_sha256'] = hashlib.sha256(prompt.encode()).hexdigest()
    result['dataset_sha256'] = digest(dataset)
    return result


def source_snapshot(database_url, cases):
    with psycopg.connect(database_url) as conn:
        rows = conn.execute('SELECT c.chunk_id, c.poi_id, a.name, c.theme, c.text, c.source_url, '
            'c.collected_at, c.verify_status, md5(c.embedding::text) FROM v2.rag_chunks c '
            'JOIN v2.attractions a ON a.poi_id=c.poi_id ORDER BY c.chunk_id').fetchall()
    by_id = {r[0]: r for r in rows}
    for case in cases:
        for reference in case['reference_evidence']:
            actual = by_id.get(reference['chunk_id'])
            if not actual or (actual[1], actual[2], actual[3], actual[4]) != (
                    reference['poi_id'], reference['name'], reference['theme'], reference['text']):
                raise ValueError('Reference snapshot mismatch: ' + reference['chunk_id'])
    encoded = json.dumps(rows, ensure_ascii=False, default=str, separators=(',', ':')).encode()
    return {'count': len(rows), 'content_provenance_embedding_sha256': hashlib.sha256(encoded).hexdigest()}


def write_report(path, report):
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    parts = ['# 回答评测人工评分表', '',
        '此表尚未人工评分。pass/fail/na；拒答和回答状态不自动换算为准确率。引用原文存在不等于语义支持。', '',
        '逐题填写 JSON 中 human_review：事实支持、引用支持、景点隔离、拒答正确性、时效性、要点覆盖；',
        'attribution 填 retrieval/generation/data/mixed/unknown，notes 说明依据。', '']
    for row in report['cases']:
        case, response = row['case'], row.get('response') or {}
        parts.extend([f"## {case['id']} · {case['category']}", '', case['question'], '',
            '**预期要点**：' + '；'.join(case['expected_points']), '',
            f"**预期拒答**：{case['should_refuse']}；**实际状态**：{response.get('status', 'request_error')}", '',
            '**答案**：', '', response.get('answer', row.get('error', '')), '',
            '**系统提示**：' + '；'.join(response.get('warnings', [])), '', '**引用证据**：', ''])
        for citation in response.get('citations', []):
            parts.extend([f"- {citation['source_id']} {citation['name']}/{citation['theme']} · {citation.get('collected_at')}",
                          '  摘录：' + '；'.join(citation.get('quotes', []))])
        parts.extend(['', '**检索片段**：' + '；'.join(f"{s['source_id']} {s['name']}/{s['theme']}" for s in response.get('retrieved_sources', [])), '',
            '| 事实支持 | 引用支持 | 景点隔离 | 拒答正确 | 时效正确 | 要点覆盖 | 归因 |',
            '|---|---|---|---|---|---|---|', '| 待评 | 待评 | 待评 | 待评 | 待评 | 待评 | 待评 |', ''])
    path.with_suffix('.md').write_text('\n'.join(parts), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--questions', type=Path, default=ROOT / 'rag/eval/cases/answer_holdout_v1.jsonl')
    parser.add_argument('--url', default='http://127.0.0.1:8100/ask')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Refusing to overwrite an existing run')
    cases = [json.loads(line) for line in args.questions.read_text(encoding='utf-8').splitlines() if line.strip()]
    if not cases or len({c['id'] for c in cases}) != len(cases):
        parser.error('Empty dataset or duplicate case IDs')
    manifest_path = args.questions.with_suffix('.manifest.json')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest['dataset_sha256'] != digest(args.questions):
        parser.error('Frozen dataset hash mismatch')
    database_url, llm = configuration()
    before = versions(args.questions)
    snapshot = source_snapshot(database_url, cases)
    report = {'metadata': {'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'dataset_manifest': manifest, 'versions_before': before, 'llm': llm, 'top_k': 5,
        'source_snapshot_before': snapshot, 'human_review_status': 'pending'}, 'cases': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_report(args.output, report)
    for case in cases:
        row = {'case': case, 'human_review': {**{d: None for d in DIMENSIONS}, 'attribution': None, 'notes': None}}
        req = urllib.request.Request(args.url, data=json.dumps({'question': case['question'], 'top_k': 5}).encode(),
                                     headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                row['response'] = json.load(response)
            actual = {s['chunk_id'] for s in row['response']['retrieved_sources']}
            expected = set(case['expected_sources'])
            row['diagnostics'] = {'expected_sources_in_context': sorted(actual & expected),
                'expected_sources_missing': sorted(expected - actual),
                'status_matches_refusal_label': (row['response']['status'] == 'insufficient_evidence') == case['should_refuse'],
                'not_accuracy_score': True}
        except urllib.error.HTTPError as exc:
            row['error'] = f'HTTP {exc.code}'
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError):
            row['error'] = 'Transport or response-format error'
        report['cases'].append(row)
        write_report(args.output, report)
        print(json.dumps({'id': case['id'], 'status': row.get('response', {}).get('status'),
                          'diagnostics': row.get('diagnostics'), 'error': row.get('error')}, ensure_ascii=False), flush=True)
    after = versions(args.questions)
    snapshot_after = source_snapshot(database_url, cases)
    report['metadata'].update({'finished_at_utc': datetime.now(timezone.utc).isoformat(),
        'versions_after': after, 'source_snapshot_after': snapshot_after,
        'frozen_state_unchanged': before == after and snapshot == snapshot_after})
    report['summary'] = {'cases': len(cases), 'response_status_counts': dict(Counter(
        r.get('response', {}).get('status', 'request_error') for r in report['cases'])),
        'human_reviewed': 0, 'answer_accuracy': None}
    write_report(args.output, report)
    print(json.dumps(report['summary'], ensure_ascii=False))
    if not report['metadata']['frozen_state_unchanged']:
        raise SystemExit('Frozen state changed during run')


if __name__ == '__main__':
    main()
