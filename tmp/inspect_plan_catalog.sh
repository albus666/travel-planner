set -euo pipefail
cd /home/ubuntu/apps/travel-planner
PYTHONPATH=rag .venv/bin/python - <<'PY'
from retrieval.search_chunks import require_database_url
import psycopg,json
with psycopg.connect(require_database_url(),options='-c default_transaction_read_only=on') as c:
    cols=c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='v2' AND table_name='attractions' ORDER BY ordinal_position").fetchall()
    print([r[0] for r in cols])
    rows=c.execute("SELECT poi_id,name FROM v2.attractions WHERE name LIKE '%博物馆%' OR name LIKE '%应天门%' OR name IN ('龙门石窟','隋唐城遗址植物园','从政坊游园','王城公园') ORDER BY poi_id").fetchall()
    print(json.dumps(rows,ensure_ascii=False))
PY