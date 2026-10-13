set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
import ast,hashlib,json
from pathlib import Path
base=Path('rag/eval/baselines/answer_v1')
manifest=json.loads((base/'manifest.json').read_text())
for path in ('rag/service/retrieval_server.py','rag/service/answer_service.py','rag/retrieval/search_chunks.py'):
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==manifest['original_file_hashes'][path],path
old=ast.parse(Path('rag/service/retrieval_server.py').read_text())
new=ast.parse(Path('/tmp/travel-ticket-stage/service/retrieval_server.py').read_text())
def contract(tree):
    names={'SearchRequest','SearchResponse','SearchHit','search_api','health','lifespan'}
    return {n.name:ast.dump(n,include_attributes=False) for n in tree.body if getattr(n,'name',None) in names}
assert contract(old)==contract(new)
assert Path('rag/service/answer_service.py').read_bytes()==Path('/tmp/travel-ticket-stage/service/answer_service.py').read_bytes()
assert not Path('rag/service/ticket_service.py').exists()
print('answer v1 frozen; /search and answer prompt unchanged')
PY
mkdir -p deploy/backups/sql-ticket-2026-10-12
test ! -f deploy/backups/sql-ticket-2026-10-12/retrieval_server.py
cp rag/service/retrieval_server.py deploy/backups/sql-ticket-2026-10-12/retrieval_server.py
cp /tmp/travel-ticket-stage/service/ticket_service.py rag/service/ticket_service.py
cp /tmp/travel-ticket-stage/service/retrieval_server.py rag/service/retrieval_server.py
cp /tmp/travel-ticket-stage/eval/test_answer_service.py rag/eval/test_answer_service.py
cp /tmp/travel-ticket-stage/eval/test_ticket_service.py rag/eval/test_ticket_service.py
bash rag/service/stop_retrieval_server.sh
nohup bash rag/service/start_retrieval_server.sh > /tmp/travel-ask-deploy.log 2>&1 < /dev/null &
echo 'SQL ticket route deployed; model warm-up started'
