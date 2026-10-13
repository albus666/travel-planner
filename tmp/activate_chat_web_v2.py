import json,base64
from pathlib import Path
names=['rag/service/web/app.js']
data={n:base64.b64encode(Path(n).read_bytes()).decode() for n in names}
s="set -euo pipefail\ncd /home/ubuntu/apps/travel-planner\n.venv/bin/python - <<'PY'\nfrom pathlib import Path\nimport base64,json\ndata=json.loads("+repr(json.dumps(data))+")\nfor n,b in data.items():Path(n).write_bytes(base64.b64decode(b))\nPY\nbash rag/service/stop_retrieval_server.sh\nbash rag/service/start_retrieval_server.sh\n.venv/bin/python - <<'PY'\nimport requests\nbase='http://127.0.0.1:8100'\nfor n in ['','app.js?v=2','markdown.js?v=2','style.css?v=2']:\n r=requests.get(base+'/ui/'+n,timeout=10);r.raise_for_status()\nassert 'composer-wrap' in requests.get(base+'/ui/').text\nprint('New chat UI assets and Markdown renderer active; no provider requests')\nPY\n"
Path('tmp/activate_chat_web_v2.sh').write_text(s,encoding='utf-8')
