set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
from pathlib import Path
import base64,io,zipfile,json,hashlib
files=list(Path('rag/eval/baselines/answer_evidence_v2').rglob('*'))
files += [Path('rag/eval/candidates/answer_evidence_v2/manifest.json')]
files += list(Path('rag/eval/reports').glob('luoyang_one_day_v1_*.json'))+list(Path('rag/eval/reports').glob('luoyang_one_day_v1_*.md'))
files += list(Path('rag/eval/reports').glob('planning_v1_qa_regression.*'))
files += list(Path('tmp').glob('*.sh'))
assert Path('rag/eval/baselines/answer_evidence_v2/manifest.json').is_file()
assert Path('rag/eval/reports/luoyang_one_day_v1_final.json').is_file()
buf=io.BytesIO(); hashes={}
with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
 for p in files:
  if p.is_file():
   data=p.read_bytes(); name=p.as_posix(); hashes[name]=hashlib.sha256(data).hexdigest(); z.writestr(name,data)
 z.writestr('tmp/remote_sync_sha256.json',json.dumps(hashes,indent=2))
print(base64.b64encode(buf.getvalue()).decode())
PY