set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
from pathlib import Path
for root in ('src','tests','scripts','evals','sql','deploy'):
    print(root+':')
    for p in sorted(Path(root).rglob('*')):
        if p.is_file() and '__pycache__' not in str(p):
            print(str(p))
unit=Path('/etc/systemd/system/travel-planner.service')
print('UNIT:')
if unit.exists():
    for line in unit.read_text().splitlines():
        if line.startswith(('Description=','WorkingDirectory=','ExecStart=','EnvironmentFile=')):
            print(line)
hook=Path('/home/ubuntu/repos/travel-planner.git/hooks/post-receive')
print('HOOK:')
if hook.exists(): print(hook.read_text())
print('RAG hashes:')
import hashlib
for p in sorted(Path('rag').rglob('*.py')):
    if 'baselines' not in str(p): print(str(p),hashlib.sha256(p.read_bytes()).hexdigest())
PY