set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
from pathlib import Path
import json
r=json.loads(Path('rag/eval/reports/langgraph_answer_v2_scope_followup.json').read_text())
for c in r['challenge'][2:]:
    a=c['response'];print(c['case']['id']);print(a['answer'])
    print('RAG状态',a['tool_results']['rag']['state'],a['tool_results']['rag']['result'].get('evidence_scope'))
    print('引用',[(s['source_id'],s['theme'],s['quotes']) for s in a['citations']])
PY