set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
from pathlib import Path
for line in Path('.env').read_text().splitlines():
    if '=' not in line or line.lstrip().startswith('#'):
        continue
    key, value = line.split('=', 1)
    key, value = key.strip(), value.strip().strip('"').strip("'")
    if key.startswith('LLM_') or key in ('OPENAI_API_KEY', 'OPENAI_BASE_URL'):
        if any(part in key for part in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD')):
            print(key + ': ' + ('configured' if value else 'empty'))
        elif any(part in key for part in ('MODEL', 'BASE_URL', 'PROVIDER')):
            print(key + ': ' + value)
        else:
            print(key + ': present')
PY