set -euo pipefail
cd /home/ubuntu/apps/travel-planner
.venv/bin/python rag/eval/run_answer_review.py --output /tmp/travel_answer_review.json
