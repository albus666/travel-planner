set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
import base64,io,zipfile
from pathlib import Path
buf=io.BytesIO()
files=['routing_legacy_rule_v1.json','routing_boundary_rule_v2.json','routing_semantic_candidate_v1.json','routing_semantic_candidate_v2.json','routing_v2_live_regression.json']
with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as archive:
    for name in files:
        archive.writestr('reports/'+name,(Path('rag/eval/reports')/name).read_bytes())
    for base in ('routing_rule_v1','routing_candidate_v2_sources'):
        root=Path('rag/eval/baselines')/base
        for path in root.rglob('*'):
            if path.is_file() and '__pycache__' not in str(path):
                archive.writestr('baselines/'+str(path.relative_to(Path('rag/eval/baselines'))),path.read_bytes())
print(base64.b64encode(buf.getvalue()).decode())
PY