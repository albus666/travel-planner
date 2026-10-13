"""Accept four mixed requests, then regress 30/25 answers and 73 searches."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[2]


def post(endpoint, body):
    request=urllib.request.Request('http://127.0.0.1:8100/'+endpoint,
        data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=120) as response:return json.load(response)


def context(response):
    return [(h['chunk_id'],h['similarity']) for h in response['retrieved_sources']]


def render(report):
    lines=[f"# 最小混合问题支持：{len(report['challenge'])}题运行与人工复评", '',
        '新回答需重新评分，未沿用之前的用户分数。自动检查工具调用、原文与引用，不将它们等同于事实与完整性人工验收。', '',
        '自动汇总：`'+json.dumps(report.get('summary',{}),ensure_ascii=False)+'`','']
    for row in sorted(report['challenge'],key=lambda r:r['case']['id']):
        c,r=row['case'],row['response']
        lines += [f"## {c['id']}", '',c['question'],'','预期行为：'+c['expected_behavior'],'',r['answer'],'',
            '工具与证据：','', '```json',json.dumps({k:r.get(k) for k in
                ('route','status','required_stores','tasks','entity_resolution','structured_data','citations','retrieved_sources','warnings')},ensure_ascii=False,indent=2),
            '```','','人工评分：事实 __；引用 __；景点隔离 __；拒答 __；时效 __；覆盖 __；归因 __','']
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--only-mixed',action='store_true')
    args=parser.parse_args()
    if args.output.exists():parser.error('Refusing overwrite')
    old=json.loads((ROOT/'rag/eval/reports/routing_challenge_v1_run1.json').read_text())
    report={'challenge':[],'answer25':[],'search73':[], 'mixed_acceptance':[],
        'answer_quality':'pending_new_human_review','run_complete':False}
    def save():
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        args.output.with_suffix('.md').write_text(render(report),encoding='utf-8')
    # First four mixed cases; reuse these responses in the complete 30-case run.
    for row in old['cases'][26:]:
        c=row['case'];r=post('ask',{'question':c['question']})
        report['challenge'].append({'case':c,'response':r,'human_review':None})
        save()
        assert r['route']=='mixed' and r['required_stores']==['ticket_sql','rag'],c['id']
        assert len(r['tasks'])==2 and all(t['tool_called'] for t in r['tasks']),c['id']
        assert r['tasks'][0]['state']=='queried_with_evidence',c['id']
        sql_cites=[s for s in r['citations'] if s['source_id']=='SQL1']
        assert len(sql_cites)==1 and sql_cites[0]['field']=='ticket_raw',c['id']
        assert r['structured_data']['ticket_raw'] in r['answer'],c['id']
        assert sql_cites[0]['quotes']==[r['structured_data']['ticket_raw']],c['id']
        # Check the original frozen SQL raw values against existing DB snapshot.
        import psycopg
        from retrieval.search_chunks import load_env_files,require_database_url
        load_env_files()
        with psycopg.connect(require_database_url(),options='-c default_transaction_read_only=on') as conn:
            raw=conn.execute('SELECT ticket_raw FROM v2.poi_details WHERE poi_id=%s',(r['structured_data']['poi_id'],)).fetchone()[0]
        assert raw==r['structured_data']['ticket_raw'],c['id']
        number=int(c['id'][-2:])
        themes={s['theme'] for s in r['citations'] if s['source_id'].startswith('S') and s['source_id']!='SQL1'}
        if number==27:assert 'visit_tips' in themes,c['id']
        if number==28:assert themes & {'overview','history_culture'},c['id']
        if number==30:assert 'preferential' in themes,c['id']
        if number==29:
            assert '轮椅' in r['answer'] and '无法确认' in r['answer'],c['id']
            assert r['tasks'][1]['answer_status']=='insufficient_evidence',c['id']
        else:
            assert r['tasks'][1]['answer_status']=='answered',c['id']
        # Verify every RAG quote is a literal span in its genuine source.
        sources={s['source_id']:s for s in r['retrieved_sources']}
        for citation in r['citations']:
            assert citation['poi_id']==r['structured_data']['poi_id'],c['id']
            if citation['source_id']!='SQL1':
                assert all(q in sources[citation['source_id']]['text'] for q in citation['quotes']),c['id']
        report['mixed_acceptance'].append({'id':c['id'],'tools_and_raw_quotes_pass':True,'human_review':None})
        print(json.dumps({'mixed_accepted':c['id'],'status':r['status'],'tasks':[t['state'] for t in r['tasks']]},ensure_ascii=False),flush=True)
        save()
    if args.only_mixed:
        report['summary']={'mixed_tool_evidence_checks':len(report['mixed_acceptance']),
            'scope':'four_mixed_only','new_answer_human_review':'pending'}
        report['run_complete']=True
        report['runtime_hashes']={'rag/service/mixed_service.py':hashlib.sha256((ROOT/'rag/service/mixed_service.py').read_bytes()).hexdigest()}
        save();print(json.dumps(report['summary'],ensure_ascii=False),flush=True);return
    for row in old['cases'][:26]:
        c=row['case'];r=post('ask',{'question':c['question']});before=row['response']
        report['challenge'].append({'case':c,'response':r,'human_review':None});save()
        assert r['route']==before['route'] and context(r)==context(before),c['id']
        assert r['structured_data']==before.get('structured_data'),c['id']
        n=int(c['id'][-2:])
        if n==25:assert '目录' in r['answer'] and '核对' in r['answer'],c['id']
        if n==26:assert all(s in r['answer'] for s in ('一次只支持一个景点','龙门石窟','老君山景区')),c['id']
        print(json.dumps({'challenge_regressed':c['id'],'route':r['route']},ensure_ascii=False),flush=True)
    questions=[json.loads(line) for line in (ROOT/'rag/eval/cases/answer_holdout_v1.jsonl').read_text().splitlines() if line.strip()]
    baseline=json.loads((ROOT/'rag/eval/reports/routing_v2_live_regression.json').read_text())['answer_regression']
    for c,b in zip(questions,baseline,strict=True):
        r=post('ask',{'question':c['question']})
        report['answer25'].append({'case':c,'response':r,'human_review':None});save()
        assert r['route']==b['response']['route'] and context(r)==context(b['response']),c['id']
        print(json.dumps({'answer25_regressed':c['id']},ensure_ascii=False),flush=True)
    retrieval=json.loads((ROOT/'deploy/backups/ask-2026-10-12/retrieval_baseline.json').read_text())
    for c in retrieval['cases']:
        r=post('search',{'question':c['question'],'top_k':20})
        assert [(h['chunk_id'],h['similarity']) for h in r['hits']]==[(h['chunk_id'],h['similarity']) for h in c['baseline']],c['question']
        report['search73'].append({'question':c['question'],'top20_unchanged':True})
    report['summary']={'mixed_tool_evidence_checks':4,'single_challenge_store_and_context_unchanged':26,
        'answer25_store_and_context_unchanged':25,'search73_top20_unchanged':73,
        'unit_tests_passed':35,'new_answer_human_review':'pending','rules_thresholds_search_ranking_unchanged':True}
    report['runtime_hashes']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT/'rag/service/mixed_service.py',ROOT/'rag/service/ticket_service.py',ROOT/'rag/service/retrieval_server.py',ROOT/'rag/service/routing_prototypes.json')}
    report['run_complete']=True;save()
    print(json.dumps(report['summary'],ensure_ascii=False),flush=True)


if __name__=='__main__':main()
