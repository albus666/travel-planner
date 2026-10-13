set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
import json
from pathlib import Path
r=json.loads(Path('rag/eval/reports/mixed_v1_live_run1.json').read_text())
for c in r['challenge'][:4]:
    print(c['case']['id'])
    print(c['response']['answer'])
    print('引用：',[(s['source_id'],s['theme'],s['poi_id']) for s in c['response']['citations']])
PY