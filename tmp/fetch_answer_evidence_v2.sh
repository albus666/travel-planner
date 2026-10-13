set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
from pathlib import Path
import base64,io,zipfile
buf=io.BytesIO()
files=list(Path('rag/eval/candidates/answer_evidence_v2').rglob('*'))+list(Path('deploy/backups/answer-evidence-2026-10-12').rglob('*'))
files += [Path('rag/eval/reports')/f for f in ('langgraph_answer_v2_live_run1.json','langgraph_answer_v2_live_run1.md','langgraph_answer_v2_scope_followup.json','langgraph_answer_v2_scope_followup.md')]
with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        if path.is_file():archive.writestr(str(path),path.read_bytes())
print(base64.b64encode(buf.getvalue()).decode())
PY