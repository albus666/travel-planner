import base64,json,hashlib
from pathlib import Path
names=['rag/service/plan_chat.py','rag/service/web/app.js','rag/service/web/index.html','rag/service/web/style.css','rag/eval/tests/test_plan_chat.py']
p=Path('rag/eval/reports/optional_departure_v1.json');r=json.loads(p.read_text(encoding='utf-8'));r['browser_checks']=['A/B/C option buttons','custom input last','skip proceeds to guide'];r['file_sha256']={n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in names};p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
names=['rag/eval/reports/optional_departure_v1.json']
for n in ['docs/PLAN_CHAT_NL_INTAKE.md','docs/WEB_TEST_MVP.md']:
 with Path(n).open('a',encoding='utf-8') as f:f.write('\n\n## 可选出发点与追问选项（2026-10-13）\n\n自然语言规划的地点追问新增 clarification/options；最后一项为自己填写，可展开文本框。可以选跳过出发点，只给攻略，也支持明文“只给攻略/忽略出发点”。新会话不会因提供地点名自动搜索：确认交通模式后才允许地图解析。没有增加酒店品牌的特殊搜索触发。\n\nChatRequest 可传 planning_mode=guide/route。攻略模式复用已有景点RAG草案，支持连续1–7天及跨日去重，保留引用；所有arrival_time、departure_time、visit_duration_minutes为null，time_check=not_checked，不调用地图、不承诺整日可行性，状态guide_draft。改景点时继续攻略模式，显式切换交通模式后才查路线。预算、无障碍等不可验证约束仍会阻塞，跳过出发点不会默默删除这些要求。\n\n167项测试通过；合成会话+真实本地RAG三日攻略通过，未调用LLM或百度；浏览器模拟验证选项、自填和跳过分支。报告 rag/eval/reports/optional_departure_v1.json；人工评分未填写，未修改冻结基线或重跑73/25/30。\n')
 names.append(n)
data={n:base64.b64encode(Path(n).read_bytes()).decode() for n in names}
s="set -euo pipefail\ncd /home/ubuntu/apps/travel-planner\n.venv/bin/python - <<'PY'\nfrom pathlib import Path\nimport base64,json,hashlib\ndata=json.loads("+repr(json.dumps(data))+")\nfor n,b in data.items():Path(n).write_bytes(base64.b64decode(b))\nr=json.loads(Path('rag/eval/reports/optional_departure_v1.json').read_text())\nfor n,h in r['file_sha256'].items():assert hashlib.sha256(Path(n).read_bytes()).hexdigest()==h,n\nprint('Optional departure docs, code and report hashes verified')\nPY\n"
Path('tmp/finalize_optional_departure.sh').write_text(s,encoding='utf-8')
