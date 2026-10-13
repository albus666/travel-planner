#!/usr/bin/env bash
# 把 /travel/ 从 410 占位改为反代到 RAG 服务。只改那两行，其余原样；失败自动回滚。
set -euo pipefail

STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="/home/ubuntu/apps/travel-planner/deploy/backups/nginx-${STAMP}"
mkdir -p "$BACKUP"
sudo -n cp /etc/nginx/sites-available/portfolio "$BACKUP/portfolio.bak"
echo "backup: $BACKUP/portfolio.bak"

sudo -n mkdir -p /etc/nginx/snippets
sudo -n cp /tmp/travel-proxy.conf /etc/nginx/snippets/travel-proxy.conf
sudo -n chmod 644 /etc/nginx/snippets/travel-proxy.conf

sudo -n python3 - <<'PY'
import re
from pathlib import Path

path = Path('/etc/nginx/sites-available/portfolio')
text = path.read_text(encoding='utf-8')
pattern = re.compile(
    r'[ \t]*location = /travel \{ return 410; \}[ \t]*\r?\n'
    r'[ \t]*location \^~ /travel/ \{ return 410; \}[ \t]*\r?\n')
replacement = (
    '    # 旅行助手：反代到常驻 RAG 服务（127.0.0.1:8100）。旧规划器删除后这里曾是 410 占位。\n'
    '    include /etc/nginx/snippets/travel-proxy.conf;\n')
text, count = pattern.subn(replacement, text)
if count != 2:
    raise SystemExit(f'expected 2 placeholder blocks (http+https), found {count}; aborting')
path.write_text(text, encoding='utf-8')
print(f'replaced blocks: {count}')
PY

if sudo -n nginx -t; then
  sudo -n systemctl reload nginx
  echo "nginx reloaded"
else
  echo "nginx -t FAILED; restoring backup"
  sudo -n cp "$BACKUP/portfolio.bak" /etc/nginx/sites-available/portfolio
  sudo -n nginx -t || true
  exit 1
fi
