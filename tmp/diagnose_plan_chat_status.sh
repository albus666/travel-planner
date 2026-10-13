set -e
cd /home/ubuntu/apps/travel-planner
PYTHONPATH=rag .venv/bin/python - <<'PY'
from retrieval.search_chunks import load_env_files
load_env_files()
from service.plan_chat import extract
import requests
try:extract(['帮我安排洛阳三天，我还没确定出发地点'])
except requests.HTTPError as e:
 print('HTTP status:',e.response.status_code)
 try:
  data=e.response.json();err=data.get('error',{});print('error type:',err.get('type'));print('error code:',err.get('code'));print('message:',str(err.get('message',''))[:400])
 except Exception:print('non-json provider response')
PY
