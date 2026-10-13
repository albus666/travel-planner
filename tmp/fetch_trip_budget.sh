set -e
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
import base64
from pathlib import Path
print(base64.b64encode(Path('rag/eval/reports/trip_budget_v1_mock.json').read_bytes()).decode())
PY
