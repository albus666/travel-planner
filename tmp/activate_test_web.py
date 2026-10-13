import base64,json
from pathlib import Path
names=['rag/service/web/app.js','rag/client/run_on_server.ps1']
data={n:base64.b64encode(Path(n).read_bytes()).decode() for n in names}
s="set -euo pipefail\ncd /home/ubuntu/apps/travel-planner\n.venv/bin/python - <<'PY'\nimport json,base64\nfrom pathlib import Path\ndata=json.loads("+repr(json.dumps(data))+")\nfor n,b in data.items():Path(n).write_bytes(base64.b64decode(b))\nPY\nbash rag/service/stop_retrieval_server.sh\nbash rag/service/start_retrieval_server.sh\n.venv/bin/python - <<'PY'\nimport requests\nbase='http://127.0.0.1:8100'\nfor name in ['','app.js','style.css']:\n r=requests.get(base+'/ui/'+name,timeout=10);r.raise_for_status()\nprint('UI assets served successfully')\nprint('Provider usage:',requests.get(base+'/maps/usage').json()['usage'])\nPY\n"
Path('tmp/activate_test_web.sh').write_text(s,encoding='utf-8')
