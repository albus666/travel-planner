set -euo pipefail
cd /home/ubuntu/apps/travel-planner
systemctl list-units --type=service --all --no-pager | grep -E 'travel|planner|rag' || true
systemctl list-unit-files --no-pager | grep -E 'travel|planner|rag' || true
ss -ltnp | grep -E ':8010|:8100' || true
ls -la
find src/travel_planner -maxdepth 2 -type d
sudo -n cat /etc/nginx/sites-enabled/portfolio