set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
from pathlib import Path
for name in ('start_retrieval_server.sh', 'stop_retrieval_server.sh'):
    path = Path('rag/service') / name
    backup = Path('deploy/backups/ask-2026-10-12') / name
    if not backup.exists():
        backup.write_bytes(path.read_bytes())
    path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
PY
bash rag/service/stop_retrieval_server.sh
nohup bash rag/service/start_retrieval_server.sh > /tmp/travel-ask-deploy.log 2>&1 < /dev/null &
echo 'Deployment started; warming model'
