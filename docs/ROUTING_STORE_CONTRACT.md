# 问题路由的数据边界

本表先于分类器变更确定。分类标签是查询应访问的资料store，不是“模型看起来像什么意图”。SQL与RAG数据都来自采集快照，均不能确认实时状态。

| 问题需要的数据 | 原始存储 | 当前回答访问的store | 路径边界 |
|---|---|---|---|
| 景点门票原文、价格资料、明确售价 | `v2.poi_details.ticket_raw` | `v2.poi_details.ticket_raw` | 固定只读SQL，原文保留，不统一成金额 |
| 实时售价、成人/儿童等特定票种售价 | 同上，但不一定包含所问精确事实 | `v2.poi_details.ticket_raw` | 可返回采集原文，不能保证实时或票种对应，仍须拒绝确认 |
| 免票、优待、优惠资格与条件 | `v2.poi_details.preferential`；派生主题片段 | `v2.rag_chunks`，`theme=preferential` | RAG；不得用ticket_raw起价替代优惠条件 |
| 游客公告、退款通知、入园须知 | `notice_text`等；派生主题片段 | `v2.rag_chunks`，`theme=notice/entry_policy` | RAG；公告里的“门票”“退票”不能触发票价SQL |
| 景点介绍、历史文化 | 介绍原文；派生主题片段 | `v2.rag_chunks`，`theme=overview/history_culture` | RAG |
| 游览路线、游玩建议 | 介绍原文；派生主题片段 | `v2.rag_chunks`，`theme=visit_tips`等 | RAG |
| 寄存、WiFi、停车、园内交通等设施 | `facilities`与介绍原文；派生主题片段 | `v2.rag_chunks`，`theme=facilities`等 | RAG；园内交通票费不是景区门票原文 |
| 当前开放、房态或其它实时信息 | 没有实时数据源 | 现有RAG资料或拒答 | 不能改查ticket_raw后确认实时状态 |

**实体与store分类分开**：未收录或简称歧义的票价问题仍属于ticket_raw store，但完整名定位失败必须澄清/拒答，不能选择相似景点。现阶段没有别名表。

第一阶段纯分类器仅包装原有 `is_ticket_question`，保持全部历史行为。路由评测独立标记expected_store和expected_resolution；之后如增设边界闸或语义召回，按版本另报，不覆盖规则版结果。
