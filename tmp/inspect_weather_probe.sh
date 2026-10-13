set -euo pipefail
cd /home/ubuntu/apps/travel-planner
PYTHONPATH=rag .venv/bin/python - <<'PY'
import json,requests
from pathlib import Path
x=json.loads(Path('rag/eval/reports/travel_agent_provider_probe.json').read_text())
print(json.dumps(x['weather'],ensure_ascii=False))
print('search',[(r['name'],r['poi_id']) for r in x['search'].get('result',[])])
j=requests.get('https://geocoding-api.open-meteo.com/v1/search',params={'name':'洛阳','count':10,'language':'zh','format':'json','countryCode':'CN'},timeout=12).json();print('geo',[(r.get('name'),r.get('admin1'),r.get('country_code'),r.get('feature_code')) for r in j.get('results',[])])
PY