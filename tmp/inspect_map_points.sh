set -e
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
import requests,json
for q in ['洛阳站','洛阳博物馆']:
 r=requests.post('http://127.0.0.1:8100/maps/query',json={'action':'search','arguments':{'query':q,'region':'洛阳'}}).json()
 print(json.dumps(r,ensure_ascii=False))
PY
