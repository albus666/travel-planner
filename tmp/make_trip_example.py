import json
from pathlib import Path
from datetime import date,timedelta
r=json.loads(Path('rag/eval/reports/baidu_maps_v1_live.json').read_text(encoding='utf-8'))
b=next(c['request'] for c in r['cases'] if c['id']=='plan_with_routes');b['optimize_order']=False
pool=['龙门石窟','天子驾六博物馆','洛阳博物馆','隋唐洛阳城应天门遗址','隋唐城遗址植物园','王城公园','从政坊游园']
days=[]
for i,name in enumerate(['龙门石窟','洛阳博物馆']):
 d=json.loads(json.dumps(b));d['plan']['trip_date']=(date(2026,10,14)+timedelta(days=i)).isoformat();d['plan']['must_visit']=[name];d['plan']['avoid']=[n for n in pool if n!=name];days.append(d)
p=Path('rag/client/examples/trip_two_days.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'days':days,'max_replans_per_day':3},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
