set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
from pathlib import Path
for root in ('src','tests','deploy'):
    print(root+':')
    for p in sorted(Path(root).rglob('*')):
        if p.is_file() and '__pycache__' not in str(p) and p.suffix in ('.py','.md','.toml'):
            print(str(p))
print('README:')
print(Path('README.md').read_text()[:6000])
print('pyproject:')
print(Path('pyproject.toml').read_text())
PY