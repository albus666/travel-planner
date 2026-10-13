set -euo pipefail
cd /home/ubuntu/apps/travel-planner
export PYTHONPATH=rag
.venv/bin/python - <<'PY'
import json
import psycopg
from retrieval.search_chunks import require_database_url
with psycopg.connect(require_database_url()) as conn:
    conn.execute('SET TRANSACTION READ ONLY')
    rows=conn.execute('SELECT a.poi_id,a.name,d.ticket_raw,d.ticket_data,d.detail_meta,d.collected_at,d.verify_status,a.source_url FROM v2.attractions a LEFT JOIN v2.poi_details d USING (poi_id) WHERE a.poi_id IN (77498,77806,82477,30611571,56309164,11078925,10615019,33194123,13665171) ORDER BY a.poi_id').fetchall()
    for row in rows: print(json.dumps(row,ensure_ascii=False,default=str))
    print('empty ticket count:',conn.execute("SELECT count(*) FROM v2.poi_details WHERE ticket_raw IS NULL OR btrim(ticket_raw)='' ").fetchone()[0])
    print('missing detail:',conn.execute('SELECT a.poi_id,a.name FROM v2.attractions a LEFT JOIN v2.poi_details d USING(poi_id) WHERE d.poi_id IS NULL LIMIT 3').fetchall())
PY