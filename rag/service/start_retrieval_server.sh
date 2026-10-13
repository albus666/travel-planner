#!/usr/bin/env bash
# 在服务器上启动常驻检索服务（BGE-M3 只加载一次）。
# 用法（在 travel-planner 项目根）: bash rag/service/start_retrieval_server.sh
#
# 已安装 systemd 单元 travel-rag 时优先交给它（开机自启、崩溃自动重启、
# 日志进 journal）；只有单元不存在时才回落到 nohup，保持旧环境可用。
set -euo pipefail
# rag/service -> rag -> project root
cd "$(dirname "$0")/../.."
APP_DIR="$(pwd)"
PORT="${RAG_RETRIEVAL_PORT:-8100}"
UNIT=/etc/systemd/system/travel-rag.service

healthy() {
  curl -sf "http://127.0.0.1:${PORT}/health" | grep -q '"model_ready":true'
}

if [[ -f "$UNIT" ]]; then
  if healthy; then
    echo "already running (systemd travel-rag)"
    curl -s "http://127.0.0.1:${PORT}/health"
    echo
    exit 0
  fi
  sudo -n systemctl restart travel-rag.service
  echo "systemd travel-rag restarted; waiting for model warm-up..."
  for _ in $(seq 1 90); do
    if healthy; then
      curl -s "http://127.0.0.1:${PORT}/health"
      echo
      exit 0
    fi
    sleep 2
  done
  echo "warm-up timeout; see: sudo journalctl -u travel-rag -n 50" >&2
  exit 1
fi

PID_FILE=/tmp/rag_retrieval_server.pid
LOG_FILE=/tmp/rag_retrieval_server.log

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "already running pid=$(cat "$PID_FILE") port=$PORT"
  curl -s "http://127.0.0.1:${PORT}/health" || true
  echo
  exit 0
fi

set -a
# shellcheck disable=SC1091
source "$APP_DIR/.env"
set +a
export HF_HOME="${HF_HOME:-/home/ubuntu/.cache/huggingface}"
export TMPDIR="${TMPDIR:-/tmp}"
export PYTHONPATH="$APP_DIR/rag"
export PYTHONIOENCODING=utf-8
export LANG=C.UTF-8

nohup "$APP_DIR/.venv/bin/python" -m uvicorn service.retrieval_server:app \
  --host 127.0.0.1 \
  --port "$PORT" \
  --log-level info \
  >"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"
echo "started pid=$(cat "$PID_FILE") port=$PORT log=$LOG_FILE"
echo "waiting for model warm-up..."
for i in $(seq 1 90); do
  if healthy; then
    curl -s "http://127.0.0.1:${PORT}/health"
    echo
    exit 0
  fi
  sleep 2
done
echo "warm-up timeout; see $LOG_FILE" >&2
exit 1
