import base64,json
from pathlib import Path
names=['rag/service/plan_chat.py','rag/service/web/app.js','rag/service/web/index.html','rag/service/web/style.css','rag/eval/tests/test_plan_chat.py']
data={n:base64.b64encode(Path(n).read_bytes()).decode() for n in names}
s="set -euo pipefail\ncd /home/ubuntu/apps/travel-planner\n.venv/bin/python - <<'PY'\nimport json,base64\nfrom pathlib import Path\ndata=json.loads("+repr(json.dumps(data))+")\nfor n,b in data.items():\n p=Path(n);backup=Path('deploy/backups/optional-departure-v1')/n\n if not backup.exists():\n  backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(p.read_bytes())\n p.write_bytes(base64.b64decode(b))\nPY\nPYTHONPATH=rag .venv/bin/python -m unittest discover -s rag/eval/tests -p 'test_*.py'\n"
Path('tmp/deploy_optional_departure.sh').write_text(s,encoding='utf-8')
