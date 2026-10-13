# 数据store路由：实施与评测

## 实施顺序

1. 数据边界先写在 `docs/ROUTING_STORE_CONTRACT.md`。SQL只读取ticket_raw；优待、公告、介绍、路线、设施走RAG主题。票价主题不在347条chunk里，不能拿其它主题替代价格原文。
2. 纯 `classify_intent` 内部调用原 `is_ticket_question`，返回枚举store、method和reason；原规则逻辑不改。阶段2的19项测试与25+73共98题分类等价检查通过。
3. 新增58道按expected_store标注的题，实体定位另设expected_resolution/expected_poi_id。30道dev、28道holdout，涵盖12道改写票价。合成题由代理设计，标签待用户审核，不代表真实用户独立盲测。
4. 旧规则出现14个票价漏判（其中12道改写全部漏判）与7个优待/公告误判；26道价格题的实体标签无定位错误，未引入别名表或擅自把“龙门”映射到龙门石窟。
5. 先加由数据表推导的RAG边界闸，再增加同一BGE-M3上的票价/非票价范例kNN。22个范例，与路由题无完全重复；每类最近3个范例余弦相似度取均值。仅用dev选阈值0.60、两类分差0.06；余弦分数不是概率。
6. 没有增加LLM分类兜底或其缓存：当前评测没有证明规则+语义仍不够，触发条件未满足。回答用DeepSeek保持原配置与Prompt。

## 对照结果

| 版本 | 58题store正确 | 票价假阳性 | 票价假阴性 | 12道改写正确 |
|---|---:|---:|---:|---:|
| 原规则 / 纯分类器包装 | 37 | 7 | 14 | 0 |
| 仅加store边界闸 | 44 | 0 | 14 | 0 |
| 边界闸 + BGE-M3语义召回 | 58 | 0 | 0 | 12 |

语义候选v1虽然58题正确，但原98题中两道入园政策误路由；失败结果保留。按notice/entry_policy边界补入“实名、分时、规定、限制”后，v2的原98题分类完全不变；holdout28/28匹配。阈值没有用holdout选择，边界闸曾根据历史回归错误修正，因此仍需要更独立的新题检验泛化。

## 在线验证

23项单元测试通过，包含纯分类器无DB调用、SQL固定参数与原文、边界闸、kNN阈值、向量不被修改、同请求只编码一次以及search复用向量。

8个在线路由样本通过。原25题仍全部RAG，Top 5片段ID及相似度与SQL阶段基线一致；73题/search top-20的ID及相似度完全一致。生成文字可能变化，未沿用之前的人工分数，报告留human_review=null。

改写票价在线样本约0.30～0.34秒；离线单次编码中位约335ms。不是“所有请求新增延迟为0”：原规则可直达SQL的题仍不编码；边界明确的RAG题仍编码一次；需要语义判断的题编码一次，若随后走RAG就把同一向量传入search。原型在服务启动时一次编码，复用同一缓存模型，不新增BERT或LLM分类模型。

## 当前配置与回退

`RAG_SEMANTIC_ROUTING_ENABLED=1` 已启用该实验，`RAG_SQL_TICKET_ENABLED` 的原设置不变。设置前者为0并重启可恢复原规则分类模式（包括原规则已知的漏判/误判）。没有改变实体resolve_poi，也没有任意SQL输入入口。

部署前代码在 `deploy/backups/routing-2026-10-12/`。只保存RAG源码和路由配置元信息，未复制密钥。旧LangGraph代码仍已删除，没有恢复。

## 留档

- `rag/eval/cases/routing_store_v1.jsonl` 与manifest：58题、store和实体标签。
- `rag/eval/reports/routing_legacy_rule_v1.json`：纯规则结果。
- `rag/eval/reports/routing_boundary_rule_v2.json`：仅边界闸结果。
- `rag/eval/reports/routing_semantic_candidate_v1.json`：含两道历史回归误判的候选。
- `rag/eval/reports/routing_semantic_candidate_v2.json`：修正后的dev/holdout和98题回归。
- `rag/eval/reports/routing_v2_live_regression.json`：在线8题、25题上下文和73题检索回归。
- `rag/eval/baselines/routing_candidate_v2_sources/`：离线候选源码及版本摘要。

通过这份合成集只说明当前样本上的store选择符合标签，不代表整体回答正确率100%。下一批应增加由用户独立提出的改写、跨字段混合问题及别名/歧义问题，先审核标签再评测，不依据本轮结果自动引入LLM兜底。

后续按用户“你自己生成”的要求完成新增30题合成挑战。当前v2已冻结；26题单store匹配，4题混合问题双store完整覆盖为0。详细结果见 `docs/ROUTING_CHALLENGE_2026-10-12.md`，回答仍待人工评分；这批不标为真实用户盲测。
