"""Live SQL-route checks against raw DB values, never an LLM self-score."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

import psycopg
from retrieval.search_chunks import require_database_url

ROOT = Path(__file__).resolve().parents[3]
CASES = [
    ('longmen_raw','龙门石窟的门票资料记载是什么？',77498,'answered'),
    ('laojun_raw','老君山景区门票原文是什么？',77806,'answered'),
    ('free_raw','隋唐城遗址植物园的票价资料是什么？',11078925,'answered'),
    ('qualifier_raw','陆浑旅游风景区门票资料原文是什么？',13665171,'answered'),
    ('empty_ticket','天子驾六博物馆门票资料是什么？',82477,'insufficient_evidence'),
    ('empty_museum','洛阳龙门博物馆门票资料记载是什么？',56309164,'insufficient_evidence'),
    ('ambiguous','龙门门票多少钱？',None,'insufficient_evidence'),
    ('unknown','洛阳银河天梯公园门票价格资料是什么？',None,'insufficient_evidence'),
    ('today','龙门石窟今天成人门票准确多少钱？',77498,'insufficient_evidence'),
    ('multi','龙门石窟和凤翔温泉门票资料分别是什么？',None,'insufficient_evidence'),
]


def snapshot(conn):
    rows=conn.execute('SELECT poi_id,ticket_raw,detail_meta,collected_at,verify_status FROM v2.poi_details ORDER BY poi_id').fetchall()
    return hashlib.sha256(json.dumps(rows,ensure_ascii=False,default=str).encode()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8100/ask')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): parser.error('Output already exists')
    versions={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (
        'rag/service/ticket_service.py','rag/service/retrieval_server.py','rag/service/answer_service.py','rag/retrieval/search_chunks.py')}
    rows=[]
    with psycopg.connect(require_database_url(),options='-c default_transaction_read_only=on') as conn:
        readonly=conn.execute('SHOW transaction_read_only').fetchone()[0]
        assert readonly=='on'
        before=snapshot(conn)
        for case_id,question,poi_id,status in CASES:
            req=urllib.request.Request(args.url,data=json.dumps({'question':question}).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=120) as response: result=json.load(response)
            checks={'sql_route':result['route']=='sql_ticket','expected_behavior':result['status']==status,
                    'no_vector_chunks':result['retrieved_sources']==[]}
            if poi_id:
                expected=conn.execute('SELECT ticket_raw FROM v2.poi_details WHERE poi_id=%s',(poi_id,)).fetchone()[0]
                checks['correct_poi']=result['structured_data']['poi_id']==poi_id
                checks['raw_field_exact']=result['structured_data']['ticket_raw']==expected
                checks['has_source_and_time']=bool(result['structured_data']['source_url'] and result['structured_data']['collected_at'])
                checks['snapshot_warning']=any('快照' in warning for warning in result['warnings'])
                if expected:
                    checks['raw_in_answer']=expected in result['answer']
                    checks['quote_exact']=result['citations'][0]['quotes']==[expected]
                else:
                    checks['no_free_inference']='不能据此推断免费' in result['answer'] and not result['citations']
            else:
                checks['no_unresolved_price']=result['structured_data'] is None and not result['citations']
            rows.append({'id':case_id,'question':question,'response':result,'checks':checks,'passed':all(checks.values())})
            print(json.dumps({'id':case_id,'checks':checks,'answer':result['answer']},ensure_ascii=False),flush=True)
        after=snapshot(conn)
    report={'versions':versions,'transaction_read_only':readonly,'snapshot_before':before,'snapshot_after':after,
            'data_unchanged':before==after,'cases':rows,'passed':sum(r['passed'] for r in rows),'total':len(rows)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if before!=after or not all(r['passed'] for r in rows): raise SystemExit('SQL-route evaluation failed')


if __name__ == '__main__': main()
