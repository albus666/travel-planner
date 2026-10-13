# 多日游自然语言补全 v1（候选，待人工评审）

替换 `docs/TRIP_BUDGET_V1.md` 中「不支持只输入一句自然语言就自动补全整段旅行」的限制。该文档与其候选 manifest 保持原样，作为当时状态的记录；本版单独记录。

新入口 `POST /plan/chat`：`RAG_PLAN_CHAT_ENABLED=1` 开启（默认 `0`），并且需要 `RAG_MAPS_ENABLED=1`。原 `/ask`、`/search`、`/plan`、`/plan/multi-day`、`/plan/with-routes`、`/plan/replan`、`/maps/*`、`/agent/ask` 处理函数未改动。

## 为什么需要这一层

`/plan/multi-day` 要求逐日提交结构化条件，其中 `departure_point`/`end_point` 必须是带 `bd09ll` 坐标的点对象、`visit_minutes` 要逐景点填写。坐标用户无法自行提供，所以「帮我安排三天」此前走不通。

本版把 `rag/service/plan_chat.py`（此前已写好但未接入服务）接到 HTTP 上，并把它的入场策略从「逐项追问」改成「能补则补」。

## 流程

1. LLM 只做抽取，返回 `Slots`，不规划、不调工具。
2. `autofill()` 补齐能安全默认的槽位，并逐条记录 `assumptions`。
3. `blocking_issues()` 只返回真正无法默认的阻塞项。
4. 无阻塞项时用百度地点检索解析出发/返回点：唯一全名命中直接规划；同名多候选必须由用户选编号。
5. `compile_trip()` 生成逐日 `RoutePlanRequest`，交给已有 `plan_trip_days()`（`multi_day_v1`：跨日去重、后续必去预留、每日有界重规划）。

## 自动补全规则

| 槽位 | 未说明时的处理 |
|---|---|
| city | 按洛阳（`洛阳市` 归一化为 `洛阳`） |
| days | 1 天 |
| start_date | 明天（北京时间）；后续日期按天递增 |
| companions | `未说明` |
| transport | 公共交通 |
| pace / preferences | 沿用 schema 默认：轻松 / 不限 |
| start_time / end_time / visit_minutes | 沿用默认 09:00–18:00 / 90 分钟 |

每次响应都带 `assumptions`，逐条写明「你未说明、本次替你假设了什么」。浏览器或客户端必须把它展示给用户，不能简化成无条件行程。

## 仍然必须追问的项

这些要么无法默认，要么不能替用户决定：

- **出发/返回点**：必须能地理编码成坐标；只说「酒店」「家」不算具体地点；目前各晚需同一地点，不支持跨夜换酒店。
- **同名候选**：多个同名结果（例如洛阳站与同名公交站）必须由用户选编号，不默认取第一条。
- **城市**：非洛阳。
- **开始日期已过去**。
- **必去/排除的景点名未唯一命中**：不展开简称、不替换相似景点。
- **必去与排除冲突、必去数量超过天数与节奏允许的站点数**。
- **`unsupported` 限制**：预算、无障碍、各景点不同时长、多个交通方式、不同住宿、指定日期开放等当前 schema 不能表达或核实的硬约束。
- **结束时间不晚于开始时间**。

## 与旧版的行为差异

- 去掉了强制「确认」这一轮。补齐后的条件不再等用户回「确认」，而是在拿到出发/返回点后直接出草案，`assumptions` 随响应返回以便纠正。这减少了轮次，代价是用户不再有机会在调用地图前预审条件。
- 常规路径由「六项逐条追问」缩短为：一句自然语言 → （只在需要时）一次地点追问 → 行程。

## 输出边界

- 车程是查询时估算，不是未来出发日期的路况预测。
- 逐日游览时长来自默认或用户填写，不是景区建议或开放时间。
- 未核实开放、预约、排队、体力、预算与整段旅行可行性。
- 候选池仍为七个景点全名，不代表全市覆盖；天数超过候选容量时返回 `unplanned_days`，不用无证据景点填充。
- 会话状态存 SQLite（默认 `var/plan_chat.sqlite3`，可用 `PLAN_CHAT_DB` 指定），保留 24 小时、最多 20 轮。

## 调用

```powershell
python rag/client/plan_chat_query.py --question "帮我安排三天，从洛阳站出发，带爸妈"
python rag/client/plan_chat_query.py --question "选1" --session-id <上一轮返回的 session_id>
```

## 验证

新增 `rag/eval/tests/test_plan_chat.py` 15 项，全部通过；用注入的假抽取器、假地图与假 planner，不调用 LLM 或百度。

全量 `python -m unittest discover -s rag/eval/tests -p 'test_*.py'` 在本机为 150 项、6 项错误。这 6 项全部是 `test_trip_budget.BudgetTests` 的 `tearDown` 清理错误：`MapBudget` 的 `connect()` 从不关闭连接，Windows 无法删除仍被占用的 `budget.sqlite3` 临时文件。它发生在测试断言之后，与 plan_chat 无关；Linux 上可删除仍打开的文件，所以服务器此前 135 项通过。（该连接泄漏本身是 `map_budget.py` 的真实缺陷，本版未修改它。）

本版未重跑 73/25/30 问答检索回归；未修改任何已冻结基线。


## 2026-10-13 服务器部署记录

本地入口、客户端和15项测试已同步至服务器，RAG_PLAN_CHAT_ENABLED=1 已启用并重启，/health model_ready=true。服务器全量150项测试全部通过（Linux）；上面的本机Windows测试记录保留。HTTP入口已响应，但真实抽取模型返回HTTP402 Insufficient Balance，未成功抽取槽位，故不能记为真实对话端到端通过。部署验证没有新增百度调用。待现有模型账户恢复余额后再少量验证；未重跑73/25/30，人工评分仍为空。报告：rag/eval/reports/plan_chat_deployment.json。

## 2026-10-13 会话地点复用修复

已确认地点保存 query/city/point，后续只修改景点时复用坐标；用户明确更换起点才重新确认。候选选择支持编号、唯一完整名称或完整“名称 — 地址”，同名名称仍要求编号。旧会话可从既有行程首段来源恢复起点。模型抽取收到已解析条件及已确认地点上下文，明确替换旧景点会加入排除。

159项测试通过；用用户既有会话副本和真实抽取模型验证“天子驾六博物馆我去过了，换个行不”保留洛阳站、排除旧景点，不查百度。该验证规划工具为Mock，不记为新行程线上验收；未修改原会话。报告 rag/eval/reports/chat_location_fix.json。服务器已重启加载修复。


## 可选出发点与追问选项（2026-10-13）

自然语言规划的地点追问新增 clarification/options；最后一项为自己填写，可展开文本框。可以选跳过出发点，只给攻略，也支持明文“只给攻略/忽略出发点”。新会话不会因提供地点名自动搜索：确认交通模式后才允许地图解析。没有增加酒店品牌的特殊搜索触发。

ChatRequest 可传 planning_mode=guide/route。攻略模式复用已有景点RAG草案，支持连续1–7天及跨日去重，保留引用；所有arrival_time、departure_time、visit_duration_minutes为null，time_check=not_checked，不调用地图、不承诺整日可行性，状态guide_draft。改景点时继续攻略模式，显式切换交通模式后才查路线。预算、无障碍等不可验证约束仍会阻塞，跳过出发点不会默默删除这些要求。

167项测试通过；合成会话+真实本地RAG三日攻略通过，未调用LLM或百度；浏览器模拟验证选项、自填和跳过分支。报告 rag/eval/reports/optional_departure_v1.json；人工评分未填写，未修改冻结基线或重跑73/25/30。
