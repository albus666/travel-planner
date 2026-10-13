set -e
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
from pathlib import Path
import base64
print(base64.b64encode(Path('rag/eval/reports/chat_location_fix.json').read_bytes()).decode())
PY
