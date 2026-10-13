set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
import json,requests
from pathlib import Path
base='http://127.0.0.1:8100'
before=requests.get(base+'/maps/usage',timeout=10).json()
response=requests.post(base+'/plan/chat',json={'message':'帮我安排洛阳三天，我还没确定出发地点'},timeout=45)
response.raise_for_status();result=response.json()
after=requests.get(base+'/maps/usage',timeout=10).json()
assert before['usage']==after['usage'],'unexpected Baidu call'
passed=result.get('status')=='needs_clarification' and result.get('slots',{}).get('days')==3
report={'status':'extraction_smoke_passed' if passed else 'extraction_smoke_failed','request':'帮我安排洛阳三天，我还没确定出发地点','response':result,'new_baidu_calls':0,'human_review':None,'full_itinerary_end_to_end':False}
Path('rag/eval/reports/plan_chat_recharge_retry.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
assert passed,'natural language extraction did not pass'
PY
