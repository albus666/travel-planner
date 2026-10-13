#!/usr/bin/env bash
# 安装 systemd 常驻单元并接管当前 nohup 进程。
set -euo pipefail

sudo -n cp /tmp/travel-rag.service /etc/systemd/system/travel-rag.service
sudo -n chmod 644 /etc/systemd/system/travel-rag.service

# 先停掉手工 nohup 起来的进程，避免端口冲突。
if [ -f /tmp/rag_retrieval_server.pid ]; then
  old=$(cat /tmp/rag_retrieval_server.pid)
  if kill -0 "$old" 2>/dev/null; then
    kill "$old" 2>/dev/null || true
    sleep 3
    kill -9 "$old" 2>/dev/null || true
    echo "stopped old nohup pid=$old"
  fi
  rm -f /tmp/rag_retrieval_server.pid
fi

# 兜底：清掉任何残留的同名进程（按精确命令行匹配，不用 pkill -f 以免误伤本脚本）。
for pid in $(pgrep -f 'uvicorn service.retrieval_server:app' || true); do
  kill "$pid" 2>/dev/null || true
done
sleep 2

sudo -n systemctl daemon-reload
sudo -n systemctl enable travel-rag.service
sudo -n systemctl restart travel-rag.service

echo "waiting for model warm-up..."
for _ in $(seq 1 90); do
  if curl -sf http://127.0.0.1:8100/health | grep -q '"model_ready":true'; then
    curl -s http://127.0.0.1:8100/health
    echo
    sudo -n systemctl is-enabled travel-rag.service
    sudo -n systemctl is-active travel-rag.service
    exit 0
  fi
  sleep 2
done

echo "warm-up timeout; last log lines:" >&2
sudo -n journalctl -u travel-rag.service -n 30 --no-pager >&2 || true
exit 1
