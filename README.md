# 洛阳 RAG 问答项目

当前代码包含纯向量检索、有来源的回答、规则/语义路由的只读门票查询，以及单景点显式混合问题的SQL与RAG分段回答。

新增可关闭的最小LangGraph工具图，复用现有能力；验收记录见 [docs/LANGGRAPH_MILESTONE_2026-10-12.md](docs/LANGGRAPH_MILESTONE_2026-10-12.md)。

独立 `/plan` 已支持洛阳一日游条件追问和有引用的候选草案，交通耗时未核实；接口与限制见 [docs/PLAN_ONE_DAY.md](docs/PLAN_ONE_DAY.md)。

- 服务：`127.0.0.1:8100`，接口 `/health`、`/search`、`/ask`。
- 使用方式与响应字段：[rag/README.md](rag/README.md)。
- 项目记忆：[docs/PROJECT_MEMORY.md](docs/PROJECT_MEMORY.md)。
- 数据采集、向量化与导入脚本保留，PostgreSQL使用 `travel.v2`。
- 评测与冻结基线保留在 `rag/eval/`。
- 最小混合支持及验收：[docs/MIXED_QUERY_MILESTONE_2026-10-12.md](docs/MIXED_QUERY_MILESTONE_2026-10-12.md)。

2026-10-12 按用户要求删除服务器旧 LangGraph 规划、校验、重规划应用及旧前端。
旧8010服务、systemd定义和自动部署钩子已移除；`/travel` 和 `/travel/` 返回410。
后续 Agent 从当前 RAG 能力重新实现。删除旧应用时环境和密钥配置未修改；后续新增路由/混合支持开关，复用既有密钥。
