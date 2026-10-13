"""Online routing smoke and strict 25/73 baseline regression, no self-scoring."""
import argparse
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[3]


def post(endpoint,body):
    req=urllib.request.Request('http://127.0.0.1:8100/'+endpoint,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=120) as response:return json.load(response)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error('Output exists')
    cases=[('龙门石窟进去要花多少钱？','sql_ticket',77498),
           ('凤翔温泉入场要付多少？','sql_ticket',10615019),
           ('老君山景区票钱大概多少？','sql_ticket',77806),
           ('龙门进去要花多少钱？','sql_ticket',None),
           ('洛阳星河漫游馆进去花多少钱？','sql_ticket',None),
           ('龙门石窟门票退票公告原文是什么？','vector',None),
           ('龙门石窟门票优待政策资料是什么？','vector',None),
           ('龙门石窟实名制分时购票怎么规定的？','vector',None)]
    smoke=[]
    for question,route,poi_id in cases:
        response=post('ask',{'question':question})
        assert response['route']==route,question
        if route=='sql_ticket':
            if poi_id:assert response['structured_data']['poi_id']==poi_id
            else:assert response['structured_data'] is None and response['status']=='insufficient_evidence'
        smoke.append({'question':question,'response':response})
        print(json.dumps({'question':question,'route':response['route'],'status':response['status'],'elapsed_ms':response['elapsed_ms']},ensure_ascii=False),flush=True)
    old=json.loads((ROOT/'rag/eval/reports/answer_holdout_v1_2026-10-12_run3_sql.json').read_text())
    regress=[]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    for row in old['cases']:
        question=row['case']['question'];response=post('ask',{'question':question})
        baseline=row['response']
        before=[(h['chunk_id'],h['similarity']) for h in baseline['retrieved_sources']]
        after=[(h['chunk_id'],h['similarity']) for h in response['retrieved_sources']]
        assert response['route']=='vector' and before==after,question
        regress.append({'id':row['case']['id'],'response':response,'store_and_context_unchanged':True,
                        'answer_text_changed':baseline['answer']!=response['answer'],'human_review':None})
        args.output.write_text(json.dumps({'smoke':smoke,'answer_regression':regress,'human_review_status':'pending'},ensure_ascii=False,indent=2),encoding='utf-8')
    retrieval=json.loads((ROOT/'deploy/backups/ask-2026-10-12/retrieval_baseline.json').read_text())
    for case in retrieval['cases']:
        response=post('search',{'question':case['question'],'top_k':20})
        assert [(h['chunk_id'],h['similarity']) for h in response['hits']]==[(h['chunk_id'],h['similarity']) for h in case['baseline']],case['question']
    result={'smoke':smoke,'answer_regression':regress,'summary':{'smoke_passed':len(smoke),
            'answer_store_and_context_unchanged':25,'search_top20_unchanged':73,
            'answer_quality_not_auto_scored':True,'human_review_status':'pending'}}
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result['summary'],ensure_ascii=False))


if __name__=='__main__':main()
