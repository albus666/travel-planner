# 旅游 Agent v1 集成

独立入口 `POST /agent/ask`；`RAG_TRAVEL_AGENT_ENABLED=1` 开启，0 关闭（修改后重启）。继续仅监听 127.0.0.1:8100，经 SSH 隧道访问。/ask、/search、/plan 的处理函数保持不变。

## 来源与集成方式

复用桌面 agent/projects/agent-runtime 的 18 个 Python 源文件，以固定源码快照保存在 rag/agent_runtime。VENDORED.json 记录逐文件 SHA-256；不读取或复制原项目 .env。旅游适配层显式提供六个只读工具，不注册文件读写、Shell 或测试执行工具。调用现有 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL，即已配置的 DeepSeek。

现有 LangGraph 问答/规划仍是稳定主流程。新增 Agent 是独立实验入口，没有再嵌套进规划图；它不是动态重规划器，也没有持久化多轮行程。

## 调用

```powershell
python rag/client/agent_query.py --question "龙门石窟的游客评论里有哪些关于步行的反馈？"
python rag/client/agent_query.py --question "查询洛阳今天的天气预报"
python rag/client/agent_query.py --json-file request.json
```

歧义响应 status=needs_clarification，并返回候选。客户端确认后重新提交原问题及以下字段：

```json
{"question":"龙门的游客评论怎么样？","confirmed_poi_id":77498,"confirmed_poi_name":"龙门石窟"}
```

这是显式用户选择字段，界面应在用户实际选择后填写，不能替用户默认选第一个。没有服务端会话 ID；每次请求重新开始有界工具循环。

## 工具与数据边界

| 工具 | 数据与边界 |
|---|---|
| search_pois | 优先本地目录；未找到再用携程 search。只接受 type=sight 且 poiId 为正整数，不将 hotel、poihotel、tripshoot 的 id 当景点 ID |
| local_search | 复用 search 与来源元数据，只保留已确认 POI 的片段，默认 Top5。覆盖介绍、历史、**设施（停车场、充电桩、行李寄存、WiFi、卫生间、吸烟区、园内交通及其参考价格）**、优待、公告与路线片段 |
| ticket_snapshot | 复用固定只读门票 SQL；快照不是实时成交价。**只覆盖门票票种与价格，不含停车、寄存等设施价格** |
| poi_details | 查询已确认 POI，校验返回身份；提供门票、开放说明、公告和优待模块原文 |
| poi_comments | 最多第一页8条，保留评论ID、发布时间、评分与正文，去掉用户昵称、头像及IP属地 |
| weather_forecast | Open-Meteo 中国明确城市未来7天预报，Asia/Shanghai；洛阳市须匹配河南，其他同名地点不猜选 |

搜索词须来自用户原文；不允许模型把“龙门”擅自扩写后再搜索。全名唯一命中可以继续，短名或多个候选要求确认。新发现景点可查资料，但不会自动加入七景点规划池。

获取时间 fetched_at 不等于来源更新时间；provider_updated_at 未提供时为 null。评论 publishTime 转为带时区时间；发布时间未知保留 null。sortType=3 的含义未得到保证，不称“最新评论”；8条默认样本不代表总体评价。

Open-Meteo 官方文档：https://open-meteo.com/en/docs 和 https://open-meteo.com/en/docs/geocoding-api 。返回城市级预报和单位，不将预报当作景点实况或开放证明。当前没有使用景点 BD09 坐标，未实现到 WGS84 的转换；景点坐标天气不在本版范围。

## 输出与执行上限

最多5轮模型请求、6次工具调用；同参数请求在单次运行内复用结果。调度前检查100秒预算，每次外部请求有超时；该预算不是HTTP客户端的严格墙钟中断承诺。不会无限重试。

每个工具记录 state：not_queried、queried_with_evidence、queried_no_evidence、query_failed。返回 tool_trace、run_id、model_steps、warnings 与原始证据。一个工具失败不抹掉已取得的其他证据。

模型最后选择 source_id 和连续原文 quote；服务校验引用存在且 quote 真正在对应正文内，再渲染回答。当前输出侧重引用证据，不提供未经验证的自由改写总结。这种检查不证明评论真实、引用完整或选择必然相关，仍需评审。

## 验收状态

本版是实验候选，不沿用 plan_v1 或 answer_evidence_v2 的评分。离线测试和五题在线冒烟结果见 rag/eval/reports/travel_agent_v1_live.json；最终状态以该报告为准。题目为合成用例，答案质量尚未人工验收。

未实现：地图、景点坐标天气、多约束交通可行性、动态重规划、长期缓存和跨请求会话；未改变现有纯向量检索排序。


2026-10-13 验收更新：Agent v1 五题在线冒烟基线已按用户人工评分冻结，25 pass、0 fail、5 na；合成集，不代表生产准确率或真实用户验收。正式 manifest：`rag/eval/baselines/travel_agent_v1/manifest.json`；评分：`rag/eval/reports/travel_agent_v1_acceptance.json`。AGENT-V1-01（天气代码中文描述）记录为低严重度非阻塞项，本轮不修。此前“待评候选”描述为部署时状态，以本次验收更新为准。

## 设施路由修复（2026-10-13，冻结后）

冻结之后发现：问设施价格（如「老君山景区停车场多少钱」）只调 `ticket_snapshot`/`poi_details`、不调 `local_search`，返回「本次未取得可引用的回答证据」。原因是 PROMPT 只写「介绍历史优先 local_search」，未覆盖设施；两个工具的描述也没写设施边界。资料本身齐备（`poi-77806-facilities_struct` 排第一，含「参考价格：¥10/次」）。

已修 `PROMPT` 与 `local_search`/`ticket_snapshot`/`poi_details` 的描述，工具集合、预算、引用校验、检索排序均未动。线上 4/4 设施问题走 `local_search` 且 `evidence_found`；五个已验收用例重跑 5/5 状态与基线一致；18 项单测通过。

代价要说明：`travel_agent.py` 哈希已变，**冻结快照不再逐字节对应当前部署**。冻结目录原样保留不修改，也不重新冻结；新回答 `human_review` 仍为空，5 例状态一致只能说明无明显回归，不等于重新人工验收。原始数据见 `rag/eval/reports/travel_agent_facility_routing_fix.json/.md`。
