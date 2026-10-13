set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
from pathlib import Path
import json,base64
print(base64.b64encode(Path('rag/eval/reports/travel_agent_v1_live.json').read_bytes()).decode())
PY