# RAG 检索模块

洛阳景点知识库的**语义检索**层：BGE-M3 dense 向量 + PostgreSQL/pgvector 余弦检索。
`/search` 负责「问题 → 找到相关片段」，保持纯向量排序；`/ask` 另外调用回答用 LLM，返回逐条引用、证据原文和资料限制。

## 最小回答链路（2026-10-12）

`POST /ask` 默认 `top_k=5`。文本问题流程为 BGE-M3 → 原有 PostgreSQL 向量检索 → 补读片段来源元数据 → DeepSeek → 引用校验。2026-10-12 新增单景点门票文案的只读 SQL 路径，见下节。未加入别名、父子 POI 或主题重排。`/search` 的默认值仍为 3，返回字段不变。

服务器沿用 `.env` 中的 `LLM_BASE_URL`、`LLM_MODEL`、`LLM_API_KEY`。调用方式参考 [DeepSeek Chat Completions 官方文档](https://api-docs.deepseek.com/api/create-chat-completion/)，使用 JSON 输出；不需要新增 SDK。

```bash
curl -s http://127.0.0.1:8100/ask \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d '{"question":"应天门遗址有什么参观公告？","top_k":5}'
```

```powershell
powershell -ExecutionPolicy Bypass -File rag\client\ask_http.ps1 -Ask -QuestionFile rag\fixtures\my_q.txt
```

客户端默认仍访问 `/search`；添加 `-Ask` 才请求回答，默认取 5 条。临时 SSH 隧道和受限权限的密钥副本在结束时清理。

回答包含 `question`、`top_k`、`status`（`answered` / `insufficient_evidence`）、`answer`、`citations`、`warnings`、`retrieved_sources`、`elapsed_ms`。`citations` 只列实际被使用的片段，包括 `chunk_id`、`poi_id`、景点、主题、`source_url`、`collected_at`、`verify_status` 和 `quotes`；`retrieved_sources` 保存原始 top-k 供调试与人工复核。

模型输出的来源编号必须存在，支持摘录必须是对应片段中的连续原文，未通过则拒绝展示生成事实。答案涉及多个景点的公告/优待/入园政策，而问题未明确列出这些景点时，服务请求澄清，避免展示跨景点政策；明确多景点比较可保留。这是回答层保守校验，不改召回或排序，也不能解决所有单一错误景点引用。该校验不能自动证明“摘录充分支持结论”，也不能证明原始资料真实或当前有效。服务统一提示易变信息核对采集时间与官方渠道，引用未核验资料时标明未人工核验。模型不可用返回 502，不伪装为资料不足；检索链路失败返回 500。回答目前为单轮、非流式，无会话记忆。

检查命令（服务器，项目根）：

```bash
PYTHONPATH=rag .venv/bin/python -m unittest discover -s rag/eval -p test_answer_service.py -v
.venv/bin/python rag/eval/runners/run_answer_review.py --output /tmp/travel_answer_review.json
```

9 个代表案例是开发验收样本，包含路线、公告、模糊与明确景点的老人政策、子景点、实时票价、实时开放、不存在的景点和诱导虚构。不能据此宣称生产准确率。

## 门票只读 SQL 路径

问“龙门石窟的门票资料记载是什么？”时，规则识别门票价格/原文意图，从数据库完整名称定位唯一景点，再以固定 SQL 和绑定 poi_id 读取 `v2.poi_details.ticket_raw`。不接收用户 SQL，不让 LLM 决定查询。规则已识别的问题不编码，语义改写识别可使用BGE-M3；SQL查询与模板回答本身不调用回答模型。连接设置 `default_transaction_read_only=on`，超时5秒。

```bash
curl -s http://127.0.0.1:8100/ask \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d '{"question":"龙门石窟的门票资料记载是什么？"}'
```

响应新增 `route`（`vector` / `sql_ticket`）和 `structured_data`。SQL 路径的 `structured_data` 返回景点、原样 `ticket_raw`、详情是否存在、来源表/字段、来源 URL、采集时间及核验状态；不返回换算后的金额。引用用 `SQL1` 和真实记录位置，`chunk_id=null`，避免伪称来自向量片段。

- 普通门票资料问题：返回原文及采集时间，提醒仅为快照；“门票￥90起”保持原样。
- 空值或没有详情：明确无法确认，不推断免费；不存在/模糊/多景点名称请求一个完整景点名称。
- 询问今天价格或特定票种准确售价：可展示采集原文，但状态为 insufficient_evidence，不把起价当成人票或实时价格。
- 优待/免票、路线、介绍、设施、停车、开放状态等问题保持原向量路径；第一版不做别名、不做多景点票价汇总，也不提供实时开放/房态。

`RAG_SQL_TICKET_ENABLED=0` 可关闭该路由（写入服务器 `.env` 后重启），恢复原回答路径；默认开启。LLM 提示词与模型未修改。测试与真实值对照：

```bash
PYTHONPATH=rag RAG_SEMANTIC_ROUTING_ENABLED=0 .venv/bin/python -m unittest discover -s rag/eval -p 'test_*.py' -v
PYTHONPATH=rag .venv/bin/python rag/eval/runners/run_ticket_eval.py \
  --output rag/eval/reports/sql_ticket_new_run.json
```

## Store分类与语义路由实验

边界表见 `docs/ROUTING_STORE_CONTRACT.md`。`classify_intent` 是保持旧逻辑的纯分类器包装，返回 `Intent(store, method, reason)`；store仅有 `v2.poi_details.ticket_raw` 和 `v2.rag_chunks`，不负责景点别名或实体定位。

`RAG_SEMANTIC_ROUTING_ENABLED=1` 启用独立实验：先保护优待、公告、入园政策、路线和设施等RAG边界，再使用旧票价规则，未匹配时复用BGE-M3查询向量做票价/非票价原型kNN。新走SQL的题仍须通过原resolve_poi，只查询原始问题中的完整名称。匹配不出唯一名称就拒答，模型不生成SQL。

源码默认关闭该实验，服务器当前配置为开启；设置0并重启可回退。原型范例与阈值在 `service/routing_prototypes.json`，修改需重启；原型只在启动时编码一次。RAG检索复用语义判断已算的向量，不重复编码。`/search` 返回格式和相似度排序不变。无LLM意图分类调用。

路由评测与版本对照见 `docs/ROUTING_EVALUATION_2026-10-12.md`。运行：

```bash
PYTHONPATH=rag .venv/bin/python rag/eval/runners/run_routing_eval.py \
  --output rag/eval/reports/new_legacy_rule_run.json
# 上面评测的是纯分类器；语义候选和在线路由分别使用另两个脚本
PYTHONPATH=rag HF_HUB_OFFLINE=1 .venv/bin/python rag/eval/runners/eval_semantic_routing.py \
  --output rag/eval/reports/new_semantic_candidate_run.json
.venv/bin/python rag/eval/integration/verify_routing_live.py \
  --output rag/eval/reports/new_live_routing_run.json
```

## 目录结构

```text
rag/
├── retrieval/                   # 检索核心（可被服务/脚本复用）
│   ├── search_chunks.py         # 模型加载、问题编码、pgvector 查询（主入口）
│   └── search_from_file.py      # 从 UTF-8 文件读问题再检索（规避 shell 中文引号问题）
├── service/                     # 常驻 HTTP 服务（模型只加载一次）
│   ├── retrieval_server.py      # FastAPI：/health、/search
│   ├── start_retrieval_server.sh
│   └── stop_retrieval_server.sh
├── eval/                        # 检索评测
│   ├── run_eval.py              # hit@k 统计
│   └── cases/eval_questions.jsonl   # 用例（问题 + 预期景点 + 预期主题）
├── client/                      # 本机操作入口（PowerShell，纯 ASCII 以免解析出错）
│   ├── run_on_server.ps1        # 在服务器上跑检索（走常驻服务）
│   ├── ask_http.ps1             # 本机直接 HTTP 调用（自动开一次性 SSH 转发）
│   └── open_db_tunnel.ps1       # 可选：把服务器 Postgres 映射到本机
└── fixtures/                    # 示例问题文本（UTF-8）
    ├── sample_question.txt
    └── my_q.txt
```

## 前置条件

- 依赖：`FlagEmbedding`、`psycopg[binary]`、`fastapi`、`uvicorn`、`numpy`
- 数据：`v2.rag_chunks.embedding` 已用 **BGE-M3 dense（1024 维）** 写满
- 环境变量 `DATABASE_URL` 指向 `travel` 库（项目根 `.env`）
- 服务器无 GPU，模型以 CPU 加载（`use_fp16=False`）

## 常用操作

### 1. 启动 / 停止常驻服务（服务器）

```bash
bash rag/service/start_retrieval_server.sh   # 预热一次，之后查询约 0.3s
bash rag/service/stop_retrieval_server.sh
```

### 2. 查询（本机，推荐）

```powershell
powershell -ExecutionPolicy Bypass -File rag\client\run_on_server.ps1
powershell -ExecutionPolicy Bypass -File rag\client\run_on_server.ps1 -QuestionFile rag\fixtures\my_q.txt
```

### 3. 直接 HTTP 调用

服务只监听服务器的 `127.0.0.1:8100`，因此：

**在服务器上**（已登录 SSH）：

```bash
curl -s http://127.0.0.1:8100/health
curl -s http://127.0.0.1:8100/search \
  -H 'Content-Type: application/json; charset=utf-8' \
  -d '{"question":"龙门石窟的游览路线是什么？","top_k":3}'
```

**在本机**（无需手动开隧道，脚本会临时转发）：

```powershell
powershell -ExecutionPolicy Bypass -File rag\client\ask_http.ps1 -QuestionFile rag\fixtures\my_q.txt -TopK 5
```

或自己开一个常驻转发窗口后再 curl：

```powershell
ssh -i key\cursor-pilot.pem -N -L 18100:127.0.0.1:8100 ubuntu@52.199.126.245
# 然后: curl http://127.0.0.1:18100/search -d '{"question":"...","top_k":3}'
```

响应示例：

```json
{
  "question": "龙门石窟的游览路线是什么？",
  "top_k": 3,
  "elapsed_ms": 325.1,
  "hits": [
    {"chunk_id":"poi-77498-visit_tips","poi_id":77498,"name":"龙门石窟",
     "theme":"visit_tips","theme_label":"游览路线与建议","text":"...","similarity":0.701}
  ]
}
```

### 4. 跑评测

```powershell
powershell -ExecutionPolicy Bypass -File rag\client\run_on_server.ps1 -Eval
```

## 评测说明

`eval/cases/eval_questions.jsonl` 每行一个 JSON：

| 字段 | 说明 |
|---|---|
| `id` | 用例编号 |
| `question` | 用户问题 |
| `expect_name` | 预期景点名（与 `v2.attractions.name` 完全一致） |
| `expect_theme` | 预期主题：`overview` / `history_culture` / `visit_tips` / `facilities` / `notice` / `preferential` / `entry_policy` |
| `note` | 出题意图（评测时忽略） |

命中规则：top-k 中任一条同时满足 `name` 与 `theme` 即 HIT。

## 注意

新增独立 `/plan`：日期/出发地/同行人/偏好/节奏/交通缺失先追问，补齐后生成有引用的一日游候选草案。`RAG_PLANNING_ENABLED=1`启用，问答路由不变；使用 `client/plan_query.py` 或JSON POST。使用范围、七景点候选池与未核实事项见 `docs/PLAN_ONE_DAY.md`。

`RAG_LANGGRAPH_ENABLED=1`让/ask走现有路由→按需SQL/检索→回答校验→合并的最小LangGraph图。响应包含workflow、node_trace、tool_results；开关为0时完全走原问答并省略这些字段，/search始终旁路。依赖声明 `rag/requirements-langgraph.txt`；细节 `docs/LANGGRAPH_MILESTONE_2026-10-12.md`。

`/ask`新增最小混合支持，服务器 `RAG_MIXED_ENABLED=1`：单景点明确同时询问门票与路线/历史/设施/优待时，返回route=mixed、required_stores与逐项tasks状态。SQL原文和RAG回答分段引用；某部分缺证据不抹掉另一部分。设为0并重启可关闭混合支持，不改变现有语义路由阈值或/search排序。多景点和任意自然语言拆解暂不支持。验收见 `docs/MIXED_QUERY_MILESTONE_2026-10-12.md`。

- 查询向量用与入库**同一个** BGE-M3 dense 模型；不要混用其它 Embedding。
- 查询向量不入库，仅作为 SQL 参数。
- 当前结构化门票字段ticket_raw仍是采集快照，不能确认实时票价；当前开闭园状态也没有实时数据接口。
