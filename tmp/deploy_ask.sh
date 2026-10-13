set -euo pipefail
cd /home/ubuntu/apps/travel-planner
export PYTHONPATH=rag
.venv/bin/python - <<'PY'
import ast
import hashlib
from pathlib import Path
old = ast.parse(Path('rag/service/retrieval_server.py').read_text())
new = ast.parse(Path('/tmp/travel-ask-stage/service/retrieval_server.py').read_text())
def contract(tree):
    names = {'SearchRequest', 'SearchResponse', 'SearchHit', 'search_api', 'health', 'lifespan'}
    return {n.name: ast.dump(n, include_attributes=False) for n in tree.body if getattr(n, 'name', None) in names}
assert contract(old) == contract(new), 'Existing endpoint implementation changed'
assert hashlib.sha256(Path('rag/retrieval/search_chunks.py').read_bytes()).hexdigest() == '9eee35bb5001850bf2b9dd05bb2e1d4a153c173ee91f14a70b2ab8a3dd2083a0'
assert not Path('rag/service/answer_service.py').exists(), 'Unexpected existing answer module'
print('Frozen /search and retrieval code verified')
PY
mkdir -p deploy/backups/ask-2026-10-12
test ! -f deploy/backups/ask-2026-10-12/retrieval_server.py
cp rag/service/retrieval_server.py deploy/backups/ask-2026-10-12/retrieval_server.py
cp /tmp/travel_retrieval_audit.json deploy/backups/ask-2026-10-12/retrieval_baseline.json
cp /tmp/travel-ask-stage/service/answer_service.py rag/service/answer_service.py
cp /tmp/travel-ask-stage/service/retrieval_server.py rag/service/retrieval_server.py
cp /tmp/travel-ask-stage/eval/test_answer_service.py rag/eval/test_answer_service.py
cp /tmp/travel-ask-stage/eval/run_answer_review.py rag/eval/run_answer_review.py
bash rag/service/stop_retrieval_server.sh
nohup bash rag/service/start_retrieval_server.sh > /tmp/travel-ask-deploy.log 2>&1 < /dev/null &
echo 'Deployment started; warm-up log: /tmp/travel-ask-deploy.log'
