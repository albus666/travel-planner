set -euo pipefail
cd /home/ubuntu/apps/travel-planner
export PYTHONPATH=rag
curl -fsS --max-time 10 http://127.0.0.1:8100/health
echo
.venv/bin/python rag/eval/run_ticket_eval.py --output rag/eval/reports/sql_ticket_2026-10-12_run1.json
.venv/bin/python rag/eval/run_answer_holdout.py --output rag/eval/reports/answer_holdout_v1_2026-10-12_run2_sql.json
.venv/bin/python - <<'PY'
import json,urllib.request
from pathlib import Path
report=json.loads(Path('rag/eval/reports/answer_holdout_v1_2026-10-12_run2_sql.json').read_text())
assert all(r['response']['route']=='vector' for r in report['cases'])
print('All 25 existing cases stayed on vector route; human re-review pending')
baseline=json.loads(Path('deploy/backups/ask-2026-10-12/retrieval_baseline.json').read_text())
for case in baseline['cases']:
    req=urllib.request.Request('http://127.0.0.1:8100/search',data=json.dumps({'question':case['question'],'top_k':20}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=120) as response: hits=json.load(response)['hits']
    assert [(h['chunk_id'],h['similarity']) for h in hits]==[(h['chunk_id'],h['similarity']) for h in case['baseline']],case['question']
Path('rag/eval/reports/sql_ticket_regression_2026-10-12.json').write_text(json.dumps({'answer_cases_on_vector_route':25,'search_cases_unchanged':73,'top_k_checked':20,'human_re_review':'pending'},indent=2))
print('All 73 /search top-20 IDs and similarities unchanged')
PY
