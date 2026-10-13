"""No LLM calls: measure store classification independently of entity resolution."""
import argparse
from collections import Counter
import hashlib
import inspect
import json
from pathlib import Path

import psycopg
from retrieval.search_chunks import require_database_url
from service.intent_classifier import classify_intent,Store
from service.ticket_service import resolve_poi

ROOT=Path(__file__).resolve().parents[3]


def evaluate(cases, classifier, catalog):
    rows=[]
    for case in cases:
        intent=classifier(case['question'])
        target=resolve_poi(case['question'],catalog) if case['expected_resolution']!='not_applicable' else None
        entity_ok=case['expected_resolution']=='not_applicable' or (
            target is None if case['expected_resolution']=='unresolved' else target is not None and target[0]==case['expected_poi_id'])
        rows.append({**case,'predicted_store':intent.store.value,'method':intent.method,
            'store_correct':intent.store.value==case['expected_store'],'entity_correct':entity_ok,
            'resolved_poi_id':target[0] if target else None})
    def metrics(group):
        tp=sum(r['expected_store']==Store.TICKET_RAW.value and r['predicted_store']==Store.TICKET_RAW.value for r in group)
        fp=sum(r['expected_store']!=Store.TICKET_RAW.value and r['predicted_store']==Store.TICKET_RAW.value for r in group)
        fn=sum(r['expected_store']==Store.TICKET_RAW.value and r['predicted_store']!=Store.TICKET_RAW.value for r in group)
        return {'count':len(group),'correct':sum(r['store_correct'] for r in group),'ticket_tp':tp,'ticket_fp':fp,'ticket_fn':fn,
                'ticket_precision':tp/(tp+fp) if tp+fp else None,'ticket_recall':tp/(tp+fn) if tp+fn else None,
                'entity_errors':sum(not r['entity_correct'] for r in group)}
    groups={name:metrics([r for r in rows if r['split']==name]) for name in ('dev','holdout')}
    groups['all']=metrics(rows)
    groups['paraphrase']=metrics([r for r in rows if r['category']=='paraphrase'])
    return {'metrics':groups,'cases':rows}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--questions',type=Path,default=ROOT/'rag/eval/cases/routing_store_v1.jsonl')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): parser.error('Output already exists')
    cases=[json.loads(x) for x in args.questions.read_text(encoding='utf-8').splitlines() if x.strip()]
    with psycopg.connect(require_database_url(),options='-c default_transaction_read_only=on') as conn:
        catalog=conn.execute('SELECT poi_id,name FROM v2.attractions ORDER BY poi_id').fetchall()
    report=evaluate(cases,classify_intent,catalog)
    report['dataset_sha256']=hashlib.sha256(args.questions.read_bytes()).hexdigest()
    report['classifier_sha256']=hashlib.sha256(Path(inspect.getsourcefile(classify_intent)).read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report['metrics'],ensure_ascii=False,indent=2))
    for row in report['cases']:
        if not row['store_correct']: print(json.dumps({k:row[k] for k in ('id','question','category','expected_store','predicted_store')},ensure_ascii=False))


if __name__=='__main__': main()
