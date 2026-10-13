import base64,json
from pathlib import Path
names=['rag/service/map_budget.py','rag/service/trip_service.py','rag/service/baidu_maps.py','rag/service/retrieval_server.py','rag/eval/tests/test_baidu_maps.py','rag/eval/tests/test_trip_budget.py','rag/client/run_on_server.ps1']
data={n:base64.b64encode(Path(n).read_bytes()).decode() for n in names}
script="set -euo pipefail\ncd /home/ubuntu/apps/travel-planner\n.venv/bin/python - <<'PY'\nimport base64,json\nfrom pathlib import Path\ndata=json.loads("+repr(json.dumps(data))+")\nfor n,b in data.items():\n p=Path(n);backup=Path('deploy/backups/trip-budget-v1')/n\n if p.exists() and not backup.exists():\n  backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(p.read_bytes())\n p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode(b))\nPY\nPYTHONPATH=rag .venv/bin/python -m unittest discover -s rag/eval/tests -p 'test_*.py'\n"
Path('tmp/deploy_trip_budget.sh').write_text(script,encoding='utf-8')
