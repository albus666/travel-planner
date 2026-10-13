set -euo pipefail
cd /home/ubuntu/apps/travel-planner
bash rag/service/stop_retrieval_server.sh
bash rag/service/start_retrieval_server.sh
.venv/bin/python - <<'PY'
import requests,json
base='http://127.0.0.1:8100'
schema=requests.get(base+'/openapi.json').json()
for p in ['/maps/usage','/plan/replan','/plan/multi-day']:assert p in schema['paths'],p
r=requests.get(base+'/maps/usage');r.raise_for_status();print(json.dumps(r.json()))
assert r.json()['usage']=={},'unexpected new provider calls'
print('New endpoints registered; Baidu usage remains zero')
PY
