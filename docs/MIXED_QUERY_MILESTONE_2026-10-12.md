# 最小混合问题支持

`/ask`新增单景点、显式复合需求处理，已部署在原127.0.0.1:8100服务。没有引入LLM分类、任意SQL、LangGraph或新的模型；现有分类器、数据边界闸、原型、阈值、单路径回答Prompt和/search查询/排序未修改。

## 流程与边界

`build_mixed_plan`按明确分句划分门票与文本需求，门票分句仍调用原有规则/语义分类器。只有存在独立的入场票价需求与独立的RAG主题需求时才创建双工具计划；“不问门票价格”等否定、停车餐饮等其他价格不主动加入ticket_sql。它是小范围的显式复合句支持，不保证能拆解任意自然语言问题。多价格需求、多景点和复杂依赖暂不支持。

计划包括ticket_question、rag_question、required_stores。两项工具顺序执行：票价调用已有try_ticket_answer，文本调用原search和answer_question。SQL仍是参数化、只读查询，TICKET_SQL和CATALOG_SQL保持原样。实体定位使用完整原问题，票价格式化仅使用价格子问题，避免将文本部分的“老人”误解为要求老人票的精确售价。

文本查询保留已定位景点名称并只包含文本子问题；混合路径的查询文字会改变，所以其片段可能与旧整句检索不同。/search本身以及单路径的检索文字、排序保持原样。没有加入新排序或重排。文本引用若涉及其他景点，该部分事实不展示。

两边的回答由服务分别加标题并拼接；SQL段保留ticket_raw原文、SQL1引用和采集时间，RAG段保留经原文摘录校验的S1等引用。票价无需再交给LLM重新改写。SQL或RAG一方失败不抹掉另一方已经得到的事实；用户需求的缺失部分单独说明。

## 状态与接口

新增响应字段：required_stores、tasks、entity_resolution。单路径required_stores只列原对应工具；混合route=mixed，每项task包含question、tool_called、state、answer_status、evidence_ids及必要的reason。

| state | 含义 |
|---|---|
| queried_with_evidence | 已执行查询，存在可引用的原文或经过校验的文本回答证据 |
| queried_no_evidence | 已查询，但没有能支持本子任务回答的引用证据；不表示整个数据库没有相关资料 |
| not_queried | 工具停用或实体未定位，未执行所需查询 |
| query_failed | 尝试调用工具但发生异常，不能据此断言记录不存在 |

tool_called表示进入工具函数；不等于已查景点票价字段。实体未唯一定位时可能已经读目录，ticket_lookup_executed仍为false，ticket_sql子任务state为not_queried；RAG也暂停以避免景点混用。

answer_status与取证状态独立：即使查询到快照，也可能无法确认实时价/具体票种，或只回答一部分文本需求。所有子任务answered才返回整体answered；否则整体insufficient_evidence，但保留有证据的回答。第29题这种部分拒答是正确行为，不因整体status而判失败。

## 验收与回归

35项测试通过，包括原有服务契约、固定SQL、单请求编码与新增加的计划/合并/失败隔离检查。55题计划预检中，30题挑战集和25题回答集仅第27—30题生成双工具计划。

四题在线检查通过，SQL原文与实际数据库只读查询对照，所有RAG引用摘录均核对为来源文本的连续原文，引用景点与SQL目标一致：

| 题号 | SQL证据 | 文本部分 | 结果 |
|---|---|---|---|
| 27 | 龙门石窟：门票￥90起 | 游览路线，visit_tips引用 | 两部分均回答 |
| 28 | 老君山景区：门票￥100起 | 历史，overview/history_culture引用 | 两部分均回答 |
| 29 | 凤翔温泉：门票￥78起 | 未检索到支持轮椅设施的证据，仅该部分无法确认 | 票价保留，部分拒答 |
| 30 | 龙门石窟：门票￥90起 | 老人免票，preferential引用 | 普通票原文与优待条件分别回答 |

随后完成30题挑战集回归：26道单路径的路径、片段ID/相似度和structured_data不变；第25题说明现有目录未匹配，建议核对名称，第26题说明一次只支持单景点并列出龙门石窟、老君山景区供选择。原25道回答集的路径及Top5上下文不变；73题/search Top20顺序及相似度完全不变。生成文字可能变化，新答案人工分数为空，不继承旧评分。

全量在线结果在 `rag/eval/reports/mixed_v1_live_run1.json/.md`。其后补强SQL停用/异常时的文本子问题隔离，避免把价格需求再次交给RAG；这仅调整故障分支，9项针对测试和四题在线复验结果另存 `mixed_v1_live_fault_scope_followup.json/.md`。原全量结果不覆盖。

随后用户对最新4题复验回答按“是否正确覆盖全部子问题”逐题复评，六项评分全部pass，共24 pass、0 fail、0 na，本轮混合问答验收4/4通过。评分已写入mixed_v1_live_fault_scope_followup.json/.md，回答原文与证据未改；未评分版本另存_unreviewed文件。该评分只绑定最新四题回答，不转移到首次全量报告中的其他版本回答。原30题/25题回归报告其余新答案仍未重新评分。

混合v1冻结在 `rag/eval/baselines/mixed_v1/`，包含当前源码、路由配置、用例、最新四题用户评审、原始未评分回答、全量回归及SHA-256清单，不含.env或密钥。30题仍为合成挑战集，不能称为真实用户盲测或整体系统准确率。

第29题明确：queried_no_evidence表示查过但没有支持轮椅需求的证据；RAG仍可返回其他主题/景点的片段，不等于零命中，更不表示不存在轮椅设施。

下一阶段按 `docs/LANGGRAPH_TOOL_CONTRACT.md` 接入有明确输入输出的检索和门票工具；本文验收版本尚未接入LangGraph。

## 配置与回退

`RAG_MIXED_ENABLED=1`服务器启用。设为0并重启只关闭混合计划；原semantic flag、阈值0.60/分差0.06不变。第25/26题的新提示独立保留。若需恢复部署前源码，备份为 `deploy/backups/mixed-2026-10-12/`；未复制.env或密钥。旧LangGraph删除状态不变。
