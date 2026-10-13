import json,hashlib
from pathlib import Path
root=Path('.')
r=json.loads(Path('rag/eval/reports/baidu_maps_v1_live.json').read_text())
p=json.loads(Path('rag/eval/reports/baidu_maps_provider_probe.json').read_text())
expected=['evidence_found','needs_clarification','time_checked_draft','constraint_conflict','needs_clarification']
assert [c['response']['status'] for c in r['cases']]==expected
assert all(x['result']['state']=='queried_with_evidence' for x in p)
for c in r['cases'][2:4]:
 assert len(c['response']['legs'])==3
 assert {s['name'] for s in c['response']['schedule']}=={'龙门石窟','洛阳博物馆'}
text=['# 百度地图与交通规划五题报告','', '日期：2026-10-13。合成在线冒烟，待人工评分；120 项服务器单测通过。', '', '## 固定评分口径', '', '地点隔离、坐标与单位、引用与时效、约束与回程、缺证据处理、需求覆盖。每项 pass/fail/na；本报告不代填人工分数。', '', '正常路线题使用评测显式选择的火车站和博物馆坐标；生产交互需用户确认同名地点。','', '## 百度权限探测', '', '|动作|结果|','|---|---|']
for x in p:text.append('|'+x['action']+' '+str(x['arguments'].get('mode',''))+(' advanced' if x['arguments'].get('advanced') else '')+'|'+x['result']['state']+'|')
for c in r['cases']:
 text+=['','## '+c['id'],'','自动状态：'+c['response']['status'],'','人工评分：待填写。','','### 请求','','```json',json.dumps(c['request'],ensure_ascii=False,indent=2),'```','','### 完整结果与证据','','```json',json.dumps(c['response'],ensure_ascii=False,indent=2),'```']
text+=['','## 验证范围','','五题状态符合预期；正常/超时两题均保留两个必去景点并含三段往返路线。/plan 澄清和 /search 返回结果冒烟通过。原 /ask、/search、/plan HTTP 处理函数 AST 未改动；本轮未重跑完整73/25/30题集。','','只有查询时交通估算，不是未来交通预测或完整日程可行性承诺。未实现动态重规划；当前为待人工验收候选。']
Path('rag/eval/reports/baidu_maps_v1_live.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
for name in ['docs/PROJECT_MEMORY.md','docs/PROJECT_STATUS_AND_ARCHITECTURE.md']:
 with Path(name).open('a',encoding='utf-8') as f:f.write('\n\n## 2026-10-13 百度地图候选已部署\n\n新增 /maps/query、/plan/with-routes；Agent 新增地点与路线工具。支持四种交通、矩阵排序、往返预算校验；超时保留必去，缺少游览时长追问。120项单测、11项接口探测、5题在线状态验证通过，人工评审待完成，不冻结。原问答/检索/规划入口保持原逻辑。本轮未重跑完整73/25/30题，尚无动态重规划或未来交通预测。详情见 [BAIDU_MAPS_V1.md](BAIDU_MAPS_V1.md)。\n')
with Path('rag/eval/README.md').open('a',encoding='utf-8') as f:f.write('\n百度地图：[五题候选报告](reports/baidu_maps_v1_live.md)、[接口探测](reports/baidu_maps_provider_probe.json)、[测试](tests/test_baidu_maps.py)、[候选 manifest](candidates/baidu_maps_v1/manifest.json)。\n')
files=['rag/service/baidu_maps.py','rag/service/route_plan.py','rag/service/travel_agent.py','rag/service/retrieval_server.py','rag/eval/tests/test_baidu_maps.py','rag/eval/reports/baidu_maps_provider_probe.json','rag/eval/reports/baidu_maps_v1_live.json','rag/eval/reports/baidu_maps_v1_live.md','docs/BAIDU_MAPS_V1.md','rag/client/maps_query.py','rag/client/run_on_server.ps1']
manifest={'version':'baidu_maps_v1','status':'deployed_pending_human_review_not_frozen','dataset_origin':'agent_generated_synthetic_not_real_user_blind','human_review':None,'unit_tests_passed':120,'provider_probes_passed':11,'live_cases_expected_statuses_passed':5,'feature_flag':'RAG_MAPS_ENABLED=1','full_73_25_30_rerun':False,'known_limitations':['query-time estimates, not future traffic forecasts','seven POI planning pool','user visit duration required','no automatic constraint repair or replanning','opening, reservations, budget and accessibility not validated','coordinate centers may differ from entrances','duplicate full names require client point confirmation','weather coordinate strategy unchanged'],'file_sha256':{n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in files}}
d=Path('rag/eval/candidates/baidu_maps_v1');d.mkdir(parents=True,exist_ok=True);(d/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Five cases and 11 probes validated; report and candidate recorded.')
