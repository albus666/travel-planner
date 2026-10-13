"""Prototype routing experiment; choose thresholds using dev only, then holdout."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import psycopg
from retrieval.search_chunks import load_model,encode_query,require_database_url
from service.intent_classifier import Store,classify_intent
from service.semantic_router import SemanticRouter
from service.store_contract import boundary_intent
from eval.runners.run_routing_eval import evaluate

ROOT=Path(__file__).resolve().parents[3]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): parser.error('Output already exists')
    path=ROOT/'rag/eval/cases/routing_store_v1.jsonl'
    cases=[json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]
    config_path=ROOT/'rag/service/routing_prototypes.json'
    config=json.loads(config_path.read_text())
    assert not ({c['question'] for c in cases} & {e['text'] for e in config['examples']})
    model=load_model()
    seed_result=model.encode([e['text'] for e in config['examples']],batch_size=8,max_length=8192,
        return_dense=True,return_sparse=False,return_colbert_vecs=False)
    vectors={}; timings={}
    for case in cases:
        start=time.perf_counter()
        vectors[case['question']]=encode_query(model,case['question'])
        timings[case['question']]=(time.perf_counter()-start)*1000
    with psycopg.connect(require_database_url(),options='-c default_transaction_read_only=on') as conn:
        catalog=conn.execute('SELECT poi_id,name FROM v2.attractions ORDER BY poi_id').fetchall()
    dev=[c for c in cases if c['split']=='dev']
    candidates=[]
    for threshold in (0.45,0.50,0.55,0.60,0.65,0.70):
        for margin in (0.00,0.02,0.04,0.06,0.08):
            router=SemanticRouter(config['examples'],seed_result['dense_vecs'],threshold,margin)
            report=evaluate(dev,lambda q:router.classify(q,vectors[q]),catalog)
            score=report['metrics']['all']
            candidates.append({'threshold':threshold,'margin':margin,'dev_metrics':score})
    # Conservative threshold selection prioritizes zero false-positive SQL access.
    best=max(candidates,key=lambda c:(-c['dev_metrics']['ticket_fp'],c['dev_metrics']['ticket_tp'],c['threshold'],c['margin']))
    router=SemanticRouter(config['examples'],seed_result['dense_vecs'],best['threshold'],best['margin'])
    result=evaluate(cases,lambda q:router.classify(q,vectors[q]),catalog)
    original=[]
    for filename in ('answer_holdout_v1.jsonl','eval_questions.jsonl'):
        for line in (ROOT/'rag/eval/cases'/filename).read_text(encoding='utf-8').splitlines():
            if not line.strip() or line.lstrip().startswith('#'): continue
            case=json.loads(line); q=case['question']
            if q not in vectors: vectors[q]=encode_query(model,q)
            decision=router.classify(q,vectors[q])
            original.append({'question':q,'legacy_store':classify_intent(q).store.value,
                             'candidate_store':decision.store.value,'unchanged':decision.store==classify_intent(q).store})
    result['historical_98_store_regression']={'count':len(original),'changes':sum(not r['unchanged'] for r in original),'cases':original}
    score_rows=[]
    for case in cases:
        p,n=router.scores(vectors[case['question']])
        score_rows.append({'id':case['id'],'ticket_knn_score':p,'rag_knn_score':n,'margin':p-n,
                           'boundary_guard':boundary_intent(case['question']).reason if boundary_intent(case['question']) else None})
    result.update({'selected_on_dev_only':best,'threshold_candidates':candidates,'scores':score_rows,
        'dataset_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'prototype_sha256':hashlib.sha256(config_path.read_bytes()).hexdigest(),
        'encode_ms_median':float(np.median(list(timings.values()))),'encode_ms_p95':float(np.percentile(list(timings.values()),95)),
        'note':'Synthetic developer benchmark, no claim of production accuracy; holdout not used to select threshold'})
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'selected':best,'metrics':result['metrics'],'encode_ms_median':result['encode_ms_median']},ensure_ascii=False,indent=2))
    for row in result['cases']:
        if not row['store_correct']: print(json.dumps(row,ensure_ascii=False))


if __name__=='__main__': main()
