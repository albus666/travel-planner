set -euo pipefail
cd /home/ubuntu/apps/travel-planner
export PYTHONPATH=rag
.venv/bin/python - <<'PY'
import psycopg
from retrieval.search_chunks import require_database_url
with psycopg.connect(require_database_url(),options='-c default_transaction_read_only=on') as conn:
    print('schema references:',conn.execute("SELECT to_regclass('public.attractions'),to_regclass('public.knowledge_chunks'),to_regclass('v2.attractions'),to_regclass('v2.rag_chunks')").fetchone())
PY
curl -s -o /dev/null -w 'legacy_attraction_http_status=%{http_code}\n' --max-time 15 http://127.0.0.1:8010/v1/attractions/77498
curl -fsS --max-time 10 http://127.0.0.1:8100/health