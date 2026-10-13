set -euo pipefail
sudo -n nginx -T 2>&1 | head -n 200
ss -ltn
ls -ld /var/www /var/www/html /home/ubuntu/apps/travel-planner