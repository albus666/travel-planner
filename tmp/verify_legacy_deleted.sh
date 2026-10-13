set -euo pipefail
cd /home/ubuntu/apps/travel-planner
export PYTHONPATH=rag
.venv/bin/python -m unittest discover -s rag/eval -p 'test_*_service.py' -v
.venv/bin/python - <<'PY'
import importlib.util,json,urllib.request
from pathlib import Path
assert not Path('src').exists()
assert not Path('tests').exists()
assert not Path('/etc/systemd/system/travel-planner.service').exists()
assert not Path('/home/ubuntu/repos/travel-planner.git/hooks/post-receive').exists()
assert importlib.util.find_spec('travel_planner') is None
question='龙门石窟的门票资料记载是什么？'
req=urllib.request.Request('http://127.0.0.1:8100/ask',data=json.dumps({'question':question}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req,timeout=30) as response: answer=json.load(response)
assert answer['route']=='sql_ticket' and answer['structured_data']['ticket_raw']=='门票￥90起'
req=urllib.request.Request('http://127.0.0.1:8100/search',data=json.dumps({'question':'龙门石窟的游览路线是什么？','top_k':3}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req,timeout=30) as response: results=json.load(response)
assert results['hits'] and results['hits'][0]['name']=='龙门石窟'
record=json.loads(Path('docs/LEGACY_PLANNER_REMOVAL.json').read_text())
record.update({'post_deletion_unit_tests_passed':16,'fresh_process_legacy_import_unavailable':True,'ask_sql_smoke_passed':True,'search_smoke_passed':True})
Path('docs/LEGACY_PLANNER_REMOVAL.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
print('Old package unavailable; 16 tests passed; /ask SQL and /search healthy')
PY
if ss -ltn | grep -q ':8010 '; then echo 'Unexpected 8010 listener'; exit 1; fi
echo '8010 listener removed'
