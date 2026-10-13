set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
import base64,io,zipfile
from pathlib import Path
buf=io.BytesIO()
with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as archive:
    for path in Path('rag/eval/baselines/mixed_v1').rglob('*'):
        if path.is_file():archive.writestr(str(path),path.read_bytes())
print(base64.b64encode(buf.getvalue()).decode())
PY