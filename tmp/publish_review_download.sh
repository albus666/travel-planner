set -euo pipefail
source_file=/home/ubuntu/apps/travel-planner/rag/eval/reports/answer_holdout_v1_2026-10-12_run1.md
download_dir=/home/ubuntu/portfolio/downloads/rag
download_file=$download_dir/answer-evaluation-25-2026-10-12.md
test -f "$source_file"
mkdir -p "$download_dir"
if [ -f "$download_file" ]; then
  cmp "$source_file" "$download_file"
else
  cp "$source_file" "$download_file"
fi
chmod 755 "$download_dir" /home/ubuntu/portfolio/downloads
chmod 644 "$download_file"
sha256sum "$source_file" "$download_file"
curl -fsSI --max-time 15 http://127.0.0.1/downloads/rag/answer-evaluation-25-2026-10-12.md
curl -fsS --max-time 15 http://127.0.0.1/downloads/rag/answer-evaluation-25-2026-10-12.md | sha256sum