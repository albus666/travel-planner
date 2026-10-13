set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
import ast,hashlib,json,shutil
from pathlib import Path
report=json.loads(Path('rag/eval/reports/routing_semantic_candidate_v2.json').read_text())
assert report['metrics']['holdout']['ticket_fp']==0 and report['metrics']['holdout']['ticket_fn']==0
assert report['historical_98_store_regression']['changes']==0
old=ast.parse(Path('rag/service/retrieval_server.py').read_text())
new=ast.parse(Path('/tmp/travel-route-stage/service/retrieval_server.py').read_text())
def search_contract(tree):
    names={'SearchRequest','SearchResponse','SearchHit','search_api','health'}
    return {n.name:ast.dump(n,include_attributes=False) for n in tree.body if getattr(n,'name',None) in names}
assert search_contract(old)==search_contract(new)
def sql_literal(path):
    tree=ast.parse(Path(path).read_text())
    return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SEARCH_SQL' for t in n.targets))
assert sql_literal('rag/retrieval/search_chunks.py')==sql_literal('/tmp/travel-route-stage/retrieval/search_chunks.py')
backup=Path('deploy/backups/routing-2026-10-12')
assert not backup.exists()
backup.mkdir(parents=True)
for path in ('rag/service/retrieval_server.py','rag/service/ticket_service.py','rag/retrieval/search_chunks.py'):
    target=backup/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
for path in ('service/intent_classifier.py','service/store_contract.py','service/semantic_router.py','service/routing_prototypes.json','service/retrieval_server.py','service/ticket_service.py','retrieval/search_chunks.py','eval/test_intent_classifier.py','eval/test_semantic_router.py'):
    shutil.copyfile(Path('/tmp/travel-route-stage')/path,Path('rag')/path)
env=Path('.env');original=env.read_bytes()
flag=b'RAG_SEMANTIC_ROUTING_ENABLED='
original_lines=original.splitlines()
other=[line for line in original_lines if not line.strip().startswith(flag)]
updated=b'\n'.join(other)+b'\nRAG_SEMANTIC_ROUTING_ENABLED=1\n'
assert [line for line in updated.splitlines() if not line.strip().startswith(flag)]==other
env.write_bytes(updated)
record={'semantic_routing_enabled':True,'previous_flag_present':any(line.strip().startswith(flag) for line in original_lines),
        'other_env_lines_unchanged':True,'threshold':0.60,'margin':0.06,'classification_llm_calls':0,
        'search_api_and_sql_unchanged':True,'pure_classifier_phase2_tests':19,'final_tests':23}
(backup/'manifest.json').write_text(json.dumps(record,indent=2))
print('Routing v2 deployed; only routing flag added, other environment lines unchanged')
PY
bash rag/service/stop_retrieval_server.sh
nohup bash rag/service/start_retrieval_server.sh > /tmp/travel-ask-deploy.log 2>&1 < /dev/null &
echo 'Warming shared BGE-M3 model and prototype vectors'
