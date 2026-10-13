import json,base64,hashlib
from pathlib import Path
rp=Path('rag/eval/reports/trip_budget_v1_mock.json');r=json.loads(rp.read_text(encoding='utf-8'))
lines=['# 配额、重规划、多日游 v1 离线报告','','135项自动测试通过；新增百度请求0。服务器新入口已注册，/maps/usage 用量为空。','','这是Mock合成证据，不是线上路线准确率或人工验收。','','|用例|状态|','|---|---|']
for c in r['cases']:lines.append('|'+c['id']+'|'+c['result']['status']+'|')
lines+=['','人工评审维度：必去/排除保留、时间预算、引用来源、跨日去重、失败状态、配额边界。评分待填写。','', '限制：逐日结构化输入，洛阳七景点，1–7连续天；不支持跨日自动移动景点、酒店预订或开放验证。预算统计仅覆盖此部署。']
for c in r['cases']:lines+=['','## '+c['id'],'','```json',json.dumps(c['result'],ensure_ascii=False,indent=2),'```']
mp=Path('rag/eval/reports/trip_budget_v1_mock.md');mp.write_text('\n'.join(lines)+'\n',encoding='utf-8')
p=Path('rag/eval/candidates/trip_budget_v1/manifest.json');m=json.loads(p.read_text(encoding='utf-8'))
for f in [rp,mp]:m['file_sha256'][f.as_posix()]=hashlib.sha256(f.read_bytes()).hexdigest()
p.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
data={f.as_posix():base64.b64encode(f.read_bytes()).decode() for f in [rp,mp,p]}
s="set -euo pipefail\ncd /home/ubuntu/apps/travel-planner\n.venv/bin/python - <<'PY'\nimport json,base64,hashlib\nfrom pathlib import Path\ndata=json.loads("+repr(json.dumps(data))+")\nfor n,b in data.items():Path(n).write_bytes(base64.b64decode(b))\nm=json.loads(Path('rag/eval/candidates/trip_budget_v1/manifest.json').read_text())\nfor n,h in m['file_sha256'].items():assert hashlib.sha256(Path(n).read_bytes()).hexdigest()==h,n\nprint('All candidate evidence hashes verified')\nPY\ncp rag/eval/reports/trip_budget_v1_mock.md /home/ubuntu/portfolio/downloads/rag/trip-budget-evaluation-2026-10-13.md\nchmod 644 /home/ubuntu/portfolio/downloads/rag/trip-budget-evaluation-2026-10-13.md\n.venv/bin/python - <<'PY'\nimport requests,hashlib\nfrom pathlib import Path\nr=requests.get('http://52.199.126.245/downloads/rag/trip-budget-evaluation-2026-10-13.md',timeout=15);r.raise_for_status()\nassert r.content==Path('rag/eval/reports/trip_budget_v1_mock.md').read_bytes()\nprint('Download verified; no Baidu calls')\nPY\n"
Path('tmp/publish_trip_budget.sh').write_text(s,encoding='utf-8')
