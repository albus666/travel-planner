set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
import base64, io, zipfile
from pathlib import Path
name = 'answer_holdout_v1_2026-10-12_run1'
buffer = io.BytesIO()
with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
    for ext in ('json','md'):
        path = Path('rag/eval/reports') / (name + '.' + ext)
        archive.writestr(path.name, path.read_bytes())
print(base64.b64encode(buffer.getvalue()).decode())
PY