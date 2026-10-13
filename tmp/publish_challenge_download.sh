set -euo pipefail
cd /home/ubuntu/apps/travel-planner
source_file=rag/eval/reports/routing_challenge_v1_run1.md
download_file=/home/ubuntu/portfolio/downloads/rag/routing-evaluation-30-2026-10-12.md
cp "$source_file" "$download_file"
chmod 644 "$download_file"
sha256sum "$source_file" "$download_file"
curl -fsSI --max-time 15 http://52.199.126.245/downloads/rag/routing-evaluation-30-2026-10-12.md
curl -fsS --max-time 15 http://52.199.126.245/downloads/rag/routing-evaluation-30-2026-10-12.md | sha256sum