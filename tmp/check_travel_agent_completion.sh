set -euo pipefail
cd /home/ubuntu/apps/travel-planner
curl -fsS http://127.0.0.1:8100/health
.venv/bin/python - <<'PY'
from pathlib import Path
import json
p=Path('rag/eval/reports/travel_agent_v1_live.json')
print('report_exists',p.exists())
if p.exists():
 r=json.loads(p.read_text());print('case_count',len(r['cases']))
 for c in r['cases']:
  o=c.get('response',{});print(c['id'],c.get('error'),o.get('status'),o.get('failure'),o.get('tool_trace'))
print('agent_route',"@app.post('/agent/ask')" in Path('rag/service/retrieval_server.py').read_text())
PY