set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
import requests,json
for a in ['globalonline','online']:
 j=requests.post('https://m.ctrip.com/restapi/soa2/30668/search',params={'action':a,'source':'globalonline','keyword':'郑州西亚斯学院'},headers={'User-Agent':'Mozilla/5.0','Cookie':'GUID=09031074218690796683','Content-Type':'application/x-www-form-urlencoded'},data='',timeout=15).json()
 print(a,json.dumps(j,ensure_ascii=False)[:4500])
PY