set -e
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
import json,base64
from pathlib import Path
names=['rag/eval/reports/baidu_maps_provider_probe.json','rag/eval/reports/baidu_maps_v1_live.json']
print(json.dumps({n:base64.b64encode(Path(n).read_bytes()).decode() for n in names}))
PY
