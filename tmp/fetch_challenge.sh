set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
import base64,io,zipfile
from pathlib import Path
buf=io.BytesIO()
files=list(Path('rag/eval/baselines/routing_v2_frozen').rglob('*'))
files += [Path('rag/eval/reports/routing_challenge_v1_run1.json'),Path('rag/eval/reports/routing_challenge_v1_run1.md')]
with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        if path.is_file(): archive.writestr(str(path),path.read_bytes())
print(base64.b64encode(buf.getvalue()).decode())
PY