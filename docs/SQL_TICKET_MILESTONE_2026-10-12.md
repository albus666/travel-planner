# 只读门票查询（2026-10-12）

用户25题逐项评分已录入并冻结为 `rag/eval/baselines/answer_v1/`。本次新增的是 `/ask` 的规则式 SQL 路由，未改 Embedding、向量排序、LLM 模型或 Prompt。

## 查询与约束

问题同时提及门票/票价及价格/资料/原文等意图时，读取完整景点名称目录，定位唯一景点，再固定参数化查询 `v2.poi_details.ticket_raw`。单次连接为数据库只读事务，设置5秒查询超时；没有任意SQL入口，没有LLM自主工具调用。

仅展示原文，不取 ticket_data 的解析金额来覆盖文案。例如龙门石窟返回“门票￥90起”，不等同90元成人票或今日票价。来源优先详情 `detail_meta.source_url`，否则使用景点目录来源；采集时间取详情真实时间并显示为+08:00。

空ticket_raw、缺详情、未识别唯一景点分别明确无法确认；不推断成免费。实时价格或特定票种问题可附采集原文，但不足以确认所问价格，status为insufficient_evidence。第一版要求完整名称，不处理简称或多景点票价汇总。`RAG_SQL_TICKET_ENABLED=0` 可关闭该路由；回退部署前入口也可恢复原流程。

## 验证与回归

16项单元测试通过，覆盖原7项回答契约及SQL规则、原文/空值/元数据、实体歧义、注入字符串不进入SQL、只读连接、禁用开关、SQL跳过Embedding/LLM，以及原25题保持向量路由。

10道真实门票题与数据库原字段逐项对照通过：龙门原文、老君山原文、植物园免费原文、陆浑带限定文案、两例空字段、简称、不存在景点、实时成人售价、多景点问题。查询前后门票字段及来源摘要一致。结果是契约验证，不代替人类业务审核。

首次集成回归发现原25题中的09题（园内交通是否包含在大门票中）被误路由为门票价格；已修正，交通/索道/缆车等混合费用问题保留向量路径。失败结果保留在 `answer_holdout_v1_2026-10-12_run2_sql.json`，不删除或改写；修正后的完整回归报告为 run3_sql，评审不能沿用旧答案分数。

最终集成回归：原25题全部保持vector路由，19题answered、6题insufficient_evidence；代码与数据摘要在运行前后不变。73题/search全部top-20的chunk_id顺序及相似度与冻结基线完全一致。对照结果为 `answer_v1_vs_sql_comparison.json`，新的生成文本仍待人工复核，不能把原25题评分直接转移。

## 使用与回退

示例：“龙门石窟的门票资料记载是什么？”——原有 `/ask` 接口，无新端口。详情见 `rag/README.md`。

入口部署前备份：`deploy/backups/sql-ticket-2026-10-12/retrieval_server.py`。

```bash
cp deploy/backups/sql-ticket-2026-10-12/retrieval_server.py rag/service/retrieval_server.py
bash rag/service/stop_retrieval_server.sh
bash rag/service/start_retrieval_server.sh
```

或者设置开关后重启。两种方式均不修改数据库和检索代码。
