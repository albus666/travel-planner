set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
import json
from pathlib import Path
p=Path('rag/eval/reports/routing_semantic_candidate_v1.json')
r=json.loads(p.read_text())
print(json.dumps({'selected':r['selected_on_dev_only'],'metrics':r['metrics'],'historical':{k:v for k,v in r['historical_98_store_regression'].items() if k!='cases'},'encoding_median_ms':r['encode_ms_median'],'encoding_p95_ms':r['encode_ms_p95']},ensure_ascii=False,indent=2))
for row in r['historical_98_store_regression']['cases']:
    if not row['unchanged']: print(json.dumps(row,ensure_ascii=False))
PY