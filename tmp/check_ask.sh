set -euo pipefail
cd /home/ubuntu/apps/travel-planner
curl -fsS --max-time 10 http://127.0.0.1:8100/health
echo
tail -n 6 /tmp/travel-ask-deploy.log
