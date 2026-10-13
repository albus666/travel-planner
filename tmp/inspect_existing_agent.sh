set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
from pathlib import Path
for name,limit in [('src/travel_planner/chat.py',10000),('src/travel_planner/graph/planner.py',12000),('src/travel_planner/db.py',6500),('src/travel_planner/tools/weather.py',1800),('src/travel_planner/tools/route.py',2200),('src/travel_planner/api/app.py',7000)]:
    print('\nFILE '+name)
    print(Path(name).read_text()[:limit])
PY