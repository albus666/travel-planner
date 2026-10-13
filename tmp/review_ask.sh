set -euo pipefail
cd /home/ubuntu/apps/travel-planner
export PYTHONPATH=rag
.venv/bin/python rag/eval/run_answer_review.py --output /tmp/travel_answer_review.json
.venv/bin/python - <<'PY'
import json
import urllib.request
from pathlib import Path
baseline = json.loads(Path('deploy/backups/ask-2026-10-12/retrieval_baseline.json').read_text())
for case in baseline['cases']:
    req = urllib.request.Request('http://127.0.0.1:8100/search',
        data=json.dumps({'question': case['question'], 'top_k': 20}).encode(),
        headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=120) as response:
        hits = json.load(response)['hits']
    assert [(h['chunk_id'],h['similarity']) for h in hits] == [(h['chunk_id'],h['similarity']) for h in case['baseline']], case['question']
print('All 73 questions: /search top-20 IDs and similarities unchanged')
PY
