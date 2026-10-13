set -e
cd /home/ubuntu/apps/travel-planner
PYTHONPATH=rag .venv/bin/python - <<'PY'
from retrieval.search_chunks import load_env_files
load_env_files()
from service.plan_chat import extract
from pydantic import ValidationError
try:
 s=extract(['帮我安排洛阳三天，我还没确定出发地点'])
 print(s.model_dump_json())
except ValidationError as e:print(e.errors(include_input=False,include_context=False))
except Exception as e:print(type(e).__name__)
PY
