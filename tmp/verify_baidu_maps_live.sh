set -e
cd /home/ubuntu/apps/travel-planner
PYTHONPATH=rag .venv/bin/python - <<'PY'
import json,requests,copy
from pathlib import Path
from datetime import datetime,timedelta,timezone
p={'lat':34.692327,'lng':112.442317,'coord_type':'bd09ll','name':'洛阳站','uid':'190b560ec24a6ba48bf15d99'};museum={'lat':34.649647,'lng':112.458391,'coord_type':'bd09ll','name':'洛阳博物馆','uid':'55fa2c0b865b5e501ce99902'};base='http://127.0.0.1:8100';report={'dataset_origin':'agent_generated_synthetic_not_real_user_blind','human_review':None,'unit_tests_passed':120,'cases':[]}
def post(path,data):
 r=requests.post(base+path,json=data,timeout=150);r.raise_for_status();return r.json()
for cid,q in [('agent_route','从洛阳站开车到洛阳博物馆多久？'),('agent_ambiguous','从龙门开车到洛阳站多久？')]:
 try:
  agent_body={'question':q,**({'map_points':{'洛阳站':p,'洛阳博物馆':museum}} if cid=='agent_route' else {})};o=post('/agent/ask',agent_body);report['cases'].append({'id':cid,'request':agent_body,'response':o});print(cid,o['status'],[(t['tool'],t['state']) for t in o['tool_trace']],flush=True)
 except Exception as e:report['cases'].append({'id':cid,'error':type(e).__name__});print(cid,type(e).__name__,flush=True)
 Path('rag/eval/reports/baidu_maps_v1_live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
day=(datetime.now(timezone(timedelta(hours=8))).date()+timedelta(days=1)).isoformat()
body={'plan':{'request':'给我安排洛阳一日游','trip_date':day,'departure':'洛阳站','companions':'两位成人','preferences':['历史文化'],'pace':'轻松','transport':'自驾','must_visit':['龙门石窟','洛阳博物馆']},'departure_point':p,'end_point':p,'start_time':'09:00','end_time':'18:00','mode':'driving','visit_minutes':{'龙门石窟':120,'洛阳博物馆':90},'buffer_minutes_per_leg':10,'optimize_order':True}
for cid,change in [('plan_with_routes',{}),('plan_conflict',{'end_time':'09:30','optimize_order':False}),('plan_missing_duration',{'visit_minutes':{}})]:
 b={**body,**change}
 try:
  o=post('/plan/with-routes',b);report['cases'].append({'id':cid,'request':b,'response':o});print(cid,o['status'],o.get('time_check'),flush=True)
 except Exception as e:report['cases'].append({'id':cid,'error':type(e).__name__});print(cid,type(e).__name__,flush=True)
 Path('rag/eval/reports/baidu_maps_v1_live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
assert post('/plan',{'request':'给我安排洛阳一日游'})['status']=='needs_clarification'
assert post('/search',{'question':'龙门石窟介绍','top_k':3})['hits']
report['existing_endpoint_smoke']='plan clarification and search hits passed';Path('rag/eval/reports/baidu_maps_v1_live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
PY

