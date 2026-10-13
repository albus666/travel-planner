set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
from pathlib import Path
import base64,io,zipfile
buf=io.BytesIO()
files=list(Path('rag/eval/baselines/langgraph_candidate_v1').rglob('*'))+list(Path('deploy/backups/langgraph-2026-10-12').rglob('*'))
files += [Path('rag/eval/reports')/f for f in ('langgraph_v1_live_run1.json','langgraph_v1_live_run1.md','langgraph_v1_schema_followup.json','langgraph_v1_schema_followup.md')]
with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        if path.is_file():archive.writestr(str(path),path.read_bytes())
print(base64.b64encode(buf.getvalue()).decode())
PY