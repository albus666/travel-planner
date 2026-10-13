set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
from pathlib import Path
print('ATTRACTION TOOLS:')
print(Path('src/travel_planner/tools/attractions.py').read_text()[:11500])
print('GRAPH TAIL:')
print(Path('src/travel_planner/graph/planner.py').read_text()[-6500:])
print('INTEGRATION REFERENCES:')
for path in Path('src/travel_planner').rglob('*.py'):
    for i,line in enumerate(path.read_text().splitlines(),1):
        if any(s in line for s in ('8100','service.answer_service','retrieval.search_chunks','checkpointer','MemorySaver','bind_tools','ToolNode','thread_id')):
            print(str(path)+':'+str(i)+':'+line)
PY
curl -fsS --max-time 10 http://127.0.0.1:8010/health
printf '\n'
curl -sS --max-time 15 http://127.0.0.1:8010/v1/attractions/77498
printf '\n'