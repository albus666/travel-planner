"""Frozen synthetic challenge: store routing and live answers scored separately."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
SQL = 'v2.poi_details.ticket_raw'
RAG = 'v2.rag_chunks'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def store_metrics(rows):
    single = [r for r in rows if len(r['case']['expected_stores']) == 1]
    return {
        'single_store_count': len(single),
        'single_store_correct': sum(r['store_correct'] is True for r in single),
        'ticket_false_positive': sum(r['case']['expected_stores'] == [RAG] and r['predicted_store'] == SQL for r in single),
        'ticket_false_negative': sum(r['case']['expected_stores'] == [SQL] and r['predicted_store'] != SQL for r in single),
        'mixed_count': len(rows) - len(single),
        'mixed_full_store_coverage': sum(r['store_correct'] is True for r in rows if len(r['case']['expected_stores']) > 1),
        'answer_quality': 'pending_human_review',
    }


def render(report):
    lines = ['# 路由 v2：新增30题合成挑战集', '',
        '题目由代理生成，标签在运行前固定、待用户审核；未用本轮结果修改规则或阈值。不是来自真实用户的独立盲测。', '',
        '单store选择与回答质量分开。混合问题需要两个store，单一路径不能计为完整通过。实体解析不等于是否正确澄清；拒答和时效性需读回答后人工评分。', '',
        '自动统计：`' + json.dumps(report['summary'], ensure_ascii=False) + '`', '',
        '人工项填写 pass / fail / na：事实、引用、景点隔离、拒答、时效、要点覆盖；失败再标注路由/实体/SQL/生成/数据/能力缺口。', '']
    for row in report['cases']:
        case = row['case']
        lines += [f"## {case['id']} · {case['category']}", '', case['question'], '',
            '预期store：' + ' + '.join(case['expected_stores']),
            '', '预期行为：' + case['expected_behavior'], '',
            f"实际分类：{row['predicted_store']}；{row['method']}；{row['reason']}", '',
            'store完整匹配：' + str(row['store_correct']), '',
            '回答：', '', row['response']['answer'], '',
            '引用及取回片段（核对回答依据）：', '', '```json',
            json.dumps({k: row['response'].get(k) for k in ('status','route','structured_data','citations','retrieved_sources','warnings')}, ensure_ascii=False, indent=2),
            '```', '', '人工评分：事实 __；引用 __；景点隔离 __；拒答 __；时效 __；覆盖 __；归因 __', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--freeze', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix('.md').exists() or args.freeze.exists():
        parser.error('Refusing to overwrite a result or frozen baseline')
    cases = [json.loads(line) for line in args.cases.read_text(encoding='utf-8').splitlines() if line.strip()]
    if not cases or len({c['id'] for c in cases}) != len(cases):
        parser.error('Empty dataset or duplicate IDs')
    if any(not c['expected_stores'] or not set(c['expected_stores']) <= {SQL,RAG} for c in cases):
        parser.error('Invalid expected store label')
    from retrieval.search_chunks import load_env_files, require_database_url
    load_env_files()
    from service.semantic_router import classify_for_request, semantic_enabled
    from service.ticket_service import CATALOG_SQL, resolve_poi
    import psycopg
    if not semantic_enabled():
        parser.error('Current semantic routing must be enabled')
    files = ['rag/service/' + name for name in ('intent_classifier.py','store_contract.py','semantic_router.py',
        'routing_prototypes.json','ticket_service.py','retrieval_server.py','answer_service.py')]
    files += ['rag/retrieval/search_chunks.py', 'rag/eval/cases/routing_store_v1.jsonl',
        'rag/eval/reports/routing_semantic_candidate_v2.json', 'rag/eval/reports/routing_v2_live_regression.json']
    args.freeze.mkdir(parents=True)
    manifest = {'version': 'routing-v2-frozen-before-challenge', 'files': {},
        'routing_enabled': True, 'dataset_sha256': digest(args.cases), 'no_secrets_archived': True,
        'config': json.loads((ROOT/'rag/service/routing_prototypes.json').read_text()),
        'dataset_origin': 'agent_generated_synthetic_not_real_user_blind'}
    for name in files:
        dest = args.freeze/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, dest)
        manifest['files'][name] = digest(ROOT/name)
    shutil.copyfile(args.cases, args.freeze/'challenge_cases.jsonl')
    (args.freeze/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    with psycopg.connect(require_database_url(), options='-c default_transaction_read_only=on') as conn:
        catalog = conn.execute(CATALOG_SQL).fetchall()
    rows = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for case in cases:
        intent, _ = classify_for_request(case['question'])
        target = resolve_poi(case['question'], catalog)
        req = urllib.request.Request('http://127.0.0.1:8100/ask',
            data=json.dumps({'question':case['question']}).encode(), headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req, timeout=120) as response:
            answer = json.load(response)
        actual = SQL if answer['route'] == 'sql_ticket' else RAG
        entity_ok = None
        if case['expected_resolution'] == 'unresolved':
            entity_ok = target is None
        elif case['expected_resolution'] == 'resolved':
            entity_ok = target is not None and target[0] == case['expected_poi_id']
        rows.append({'case':case, 'predicted_store':intent.store.value, 'method':intent.method,
            'reason':intent.reason, 'store_correct':case['expected_stores'] == [intent.store.value],
            'resolved_poi_id':target[0] if target else None, 'entity_resolution_correct':entity_ok,
            'live_store':actual, 'live_matches_classifier':actual == intent.store.value,
            'response':answer, 'human_review':None})
        report = {'baseline_manifest':manifest, 'summary':store_metrics(rows), 'cases':rows,
            'run_complete':len(rows)==len(cases), 'labels_review_status':'agent_authored_pending_user_review'}
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        args.output.with_suffix('.md').write_text(render(report), encoding='utf-8')
        print(json.dumps({'id':case['id'],'store_correct':rows[-1]['store_correct'],
            'method':intent.method,'route':answer['route'],'status':answer['status']},ensure_ascii=False),flush=True)
    changed = [name for name, sha in manifest['files'].items() if digest(ROOT/name) != sha]
    if changed:
        raise RuntimeError('Frozen source changed during run: ' + repr(changed))
    print(json.dumps(report['summary'], ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
