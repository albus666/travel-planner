set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
import requests,json
s=requests.Session();s.headers['User-Agent']='Mozilla/5.0'
for keyword in ['龙门石窟','郑州西亚斯学院']:
 try:
  r=s.post('https://m.ctrip.com/restapi/soa2/30668/search',params={'action':'globalonline','source':'globalonline','keyword':keyword},headers={'Cookie':'GUID=09031074218690796683'},timeout=15);r.raise_for_status();j=r.json()
  print('search',keyword,[(x.get('word'),x.get('poiId'),x.get('type'),x.get('districtName')) for x in j.get('data',[])][:8])
 except Exception as e:print('search_error',type(e).__name__)
try:
 r=s.post('https://m.ctrip.com/restapi/soa2/13444/json/getCommentCollapseList',json={'arg':{'channelType':2,'collapseType':0,'commentTagId':0,'pageIndex':1,'pageSize':3,'poiId':77498,'sourceType':1,'sortType':3,'starType':0},'head':{'cid':'09031030113497386388','ctok':'','cver':'1.0','lang':'01','sid':'8888','syscode':'09','auth':'','xsid':'','extension':[]}},timeout=15);r.raise_for_status();j=r.json();items=(j.get('result') or {}).get('items') or [];print('comments',len(items),'keys',list(items[0]) if items else list(j));print('time_fields',{k:v for k,v in (items[0] if items else {}).items() if any(w in k.lower() for w in ['time','date','id']) and not isinstance(v,(dict,list))})
except Exception as e:print('comments_error',type(e).__name__)
PY