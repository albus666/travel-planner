import base64,json
from pathlib import Path
n='docs/PLAN_CHAT_NL_INTAKE.md';data=base64.b64encode(Path(n).read_bytes()).decode()
s="set -e\ncd /home/ubuntu/apps/travel-planner\n.venv/bin/python - <<'PY'\nfrom pathlib import Path\nimport base64\nPath("+repr(n)+").write_bytes(base64.b64decode("+repr(data)+"))\nprint('Fix documentation synchronized')\nPY\n"
Path('tmp/sync_chat_location_doc.sh').write_text(s,encoding='utf-8')
