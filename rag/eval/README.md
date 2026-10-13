# eval 目录

Python 文件已按用途实际移动到以下目录；题集、报告和冻结快照保持原路径。

| 目录 | 内容 |
|---|---|
| runners/ | 运行评测与检索审计，如 eval_semantic_routing.py、run_eval.py |
| builders/ | 构建题集：build_answer_holdout.py、build_routing_cases.py |
| reviews/ | 录入历史评分：record_answer_v1_review.py |
| integration/ | 在线集成回归：verify_*_live.py |
| tests/ | 单元测试：test_*.py |
| cases/ | 题集及元数据 |
| reports/ | 运行输出和评分记录 |
| candidates/ | 候选版本及提升记录 |
| baselines/ | 不可变快照；验收状态以 manifest 为准 |
| catalog/ | 按能力分类的导航与文件清单 |

## 运行方式

在项目根目录设置 PYTHONPATH=rag，然后运行：

```sh
python -m eval.runners.run_eval --top-k 3
python -m eval.runners.eval_semantic_routing --help
python -m eval.integration.verify_plan_live --help
python -m unittest discover -s rag/eval/tests -p 'test_*.py'
```

PowerShell 设置方式：`$env:PYTHONPATH="rag"`。旧的 eval.run_eval 入口已迁移为 eval.runners.run_eval，不保留根目录兼容壳。在线运行器可能调用数据库与模型，整理目录不需要重跑它们。

按能力浏览：[检索](catalog/retrieval.md)、[路由](catalog/routing.md)、[回答](catalog/answer.md)、[门票 SQL](catalog/ticket_sql.md)、[混合](catalog/mixed.md)、[问答图](catalog/langgraph.md)、[规划](catalog/planning.md)。

冻结包中的历史源码不随目录重构修改。旧报告里的路径是当时运行的证据，保留原样。新增能力先锁定评分维度，整批评完再决定是否修改。

新能力：[旅游 Agent 五题候选报告](reports/travel_agent_v1_live.md)，[manifest](candidates/travel_agent_v1/manifest.json)，[工具测试](tests/test_travel_agent.py)。

Agent v1 已验收：[冻结 manifest](baselines/travel_agent_v1/manifest.json) · [人工评分](reports/travel_agent_v1_acceptance.md)。原五题报告保留，候选已提升。

百度地图：[五题候选报告](reports/baidu_maps_v1_live.md)、[接口探测](reports/baidu_maps_provider_probe.json)、[测试](tests/test_baidu_maps.py)、[候选 manifest](candidates/baidu_maps_v1/manifest.json)。

配额/多日/重规划：[Mock运行器](runners/eval_trip_budget_mock.py)、[测试](tests/test_trip_budget.py)、[候选](candidates/trip_budget_v1/manifest.json)。运行器不会调用百度或LLM。

多日游自然语言补全：[说明](../../docs/PLAN_CHAT_NL_INTAKE.md)、[测试](tests/test_plan_chat.py)、[候选](candidates/plan_chat_v1/manifest.json)。入口 `POST /plan/chat`，默认关闭；只用注入的假抽取器/假地图/假 planner 测试，不调用 LLM 或百度。
