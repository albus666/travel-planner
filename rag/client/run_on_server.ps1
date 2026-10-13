# Query retrieval on EC2 (cached BGE-M3 + server-local Postgres).
# Uses the always-on HTTP service; starts it if it is not running yet.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File rag\client\run_on_server.ps1
#   powershell -ExecutionPolicy Bypass -File rag\client\run_on_server.ps1 -QuestionFile rag\fixtures\my_q.txt
#   powershell -ExecutionPolicy Bypass -File rag\client\run_on_server.ps1 -Eval
#   powershell -ExecutionPolicy Bypass -File rag\client\run_on_server.ps1 -Cold   # one-shot, loads model each run
#
# Chinese questions live in UTF-8 text files under rag\fixtures\.

param(
    [string]$QuestionFile = "",
    [int]$TopK = 3,
    [switch]$Eval,
    [switch]$Cold
)

$ErrorActionPreference = "Stop"
# client -> rag -> project root
$RagRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = Split-Path -Parent $RagRoot
$Key = Join-Path $ProjectRoot "key\cursor-pilot.pem"
$HostName = "52.199.126.245"
$RemoteApp = "/home/ubuntu/apps/travel-planner"
$RemoteQuestion = "/tmp/rag_question_utf8.txt"
$Port = 8100
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false

if (-not (Test-Path $Key)) {
    throw "missing key: $Key"
}

function Invoke-RemoteBash([string]$ScriptBody) {
    # Normalize to LF: CRLF makes remote bash choke ("set: pipefail\r: invalid option name")
    $normalized = $ScriptBody.Replace("`r`n", "`n").Replace("`r", "`n")
    $b64 = [Convert]::ToBase64String($Utf8NoBom.GetBytes($normalized))
    ssh -i $Key "ubuntu@$HostName" "echo $b64 | base64 -d | bash"
    if ($LASTEXITCODE -ne 0) {
        throw "remote command failed, exit=$LASTEXITCODE"
    }
}

# --- Sync local rag tree to server (preserve subdirs) ---
# Vendored runtime is versioned with this project; never upload .env from its source project.
scp -i $Key -q -r (Join-Path $RagRoot "agent_runtime") "ubuntu@${HostName}:$RemoteApp/rag/"
Invoke-RemoteBash "mkdir -p $RemoteApp/rag/retrieval $RemoteApp/rag/service $RemoteApp/rag/eval/cases $RemoteApp/rag/eval/runners $RemoteApp/rag/fixtures"
scp -i $Key -q (Join-Path $RagRoot "retrieval\__init__.py") `
    (Join-Path $RagRoot "retrieval\search_chunks.py") `
    (Join-Path $RagRoot "retrieval\search_from_file.py") `
    "ubuntu@${HostName}:$RemoteApp/rag/retrieval/"
scp -i $Key -q (Join-Path $RagRoot "service\__init__.py") `
    (Join-Path $RagRoot "service\retrieval_server.py") `
    (Join-Path $RagRoot "service\travel_agent.py") `
    (Join-Path $RagRoot "service\travel_online.py") `
      (Join-Path $RagRoot "service\baidu_maps.py") `
      (Join-Path $RagRoot "service\route_plan.py") `
      (Join-Path $RagRoot "service\map_budget.py") `
      (Join-Path $RagRoot "service\trip_service.py") `
      (Join-Path $RagRoot "service\plan_chat.py") `
    (Join-Path $RagRoot "service\answer_service.py") `
      (Join-Path $RagRoot "service\answer_evidence_guards.py") `
      (Join-Path $RagRoot "service\quote_match.py") `
    (Join-Path $RagRoot "service\ticket_service.py") `
    (Join-Path $RagRoot "service\intent_classifier.py") `
    (Join-Path $RagRoot "service\store_contract.py") `
    (Join-Path $RagRoot "service\semantic_router.py") `
      (Join-Path $RagRoot "service\mixed_service.py") `
      (Join-Path $RagRoot "service\ask_graph.py") `
      (Join-Path $RagRoot "service\graph_tools.py") `
      (Join-Path $RagRoot "service\plan_service.py") `
    (Join-Path $RagRoot "service\routing_prototypes.json") `
    (Join-Path $RagRoot "service\start_retrieval_server.sh") `
    (Join-Path $RagRoot "service\stop_retrieval_server.sh") `
    "ubuntu@${HostName}:$RemoteApp/rag/service/"
  scp -i $Key -q -r (Join-Path $RagRoot "service\web") `
    "ubuntu@${HostName}:$RemoteApp/rag/service/"
scp -i $Key -q (Join-Path $RagRoot "eval\__init__.py") `
    "ubuntu@${HostName}:$RemoteApp/rag/eval/"
scp -i $Key -q (Join-Path $RagRoot "eval\runners\__init__.py") `
    (Join-Path $RagRoot "eval\runners\run_eval.py") `
    "ubuntu@${HostName}:$RemoteApp/rag/eval/runners/"
scp -i $Key -q (Join-Path $RagRoot "eval\cases\eval_questions.jsonl") `
    "ubuntu@${HostName}:$RemoteApp/rag/eval/cases/"

Invoke-RemoteBash "chmod +x $RemoteApp/rag/service/*.sh"

if ($Eval) {
    $bash = @"
set -euo pipefail
cd $RemoteApp
set -a
source .env
set +a
export HF_HOME=/home/ubuntu/.cache/huggingface
export TMPDIR=/tmp
export PYTHONPATH=rag
export PYTHONIOENCODING=utf-8
export LANG=C.UTF-8
.venv/bin/python -m eval.runners.run_eval --top-k $TopK
"@
    Invoke-RemoteBash $bash
    return
}

if (-not $QuestionFile) {
    $QuestionFile = Join-Path $RagRoot "fixtures\sample_question.txt"
}
if (-not (Test-Path $QuestionFile)) {
    throw "question file not found: $QuestionFile"
}

$localTmp = Join-Path $env:TEMP ("rag_question_{0}.txt" -f [guid]::NewGuid().ToString("N"))
$text = [IO.File]::ReadAllText((Resolve-Path $QuestionFile).Path).Trim()
if (-not $text) {
    throw "question file is empty: $QuestionFile"
}
[IO.File]::WriteAllText($localTmp, $text, $Utf8NoBom)
scp -i $Key -q $localTmp "ubuntu@${HostName}:$RemoteQuestion"
Remove-Item -Force $localTmp -ErrorAction SilentlyContinue

if ($Cold) {
    $bash = @"
set -euo pipefail
cd $RemoteApp
set -a
source .env
set +a
export HF_HOME=/home/ubuntu/.cache/huggingface
export TMPDIR=/tmp
export PYTHONPATH=rag
export PYTHONIOENCODING=utf-8
export LANG=C.UTF-8
.venv/bin/python -m retrieval.search_from_file $RemoteQuestion --top-k $TopK
"@
    Invoke-RemoteBash $bash
    return
}

$bash = @"
set -euo pipefail
cd $RemoteApp
chmod +x rag/service/start_retrieval_server.sh
if ! curl -sf http://127.0.0.1:$Port/health | grep -q '"model_ready":true'; then
  echo "[info] retrieval server not ready, starting (first load warms BGE-M3)..."
  bash rag/service/start_retrieval_server.sh
fi
.venv/bin/python - <<PY
import json
from pathlib import Path
import urllib.request

question = Path("$RemoteQuestion").read_text(encoding="utf-8").strip()
payload = json.dumps({"question": question, "top_k": $TopK}, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(
    "http://127.0.0.1:$Port/search",
    data=payload,
    headers={"Content-Type": "application/json; charset=utf-8"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=120) as resp:
    data = json.loads(resp.read().decode("utf-8"))
print("Q:", data["question"])
print("hits=%d  elapsed_ms=%s" % (len(data["hits"]), data.get("elapsed_ms")))
for i, h in enumerate(data["hits"], 1):
    preview = (h.get("text") or "").replace("\n", " ")
    if len(preview) > 160:
        preview = preview[:160] + "…"
    print("%d. %s / %s  sim=%.4f  chunk_id=%s" % (
        i, h.get("name"), h.get("theme"), float(h.get("similarity") or 0), h.get("chunk_id")))
    print("   " + preview)
PY
"@
Invoke-RemoteBash $bash
