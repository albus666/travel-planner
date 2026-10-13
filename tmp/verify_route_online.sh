set -euo pipefail
cd /home/ubuntu/apps/travel-planner
export PYTHONPATH=rag
.venv/bin/python rag/eval/verify_routing_live.py --output rag/eval/reports/routing_v2_live_regression.json
.venv/bin/python - <<'PY'
import json
from pathlib import Path
import psycopg
from retrieval.search_chunks import require_database_url
from service.intent_classifier import classify_intent
from service.store_contract import boundary_intent
from eval.run_routing_eval import evaluate
cases=[json.loads(x) for x in Path('rag/eval/cases/routing_store_v1.jsonl').read_text().splitlines() if x.strip()]
with psycopg.connect(require_database_url(),options='-c default_transaction_read_only=on') as conn:
    catalog=conn.execute('SELECT poi_id,name FROM v2.attractions ORDER BY poi_id').fetchall()
report=evaluate(cases,lambda q:boundary_intent(q) or classify_intent(q),catalog)
Path('rag/eval/reports/routing_boundary_rule_v2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('Boundary-only:',json.dumps(report['metrics']['all']))
PY
