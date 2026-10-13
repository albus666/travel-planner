set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python - <<'PY'
import sys,importlib.metadata as m
print(sys.version.split()[0])
for p in ('langgraph','langchain-core','fastapi','psycopg','FlagEmbedding'):
    try:print(p,m.version(p))
    except m.PackageNotFoundError:print(p,'not_installed')
PY