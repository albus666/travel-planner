#!/usr/bin/env bash
# 停止常驻检索服务。装了 systemd 单元就交给 systemctl，否则回落到 pid 文件。
set -euo pipefail
UNIT=/etc/systemd/system/travel-rag.service

if [[ -f "$UNIT" ]]; then
  sudo -n systemctl stop travel-rag.service
  echo "stopped (systemd travel-rag)"
  exit 0
fi

PID_FILE=/tmp/rag_retrieval_server.pid
if [[ ! -f "$PID_FILE" ]]; then
  echo "not running (no pid file)"
  exit 0
fi
pid="$(cat "$PID_FILE")"
if kill -0 "$pid" 2>/dev/null; then
  kill "$pid"
  sleep 1
  kill -9 "$pid" 2>/dev/null || true
  echo "stopped pid=$pid"
else
  echo "stale pid file ($pid)"
fi
rm -f "$PID_FILE"
