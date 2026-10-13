# Agent 设施问题路由修复（2026-10-13）

## 缺陷

`/agent/ask` 问设施价格——例如「老君山景区停车场多少钱」——只调 `ticket_snapshot` 和 `poi_details`，**不调 `local_search`**，因此拿不到设施条目，最终返回 `本次未取得可引用的回答证据，无法确认。`

原因在提示词，不在数据、也不在检索：

- `PROMPT` 只写了「介绍历史优先 local_search」，**完全没提设施/停车**，模型把「停车场多少钱」当成票价问题处理。
- `ticket_snapshot` 的描述是「查询本地已采集门票原文」，`local_search` 的描述是「检索已确认景点的本地介绍、历史、路线片段」——两者都没说明设施归谁。

资料本身是齐备的：`poi-77806-facilities_struct` 含「停车场…参考价格：¥10/次…蓝牌车：10元/次；黄牌车：20元/次；新能源车：5元/次」，在该问题的检索里排名第一（相似度 0.7506）。

## 修复

只改 `rag/service/travel_agent.py` 的提示词与工具描述：

| 改动 | 内容 |
|---|---|
| `PROMPT` | 设施（停车场、充电桩、行李寄存、WiFi、卫生间、吸烟区、园内交通及其参考价格）明确归 `local_search`；并写明 `ticket_snapshot` 只覆盖门票，问设施价格时**必须再用** `local_search`，两者可一起调用 |
| `local_search` 描述 | 由「介绍、历史、路线片段」扩为含设施及其参考价格 |
| `ticket_snapshot` 描述 | 显式声明不含停车、寄存等设施价格 |
| `poi_details` 描述 | 写明是详情快照，不保证实时营业 |

未改动：工具集合、权限、调用预算（6 次工具 / 5 轮模型 / 100 秒）、引用校验逻辑、检索与排序、其他任何端点。

## 线上验证

端点 `https://agentfolio.duckdns.org/travel/agent/ask`，4 个设施问题 **4/4 调用 `local_search` 且 `evidence_found`**：

| 问题 | 工具 | 结果 | 引用 |
|---|---|---|---|
| 老君山景区停车场多少钱 | `local_search` | evidence_found | 参考价格 ¥10/次、蓝牌车/黄牌车/新能源车 |
| 老君山景区停车场多少钱（重跑） | `local_search` | evidence_found | 同上，稳定复现 |
| 老君山景区停车费怎么收 | `local_search` | evidence_found | 同上 |
| 老君山景区行李寄存多少钱 | `local_search` | evidence_found | 小柜20元/门、中柜25元/门、大柜30元/门 |

## 已验收用例回归

`travel_agent_v1` 的 5 个已验收用例重跑，**5/5 状态与冻结基线完全一致**：

| 用例 | 基线 | 现在 |
|---|---|---|
| comments | insufficient_evidence | insufficient_evidence |
| ambiguous | needs_clarification | needs_clarification |
| weather | evidence_found | evidence_found |
| unknown | needs_clarification | needs_clarification |
| mixed | evidence_found | evidence_found |

单测：`rag/eval/tests/test_travel_agent.py` 18 项通过，新增 1 项锁定设施路由契约（`local_search` 描述含「停车」、`ticket_snapshot` 描述声明「不含停车」、`PROMPT` 含「设施」与两个工具名）。

## 冻结影响（如实记录）

冻结 manifest `rag/eval/baselines/travel_agent_v1/manifest.json` 里 `rag/service/travel_agent.py` 的记录哈希是 `92c48a40b59e6e734c68b1669e27124a079f0b922a90ae4584a93d95d92e241e`，当前文件哈希已不同——**PROMPT 和工具描述变了，冻结快照不再逐字节对应当前部署**。

处理方式：

- 冻结目录 `rag/eval/baselines/travel_agent_v1/` **原样保留，不修改**；它是那一版的历史记录。
- 不重新冻结，也不把本次当作用户验收：新回答的 `human_review` 仍为空。5 个用例状态一致只能说明没有明显回归，不能替代人工评分。
- 原验收表对 comments 用例的「引用支持」本就是 `na`，所以该用例 0 引用不构成回归。

## 未做

- 未重跑 73/25/30 问答检索回归（本次未触碰检索与 `/ask` 链路）。
- 未修 `AGENT-V1-01`（weather_code 数值未翻译成中文天气描述），仍是记录不修的低severity项。
- 未做通用设施/票价路由的语义分类，只在提示词与工具描述层面给出边界。

原始数据见 `rag/eval/reports/travel_agent_facility_routing_fix.json`。
