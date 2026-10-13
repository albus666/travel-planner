set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
from pathlib import Path
import json
p=Path('rag/eval/reports/langgraph_v1_live_run1.json');r=json.loads(p.read_text())
for c in r.get('extra_smoke',[]):
    print(c['name'],c['response']['node_trace'],c['response']['status'])
    print(c['response']['answer'])
PY