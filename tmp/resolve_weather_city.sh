set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
import requests
for q in ['洛阳市','Luoyang']:
 j=requests.get('https://geocoding-api.open-meteo.com/v1/search',params={'name':q,'count':10,'language':'zh','countryCode':'CN'},timeout=12).json();print(q,[(r.get('id'),r.get('name'),r.get('admin1'),r.get('latitude'),r.get('longitude'),r.get('feature_code')) for r in j.get('results',[])])
PY