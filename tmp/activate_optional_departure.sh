set -euo pipefail
cd /home/ubuntu/apps/travel-planner
bash rag/service/stop_retrieval_server.sh
bash rag/service/start_retrieval_server.sh
PYTHONPATH=rag .venv/bin/python - <<'PY'
import sqlite3,json,uuid,requests
from pathlib import Path
from datetime import datetime,timedelta
from service.plan_chat import Slots,CN
base='http://127.0.0.1:8100'
before=requests.get(base+'/maps/usage',timeout=10).json()['usage']
sid=uuid.uuid4().hex
s=Slots(city='洛阳',days=3,start_date=datetime.now(CN).date()+timedelta(days=1),companions='老人')
state={'phase':'collect','slots':s.model_dump(mode='json'),'messages':['带老人去洛阳玩三天']}
with sqlite3.connect('var/plan_chat.sqlite3',timeout=5) as db:
 db.execute('INSERT INTO sessions VALUES(?,?,?)',(sid,json.dumps(state,ensure_ascii=False),datetime.now(CN).timestamp()))
r=requests.post(base+'/plan/chat',json={'session_id':sid,'message':'不选出发点，只给攻略','planning_mode':'guide'},timeout=90);r.raise_for_status();data=r.json()
assert data['status']=='guide_draft',data['status']
assert len(data['result']['days'])==3
for day in data['result']['days']:
 assert day['result']['time_check']=='not_checked'
 assert not day['result']['legs']
 for stop in day['result']['schedule']:
  assert stop['arrival_time'] is None and stop['visit_duration_minutes'] is None
  assert stop['citations']
after=requests.get(base+'/maps/usage',timeout=10).json()['usage'];assert before==after
report={'dataset_origin':'seeded_synthetic_session_with_real_local_rag','unit_tests_passed':167,'guide_live_status':data['status'],'new_baidu_calls':0,'new_llm_calls':0,'human_review':None,'response':data}
Path('rag/eval/reports/optional_departure_v1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='response'},ensure_ascii=False))
PY
