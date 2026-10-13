set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
import base64,io,zipfile
from pathlib import Path
buf=io.BytesIO()
files=list(Path('deploy/backups/mixed-2026-10-12').rglob('*'))
files += [Path('rag/eval/reports')/f for f in ('mixed_preflight_v1.json','mixed_v1_live_run1.json','mixed_v1_live_run1.md','mixed_v1_live_fault_scope_followup.json','mixed_v1_live_fault_scope_followup.md')]
with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        if path.is_file():archive.writestr(str(path),path.read_bytes())
print(base64.b64encode(buf.getvalue()).decode())
PY