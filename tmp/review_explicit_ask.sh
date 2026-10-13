set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
import json
from pathlib import Path
import urllib.request
question = '龙门石窟的老人免票年龄条件是什么？'
req = urllib.request.Request('http://127.0.0.1:8100/ask',
    data=json.dumps({'question':question}).encode(), headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req, timeout=120) as response:
    result = json.load(response)
path = Path('/tmp/travel_answer_review.json')
rows = json.loads(path.read_text())
rows.append({'id':'elderly_explicit','question':question,
    'review_criteria':'明确龙门石窟，保留60周岁含以上条件，不套用其他POI政策',
    'response':result,'human_review':None})
path.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:result[k] for k in ('status','answer','warnings')},ensure_ascii=False))
PY
