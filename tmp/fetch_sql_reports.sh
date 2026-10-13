set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
import base64,io,zipfile
from pathlib import Path
files=['sql_ticket_2026-10-12_run1.json','sql_ticket_2026-10-12_run2.json','sql_ticket_regression_2026-10-12.json','answer_holdout_v1_2026-10-12_run2_sql.json','answer_holdout_v1_2026-10-12_run2_sql.md','answer_holdout_v1_2026-10-12_run3_sql.json','answer_holdout_v1_2026-10-12_run3_sql.md']
buf=io.BytesIO()
with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as archive:
    for name in files: archive.writestr(name,(Path('rag/eval/reports')/name).read_bytes())
print(base64.b64encode(buf.getvalue()).decode())
PY